import requests
from requests.auth import HTTPBasicAuth
import json
from collections import Counter

# -----------------------------------
# REQUIRED INPUTS
# -----------------------------------
EMAIL = ""                     # your Atlassian email
API_TOKEN = ""                    # your Atlassian API token
JIRA_BASE_URL = "https://.atlassian.net/"  # your Jira Cloud URL

PROJECT_NAME = "AI First Optimization VE.com"
# PROJECT_NAME = "AI Ecosystem on Website"

# -----------------------------------
# BUILD JQL & REQUEST ISSUES
# -----------------------------------
search_url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"

jql = f'project = "{PROJECT_NAME}"'

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
    print("Error:", response.status_code, response.text)
    exit()

data = response.json()

# Diagnostic: show all statuses and status categories
status_category_counter = Counter()
status_details = {}

for issue in data.get("issues", []):
    st = issue["fields"]["status"]
    name = st["name"]
    category = st["statusCategory"]["name"]  # e.g., "To Do", "In Progress", "Done"
    
    status_category_counter[category] += 1
    status_details.setdefault(name, category)

print("\n--- Status Category Summary (matches your board) ---")
for cat, count in status_category_counter.items():
    print(f"{cat}: {count}")

print("\nDetailed status mapping:")
for name, cat in status_details.items():
    print(f"{name}  -->  {cat}")

# -----------------------------------
# SAVE FULL JSON TO del.json
# -----------------------------------
with open("del.json", "w") as f:
    json.dump(data, f, indent=2)

# -----------------------------------
# SUMMARY: COUNT ISSUES BY STATUS
# -----------------------------------
status_counter = Counter()

for issue in data.get("issues", []):
    fields = issue.get("fields", {})
    status = fields.get("status", {}).get("name", "Unknown")
    status_counter[status] += 1

# -----------------------------------
# PRINT SUMMARY IN TERMINAL
# -----------------------------------
print("\n--- Project Summary ---")
print(f'Project: "{PROJECT_NAME}"')
print(f"Total Issues Found: {len(data.get('issues', []))}\n")

print("Status Breakdown:")
for status, count in status_counter.items():
    print(f"  {status}: {count}")

print("\nFull raw data written to del.json\n")
