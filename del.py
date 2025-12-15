import requests
from requests.auth import HTTPBasicAuth
import json
from collections import Counter
from dotenv import load_dotenv
import os

# -----------------------------------
# REQUIRED INPUTS
# -----------------------------------
load_dotenv()

EMAIL = os.getenv("JIRA_EMAIL")                 # your Atlassian email
API_TOKEN = os.getenv("JIRA_API_TOKEN")         # your Atlassian API token
JIRA_BASE_URL = os.getenv("JIRA_DOMAIN")        # your Jira Cloud URL

if not all([EMAIL, API_TOKEN, JIRA_BASE_URL]):
    raise RuntimeError(
        "Missing environment variables. "
        "Check JIRA_EMAIL, JIRA_API_TOKEN, JIRA_DOMAIN."
    )

# PROJECT_NAME = "AI First Optimization VE.com"
PROJECT_NAME = "Billion Words Website (1B)"

# -----------------------------------
# BUILD JQL & REQUEST ISSUES
# -----------------------------------
search_url = f"{JIRA_BASE_URL}/rest/api/3/search/jql"
jql = f'project = "{PROJECT_NAME}"'

# -----------------------------------
# PAGINATED FETCH (maxResults capped at 5000)
# -----------------------------------
all_issues = []
start_at = 0
max_results = 5000

while True:
    params = {
        "jql": jql,
        "startAt": start_at,
        "maxResults": max_results,
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
    issues = data.get("issues", [])

    if not issues:
        break

    all_issues.extend(issues)
    start_at += len(issues)

    total = data.get("total", 0)
    print(f"Fetched {len(all_issues)} / {total} issues")

    if start_at >= total:
        break

# -----------------------------------
# Diagnostic: show all statuses and status categories
# -----------------------------------
status_category_counter = Counter()
status_details = {}

for issue in all_issues:
    st = issue["fields"]["status"]
    name = st["name"]
    category = st["statusCategory"]["name"]  # To Do / In Progress / Done

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
    json.dump({"issues": all_issues}, f, indent=2)

# -----------------------------------
# SUMMARY: COUNT ISSUES BY STATUS
# -----------------------------------
status_counter = Counter()

for issue in all_issues:
    fields = issue.get("fields", {})
    status = fields.get("status", {}).get("name", "Unknown")
    status_counter[status] += 1

# -----------------------------------
# PRINT SUMMARY IN TERMINAL
# -----------------------------------
print("\n--- Project Summary ---")
print(f'Project: "{PROJECT_NAME}"')
print(f"Total Issues Found: {len(all_issues)}\n")

print("Status Breakdown:")
for status, count in status_counter.items():
    print(f"  {status}: {count}")

print("\nFull raw data written to del.json\n")