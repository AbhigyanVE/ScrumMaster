from clients.taiga_client import TaigaClient

def main():
    client = TaigaClient(use_mock=True)

    projects = client.get_projects()
    print("Projects:", projects)

    project = projects[0]
    sprint = client.get_active_sprint(project_slug=project["slug"])
    print("Active Sprint:", sprint)

    issues = client.get_issues(project_slug=project["slug"], sprint_id=sprint["id"])
    print("\nIssues:")
    for issue in issues:
        print(issue)

if __name__ == "__main__":
    main()