import requests

BASE_URL = "https://projects.vestaging.in:9093/api/v1"

USERNAME = "AbhigyanSen"
PASSWORD = "abhigyan'styga"
PROJECT_SLUG = "sandipghosh-ai-scrum-master"  # from your URL

def taiga_login(username, password):
    url = f"{BASE_URL}/auth/token"
    payload = {
        "username": username,
        "password": password,
        "type": "normal"
    }
    r = requests.post(url, json=payload, verify=False)
    print("Login Response:", r.text)  # debug
    r.raise_for_status()
    return r.json()["auth_token"]

def get_project(auth_token, slug):
    url = f"{BASE_URL}/projects/by_slug?slug={slug}"
    headers = {"Authorization": f"Bearer {auth_token}"}
    r = requests.get(url, headers=headers, verify=False)
    r.raise_for_status()
    return r.json()


def get_user_stories(auth_token, project_id):
    url = f"{BASE_URL}/userstories?project={project_id}"
    headers = {"Authorization": f"Bearer {auth_token}"}
    r = requests.get(url, headers=headers, verify=False)
    r.raise_for_status()
    return r.json()


def get_tasks(auth_token, project_id):
    url = f"{BASE_URL}/tasks?project={project_id}"
    headers = {"Authorization": f"Bearer {auth_token}"}
    r = requests.get(url, headers=headers, verify=False)
    r.raise_for_status()
    return r.json()


def get_taskboard(auth_token, project_id, milestone_id):
    # milestone_id = sprint ID
    url = f"{BASE_URL}/taskboard/{project_id}/{milestone_id}"
    headers = {"Authorization": f"Bearer {auth_token}"}
    r = requests.get(url, headers=headers, verify=False)
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    print("🔐 Logging in…")
    token = taiga_login(USERNAME, PASSWORD)
    print("✅ Auth Token:", token)

    print("\n📌 Fetching project…")
    project = get_project(token, PROJECT_SLUG)
    print("Project ID:", project["id"])
    print("Project Name:", project["name"])

    project_id = project["id"]

    print("\n📌 Fetching user stories…")
    user_stories = get_user_stories(token, project_id)
    print("User Stories:", len(user_stories))

    print("\n📌 Fetching tasks…")
    tasks = get_tasks(token, project_id)
    print("Tasks:", len(tasks))

    # OPTIONAL: If you want sprint / taskboard data
    if user_stories:
        milestone_id = user_stories[0].get("milestone")  # crude way to find a sprint
        if milestone_id:
            print("\n📌 Fetching Taskboard for Sprint:", milestone_id)
            taskboard = get_taskboard(token, project_id, milestone_id)
            print("Taskboard Columns:", taskboard.keys())
        else:
            print("\n⚠️ No milestone found in stories to fetch taskboard.")
