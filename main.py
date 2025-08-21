import os
import base64
import json
from datetime import datetime, timedelta
import google.generativeai as genai
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests
import time
from dotenv import load_dotenv

# --- CONFIGURATION ---
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# --- 1. GMAIL AUTHENTICATION & EMAIL FETCHING ---
def get_gmail_service():
    """Authenticates with the Gmail API and returns the service object."""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
            
    return build('gmail', 'v1', credentials=creds)

def search_emails_last_24_hours(service):
    """Searches for job-related emails from the last 24 hours."""
    try:
        yesterday = datetime.now() - timedelta(days=1)
        # Expanded query to better catch rejection emails
        query = f'(subject:"application" OR subject:"interview" OR subject:"assessment" OR subject:"update on your application"OR subject:"your application") after:{yesterday.strftime("%Y/%m/%d")}'
        
        print(f"Searching Gmail with query: {query}")
        response = service.users().messages().list(userId='me', q=query).execute()
        messages = response.get('messages', [])
        
        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
            messages.extend(response.get('messages', []))
        return messages
    except HttpError as error:
        print(f'An error occurred during email search: {error}')
        return []

def get_email_body(service, msg_id):
    """
    Fetches the full content for a given message ID.
    It prioritizes plain text but falls back to HTML if necessary.
    """
    try:
        message = service.users().messages().get(userId='me', id=msg_id, format='full').execute()
        payload = message.get('payload', {})
        parts = payload.get('parts')
        
        if parts:
            for part in parts:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data: return base64.urlsafe_b64decode(data).decode('utf-8')
            for part in parts:
                if part['mimeType'] == 'text/html':
                    data = part['body'].get('data')
                    if data: return base64.urlsafe_b64decode(data).decode('utf-8')

        elif 'body' in payload and 'data' in payload['body']:
            data = payload['body']['data']
            return base64.urlsafe_b64decode(data).decode('utf-8')
            
        return ""
    except HttpError as error:
        print(f'An error occurred while fetching email body: {error}')
        return ""

# --- 2. PARSE WITH GEMINI AI ---
def parse_content_with_gemini(content):
    """Uses Gemini to extract company, role, status, and source from email content."""
    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set.")
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.5-flash')
    
    prompt = f"""
    Analyze the following email and extract four pieces of information: Company Name, Job Title, Application Status, and Application Source.
    
    1.  **Status**: Must be one of these keywords: 'Applied', 'Interview', 'Assessment', 'Offer', 'Rejected'. 
        - If the email is a simple confirmation, status is 'Applied'.
        - If it mentions a test or coding challenge, use 'Assessment'.
        - If it mentions a call or meeting with a person, use 'Interview'.
        - If it says they are not moving forward or the position is filled, use 'Rejected'.

    2.  **Source**: Must be one of these keywords: 'LinkedIn', 'Indeed', 'Naukri', 'Foundit', 'Company Website'.
        - Determine the source from the email content. If it's not a known job board, assume it's 'Company Website'.

    Format the output as a clean JSON object with four keys: "company", "role", "status", and "source".
    If any information cannot be found, use the string "N/A".

    Email content snippet:
    ---
    {content[:8000]} 
    ---
    """
    
    try:
        response = model.generate_content(prompt)
        json_str = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(json_str)
    except Exception as e:
        print(f"Error parsing with Gemini: {e}")
        return None

# --- 3. NOTION DATABASE INTERACTION ---
def read_notion_database():
    """Reads all existing entries from the Notion database and returns them."""
    notion_key = os.getenv('NOTION_API_KEY')
    database_id = os.getenv('NOTION_DATABASE_ID')
    if not notion_key or not database_id:
        raise ValueError("NOTION environment variables not set.")

    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {"Authorization": f"Bearer {notion_key}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    
    db_data = []
    has_more = True
    start_cursor = None

    while has_more:
        payload = {}
        if start_cursor: payload['start_cursor'] = start_cursor
            
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"Failed to read Notion database: {response.text}")
            return []

        data = response.json()
        results = data.get('results', [])
        
        for item in results:
            properties = item.get('properties', {})
            company_prop = properties.get('Company', {}).get('rich_text', [])
            role_prop = properties.get('Role', {}).get('title', [])
            status_prop = properties.get('Status', {}).get('select', {})
            source_prop = properties.get('Source', {}).get('select', {})
            
            company = company_prop[0]['plain_text'] if company_prop else "N/A"
            role = role_prop[0]['plain_text'] if role_prop else "N/A"
            status = status_prop.get('name') if status_prop else "N/A"
            source = source_prop.get('name') if source_prop else "N/A"
            
            db_data.append({'page_id': item['id'], 'company': company.lower(), 'role': role.lower(), 'status': status, 'source': source})
            
        has_more = data.get('has_more', False)
        start_cursor = data.get('next_cursor')
        
    print(f"Successfully read {len(db_data)} entries from Notion.")
    return db_data

def add_to_notion(data):
    """Adds a new application entry to the Notion database."""
    notion_key = os.getenv('NOTION_API_KEY')
    database_id = os.getenv('NOTION_DATABASE_ID')
    url = "https://api.notion.com/v1/pages"
    headers = {"Authorization": f"Bearer {notion_key}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    
    payload = {
        "parent": {"database_id": database_id},
        "properties": {
            "Role": {"title": [{"text": {"content": data.get("role", "N/A")}}]},
            "Company": {"rich_text": [{"text": {"content": data.get("company", "N/A")}}]},
            "Status": {"select": {"name": data.get("status", "Applied")}},
            "Source": {"select": {"name": data.get("source", "N/A")}},
            "Applied Date": {"date": {"start": datetime.now().strftime('%Y-%m-%d')}}
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"-> Successfully ADDED to Notion: {data.get('role')} at {data.get('company')}")
    else:
        print(f"-> Failed to add to Notion. Status: {response.status_code}, Response: {response.text}")

def update_notion_entry(page_id, updates):
    """Updates properties of an existing entry in the Notion database."""
    notion_key = os.getenv('NOTION_API_KEY')
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {"Authorization": f"Bearer {notion_key}", "Content-Type": "application/json", "Notion-Version": "2022-06-28"}
    
    properties_to_update = {}
    if 'Status' in updates:
        properties_to_update['Status'] = {"select": {"name": updates['Status']}}
    if 'Source' in updates:
        properties_to_update['Source'] = {"select": {"name": updates['Source']}}

    if not properties_to_update:
        print("-> No new information to update.")
        return

    payload = {"properties": properties_to_update}

    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code == 200:
        print(f"-> Successfully UPDATED entry in Notion with: {updates}")
    else:
        print(f"-> Failed to update Notion. Status: {response.status_code}, Response: {response.text}")

# --- MAIN EXECUTION LOGIC ---
def main():
    """Main function to run the job tracker."""
    load_dotenv()
    print("Starting job application tracking script...")
    
    notion_db = read_notion_database()
    gmail_service = get_gmail_service()
    messages = search_emails_last_24_hours(gmail_service)
    
    if not messages:
        print("No new job-related emails found in the last 24 hours.")
        return

    print(f"Found {len(messages)} new emails to process.")
    
    for msg_summary in reversed(messages): # Process oldest first
        msg_id = msg_summary['id']
        print(f"\nProcessing email ID: {msg_id}...")
        
        email_body = get_email_body(gmail_service, msg_id)
        if not email_body:
            print("-> Could not retrieve email body. Skipping.")
            continue
        
        parsed_data = parse_content_with_gemini(email_body)
        if not parsed_data or parsed_data.get('company', 'N/A') == 'N/A' or parsed_data.get('role', 'N/A') == 'N/A':
            print("-> Gemini could not extract company or role. Skipping.")
            continue
        
        company_name = parsed_data.get('company', '').lower()
        role_name = parsed_data.get('role', '').lower()
        new_status = parsed_data.get('status')
        new_source = parsed_data.get('source')

        # Match on both company and role
        existing_app = next((app for app in notion_db if app['company'] == company_name and app['role'] == role_name), None)
        
        if existing_app:
            print(f"-> Found existing application for {role_name.title()} at {company_name.title()}.")
            updates_to_make = {}
            
            # Check if status needs updating
            if new_status != 'Applied' and new_status != existing_app.get('status'):
                updates_to_make['Status'] = new_status
            
            # Check if source is missing and can be filled
            if (not existing_app.get('source') or existing_app.get('source') == 'N/A') and new_source != 'N/A':
                updates_to_make['Source'] = new_source
            
            if updates_to_make:
                update_notion_entry(existing_app['page_id'], updates_to_make)
            else:
                print("-> No new information to update. Skipping.")

        else:
            # It's a new application, so add it to the database.
            print(f"-> Found new application for {role_name.title()} at {company_name.title()}.")
            add_to_notion(parsed_data)
        
        time.sleep(1)

if __name__ == '__main__':
    main()
