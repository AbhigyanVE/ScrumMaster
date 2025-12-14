import os
import requests
import json
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from collections import Counter

# -----------------------------------
# LOAD .ENV VARIABLES
# -----------------------------------
load_dotenv()

EMAIL = os.getenv("JIRA_EMAIL")
API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_BASE_URL = os.getenv("JIRA_DOMAIN")

if not EMAIL or not API_TOKEN or not JIRA_BASE_URL:
    print("ERROR: Missing EMAIL, API_TOKEN, or JIRA_BASE_URL in .env")
    exit()

print(f"Connecting to Jira at: {JIRA_BASE_URL}...\n")

# -----------------------------------
# STEP 1: FETCH ALL PROJECTS
# -----------------------------------
projects_url = f"{JIRA_BASE_URL}/rest/api/3/project/search"

print("--- Step 1: Fetching All Projects ---")

projects_response = requests.get(
    projects_url,
    auth=HTTPBasicAuth(EMAIL, API_TOKEN),
    headers={"Accept": "application/json"}
)

if projects_response.status_code != 200:
    print("Error fetching projects:", projects_response.status_code, projects_response.text)
    exit()

projects_data = projects_response.json()
projects = projects_data.get("values", [])

print(f"Found {len(projects)} projects.\n")

# -----------------------------------
# PREPARE OUTPUT FOLDER
# -----------------------------------
output_dir = "JSONs"
os.makedirs(output_dir, exist_ok=True)

# -----------------------------------
# STEP 2: FETCH ISSUES PER PROJECT
# -----------------------------------
print("--- Step 2: Fetching Issues per Project ---")

total_issues_saved = 0
projects_processed = 0

for proj in projects:
    proj_name = proj["name"]
    proj_key = proj["key"]  # used for filenames
    
    print(f"-> Fetching issues for Project: {proj_name} ({proj_key})...")

    search_url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
    jql = f'project = "{proj_name}"'

    params = {
        "jql": jql,
        "maxResults": 5000,
        "fields": "*all"
    }

    response = requests.get(
        search_url,
        params=params,
        auth=HTTPBasicAuth(EMAIL, API_TOKEN),
        headers={"Accept": "application/json"}
    )

    if response.status_code != 200:
        print(f"   !! Error fetching issues for {proj_key}: {response.status_code}")
        continue

    data = response.json()
    issues = data.get("issues", [])
    count = len(issues)
    total_issues_saved += count
    projects_processed += 1

    print(f"   -> Fetched {count} issues (API reported {count})")

    # -----------------------------------
    # STEP 3: SAVE TO JSON FILE
    # -----------------------------------
    filename = f"{proj_key}_issues.json"
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"  -> Saved {count} issues for {proj_key} to {filepath}\n")


# -----------------------------------
# FINAL SUMMARY
# -----------------------------------
print("--- Save Complete ---")
print(f"Successfully saved data for {projects_processed} out of {len(projects)} projects.")
print(f"Total issues extracted and saved: {total_issues_saved}")
print(f"Total issues found across all projects: {total_issues_saved}\n")
