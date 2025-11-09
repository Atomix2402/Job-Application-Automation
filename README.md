# Automated Job Application Tracker

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=yellow)
![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-Automated-blue?logo=githubactions&logoColor=white)
![Notion](https://img.shields.io/badge/Notion-Database-black?logo=notion&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini%20AI-Parsing-blue?logo=google&logoColor=white)

An automated Python script that scans your Gmail for job applications, uses AI to parse the details, and automatically populates or updates a Notion database.

## Overview

This project solves the tedious problem of manually tracking job applications. It runs on an automated daily schedule, ensuring your job search stays perfectly organized without any manual effort.

* **Scans Gmail:** Finds all job-related emails from the last 24 hours (applications, interview invites, rejections).
* **Intelligent Parsing:** Uses the Google Gemini AI to read the email and extract the Company Name, Job Role, Application Status, and Source (e.g., LinkedIn, Company Website).
* **Dynamic Notion Sync:** Connects to a Notion database to add or update your applications.
* **Smart Updates:** This is the key feature. If you get an "Assessment" email for a job you've already "Applied" to, the script **updates the status** of the existing row instead of creating a duplicate.

---

## How It Works

This project is built on a 3-step automated workflow that runs once every day.

1. **Scheduled Trigger:** At 4:00 AM IST, a GitHub Actions workflow automatically starts.
2. **Fetch & Parse:** The Python script connects to the Gmail API, finds relevant emails, and sends their content to the Gemini API for analysis.
3. **Sync to Notion:** The script fetches your existing database from Notion. It then intelligently matches the parsed data to existing entries.
   * **New Application?** A new row is created in Notion.
   * **Status Update?** The "Status" (e.g., "Applied" -> "Interview") and "Source" fields are updated on the existing row.
   * **Duplicate?** The script skips it to keep the database clean.

---

## Technology Stack

* **Core Logic:** Python 3.12
* **Authentication:** Google OAuth2 (for Gmail)
* **Automation:** GitHub Actions
* **APIs:**
  * Google Gmail API
  * Google Gemini API
  * Notion API
* **Key Python Libraries:**
  * `google-api-python-client`
  * `google-generativeai`
  * `requests`
  * `python-dotenv`

---

## Setup Guide

Follow these steps to get your own instance of the tracker running.

### Part 1: Get All Your Keys & Credentials

You need to collect four sets of keys.

**1. Google Cloud & Gmail API (`credentials.json`)**
* Go to the [Google Cloud Console](https://console.cloud.google.com/).
* Create a new project.
* Enable the **Gmail API**.
* Go to "Credentials" and create an **"OAuth client ID"**.
* Select the application type as **"Desktop app"**.
* Download the JSON file and rename it to `credentials.json`.

**2. Google AI Studio (Gemini API Key)**
* Go to [Google AI Studio](https://aistudio.google.com/).
* Click **"Get API key"** and create a new key.
* Copy this key.

**3. Notion Integration (Notion API Key)**
* Go to [Notion's My Integrations](https://www.notion.so/my-integrations).
* Create a **"+ New integration"**. Give it a name (e.g., "Job Tracker Bot").
* Copy the **"Internal Integration Secret"** key.

**4. Notion Database (Database ID)**
* Create a new, full-page **Table** in Notion.
* Set up the following columns (names and types are important):
  * **Role** (Type: `Title`)
  * **Company** (Type: `Text`)
  * **Status** (Type: `Select` - Add options: `Applied`, `Assessment`, `Interview`, `Offer`, `Rejected`)
  * **Applied Date** (Type: `Date`)
  * **Source** (Type: `Select`)
* Click the **`•••`** (three-dot) menu in the top-right of your Notion page.
* Click **"+ Add connections"** and add the integration you just created ("Job Tracker Bot").
* From the database URL, copy the **Database ID** (the long string of characters):
  `https://www.notion.so/your-workspace/`**`[THIS_IS_THE_DATABASE_ID]`**`?v=...`
