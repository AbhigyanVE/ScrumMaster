from taiga_client.taiga_client import TaigaClient

def main():
    client = TaigaClient(username="demo", password="demo")  # or token
    projects = client.get_projects()
    print("Projects:", projects)

    # pick one project (for demo)
    project = projects[0]
    sprint = client.get_active_sprint(project_slug_or_id=project.slug or project.id)
    print("Active Sprint / milestone:", sprint)

    issues = client.get_issues(project_slug_or_id=project.slug or project.id, sprint_id=sprint.id if sprint else None)
    print("Issues / User-Stories:")
    for issue in issues:
        print(issue)

if __name__ == "__main__":
    main()