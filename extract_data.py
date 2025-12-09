import requests
import json
import os
from dotenv import dotenv_values
import time

# --- Configuration & Setup ---
ENV_FILE = ".env"
config = dotenv_values(ENV_FILE)

JIRA_DOMAIN = config.get("JIRA_DOMAIN")
JIRA_EMAIL = config.get("JIRA_EMAIL")
JIRA_API_TOKEN = config.get("JIRA_API_TOKEN")

# API Configuration
API_VERSION = "3"
BASE_API_URL = f"{JIRA_DOMAIN}/rest/api/{API_VERSION}"
AUTH_TUPLE = (JIRA_EMAIL, JIRA_API_TOKEN)
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}

# Define the fields we want to extract for each issue
FIELDS_LIST = "key,summary,status,assignee,priority,created,updated,timespent,parent"
MAX_RESULTS_PER_PAGE = 50 

if not all([JIRA_DOMAIN, JIRA_EMAIL, JIRA_API_TOKEN]):
    print("Error: Missing JIRA_DOMAIN, JIRA_EMAIL, or JIRA_API_TOKEN in the .env file.")
    print("Please check your .env file and ensure all variables are correctly set.")
    exit()

# --- Core API Call Functions ---

def get_all_projects():
    """Fetches a list of all projects (spaces) visible to the user."""
    print("--- Step 1: Fetching All Projects ---")
    
    url = f"{BASE_API_URL}/project"
    
    try:
        response = requests.get(url, auth=AUTH_TUPLE, headers=HEADERS, timeout=15)
        response.raise_for_status()
        projects = response.json()
        print(f"Found {len(projects)} projects.")
        return projects
        
    except requests.exceptions.RequestException as err:
        print(f"\n--- Error Fetching Projects ---")
        print(f"An error occurred: {err}")
        try:
            print(f"Jira Error Response: {response.json().get('errorMessages', 'N/A')}")
        except:
            pass
        return None


def fetch_issues_by_jql(jql_query):
    """
    Fetches all issue data for a given JQL query using pagination.
    This is a generalized version of your original script's core logic.
    """
    all_issues = []
    start_at = 0
    total_issues = None
    # Correct endpoint path for the /rest/api/3 base URL
    url = f"{BASE_API_URL}/search/jql" 

    while True:
        params = {
            "jql": jql_query,
            "fields": FIELDS_LIST,
            "startAt": start_at,
            "maxResults": MAX_RESULTS_PER_PAGE
        }
        
        try:
            response = requests.get(
                url, 
                auth=AUTH_TUPLE, 
                headers=HEADERS,
                params=params,
                timeout=15 
            )
            response.raise_for_status()
            data = response.json()
            
            if total_issues is None:
                total_issues = data.get("total", 0)
            
            issues_on_page = data.get("issues", [])
            
            all_issues.extend(issues_on_page)
            
            # Check for the break condition
            if (start_at + len(issues_on_page)) >= total_issues:
                break
            
            start_at += len(issues_on_page)
            
            # Pause briefly to be polite to the Jira API
            time.sleep(0.1) 

        except requests.exceptions.HTTPError as errh:
            print(f"   [Error] Status {response.status_code} for JQL '{jql_query}'")
            try:
                error_details = response.json()
                print(f"   [Jira Error]: {error_details.get('errorMessages', ['Unknown Jira Error'])[-1]}")
            except json.JSONDecodeError:
                 print(f"   [Jira Error]: Could not decode response.")
            return None # Stop fetching for this project
        
        except requests.exceptions.RequestException as err:
            print(f"   [Error] Unexpected error during fetch: {err}")
            return None

    return all_issues, total_issues


# --- Main Logic to Extract All Data ---

def fetch_all_project_data():
    """
    Executes the full extraction process: get projects, then get issues for each project.
    Returns a dictionary where keys are project keys and values are project data.
    """
    projects = get_all_projects()
    if not projects:
        print("Could not retrieve projects. Aborting.")
        return None

    all_data = {}
    
    print("\n--- Step 2: Fetching Issues per Project ---")
    
    for project in projects:
        key = project.get('key')
        name = project.get('name')
        
        if not key:
            print(f"Skipping project with no key: {name}")
            continue

        # The JQL query MUST be restricted (bounded) to a project and a time range 
        # to prevent the "Unbounded JQL" error from Jira Cloud.
        project_jql = f'project = "{key}" AND created >= "2000/01/01" ORDER BY created DESC'
        
        print(f"-> Fetching issues for Project: {name} ({key})...")
        
        # Get the result first, which will be None on error or (issues, total) on success
        result = fetch_issues_by_jql(project_jql) 

        if result is None:
            # If fetch failed, use empty lists and zero counts
            issues = []
            total = 0
        else:
            # If fetch succeeded, safely unpack the tuple
            issues, total = result

        # FIX v2.2: Use len(issues) instead of total to get the ACTUAL count
        actual_count = len(issues)
        
        # Store the project details and its issues
        all_data[key] = {
            "name": name,
            "id": project.get('id'),
            "self_url": project.get('self'),
            "issue_count": actual_count,  # FIX v2.2: Use actual count from issues list
            "issues": issues
        }
        
        # Debug print to verify
        '''
        The Jira API sometimes returns total: 0 in the response metadata when:
        - Using certain field restrictions
        - The JQL query structure confuses the total counter
        - But it still returns all the actual issues in the issues[] array

        and hence we see a discrepancy: -> Fetched 19 issues (API reported 0)
        '''
        print(f"   -> Fetched {actual_count} issues (API reported {total})")

    return all_data

def save_project_data_to_separate_files(project_data, folder_name="JSONs"):
    """
    Saves the data for each project into a separate JSON file within a specified folder.
    """
    print(f"\n--- Step 3: Saving Data to '{folder_name}' Folder ---")
    
    # Create the directory if it doesn't exist
    if not os.path.exists(folder_name):
        os.makedirs(folder_name)
        print(f"Created directory: {folder_name}")

    saved_count = 0
    total_issues = 0

    for project_key, data in project_data.items():
        # Create a clean filename using the project key
        filename = f"{project_key}_issues.json"
        filepath = os.path.join(folder_name, filename)
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                # We save the entire project dictionary (metadata + issues) for context
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"  -> Saved {data['issue_count']} issues for {project_key} to {filepath}")
            saved_count += 1
            total_issues += data['issue_count']

        except Exception as e:
            print(f"  [Error] Failed to save file {filepath}: {e}")

    print(f"\n--- Save Complete ---")
    print(f"Successfully saved data for {saved_count} out of {len(project_data)} projects.")
    print(f"Total issues extracted and saved: {total_issues}")


def extract_and_display_issue_details(issue_data):
    """
    Helper function to process and display individual issue data.
    """
    issues = []
    for key, project_data in issue_data.items():
        issues.extend(project_data.get('issues', []))

    print(f"\n--- Sample Data (First 5 Issues Across All Projects) ---")
    if not issues:
        print("No issues found in any project.")
        return

    for i, issue in enumerate(issues[:5]):
        key = issue.get("key")
        fields = issue.get("fields", {}) 
        summary = fields.get("summary", "No Summary")
        
        # Use the fixed, safe retrieval pattern for potentially None values
        status = fields.get("status", {}).get("name", "Unknown Status")
        assignee = (fields.get("assignee") or {}).get("displayName", "Unassigned")
        
        # Also check priority for None
        priority = (fields.get("priority") or {}).get("name", "Unknown Priority")

        print(f"{i+1}. {key} - {summary}")
        print(f"   Status: {status}, Assignee: {assignee}, Priority: {priority}")
        
    print(f"\nTotal issues found across all projects: {len(issues)}")

# --- Main Execution ---

if __name__ == "__main__":
    print(f"Connecting to Jira at: {JIRA_DOMAIN}...\n")
    
    project_data = fetch_all_project_data()
    
    if project_data:
        # Save data to separate files in the 'JSONs' folder
        save_project_data_to_separate_files(project_data, folder_name="JSONs")
        
        # Display sample data from the aggregated project_data dictionary
        extract_and_display_issue_details(project_data)