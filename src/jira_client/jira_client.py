from typing import List
# from src.models.issue_models import Issue
from models.issue_models import Issue

class JiraClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url
        self.token = token

    def get_boards(self) -> List[dict]:
        # mock board list
        return [
            {"id": 1, "name": "Backend Team"},
            {"id": 2, "name": "Frontend Team"},
        ]

    def get_active_sprint(self, board_id: int) -> dict:
        # mock sprint
        return {"id": 99, "name": "Sprint 42", "state": "active"}

    def get_issues(self, sprint_id: int) -> List[Issue]:
        # mock issues
        return [
            Issue(
                key="PROJ-101",
                summary="Implement login",
                status="In Progress",
                assignee="Abhi",
                priority="High",
                story_points=5,
                created="2025-02-01T10:00:00Z",
                updated="2025-02-15T14:05:00Z",
            ),
            Issue(
                key="PROJ-102",
                summary="API validation bug",
                status="To Do",
                assignee="John",
                priority="Medium",
                story_points=3,
                created="2025-02-02T09:00:00Z",
                updated="2025-02-10T11:20:00Z",
            ),
        ]