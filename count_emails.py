import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re
from datetime import datetime, timedelta

# --- CONFIGURATION ---
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
OUTPUT_FILE = 'found_subjects.txt'
# **UPDATED**: Set how many days back you want to search.
DAYS_TO_SEARCH = 60

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

def main():
    """
    Main function to connect to Gmail, count recent emails, and log the subjects of matching emails.
    """
    print("Connecting to Gmail to count and log your application emails...")
    
    # The phrases we are looking for in the subject lines.
    search_phrases = [
        "application received",
        "thank you for applying",
        "your application for"
    ]
    pattern = re.compile('|'.join(search_phrases), re.IGNORECASE)
    days_to_search = DAYS_TO_SEARCH

    try:
        service = get_gmail_service()
        
        # **MODIFIED**: Calculate the date to search from
        search_after_date = (datetime.now() - timedelta(days=days_to_search)).strftime('%Y/%m/%d')
        query = f"after:{search_after_date}"
        
        print(f"\nSearching for all emails received in the last {days_to_search} days...\n")

        # Get the list of messages within the date range
        response = service.users().messages().list(userId='me', q=query).execute()
        messages = response.get('messages', [])
        
        while 'nextPageToken' in response:
            page_token = response['nextPageToken']
            response = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
            messages.extend(response.get('messages', []))

        # **NEW**: Check if the count is too high and adjust if necessary
        if len(messages) >= 500:
            print(f"Found {len(messages)} emails, which is over the 500 limit. Reducing search window to 30 days.")
            days_to_search = 30  # Reduce the days
            search_after_date = (datetime.now() - timedelta(days=days_to_search)).strftime('%Y/%m/%d')
            query = f"after:{search_after_date}"
            
            print(f"\nRe-searching for all emails received in the last {days_to_search} days...\n")
            
            # Re-run the search with the new query
            response = service.users().messages().list(userId='me', q=query).execute()
            messages = response.get('messages', [])
            
            while 'nextPageToken' in response:
                page_token = response['nextPageToken']
                response = service.users().messages().list(userId='me', q=query, pageToken=page_token).execute()
                messages.extend(response.get('messages', []))

        if not messages:
            print(f"No emails found in the last {days_to_search} days. You can try increasing the initial DAYS_TO_SEARCH.")
            return

        total_emails_checked = len(messages)
        passed_query_count = 0
        
        print(f"Total emails to check in the last {days_to_search} days: {total_emails_checked}.")

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            f.write(f"--- Subjects of Found Application Emails (Last {days_to_search} Days) ---\n\n")

        # Since the number of emails is now much smaller, we can process them
        # without worrying about the batch limit.
        for i, message_info in enumerate(messages):
            print(f"Checking email {i+1}/{total_emails_checked}...", end='\r')
            msg_id = message_info['id']
            message = service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['subject']).execute()
            
            headers = message.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), 'No Subject')
            
            if pattern.search(subject):
                passed_query_count += 1
                with open(OUTPUT_FILE, 'a', encoding='utf-8') as f:
                    f.write(f"{subject}\n")

        print("\n\n" + "="*50)
        print("          Scan Complete")
        print("="*50)
        print(f"  Total emails checked: {total_emails_checked}")
        print(f"  Emails that passed the query: {passed_query_count}")
        print(f"  The subjects have been written to '{OUTPUT_FILE}'")
        print("="*50 + "\n")

    except HttpError as error:
        print(f'\nAn error occurred: {error}')
    except Exception as e:
        print(f'\nAn unexpected error occurred: {e}')

if __name__ == '__main__':
    main()
