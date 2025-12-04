from jira_client.jira_client import JiraClient

def main():
    client = JiraClient(base_url="mock", token="mock")
    
    boards = client.get_boards()
    print("Boards:", boards)

    sprint = client.get_active_sprint(board_id=boards[0]["id"])
    print("Active Sprint:", sprint)

    issues = client.get_issues(sprint_id=sprint["id"])
    print("\nIssues:")
    for issue in issues:
        print(issue)


if __name__ == "__main__":
    main()