from typing import List
from taiga import TaigaAPI
from models.issue_models import Issue

class TaigaClient:
    """
    Taiga client that either connects to real API or uses synthetic fallback.
    """

    def __init__(self, use_mock: bool = True, username: str = None, password: str = None, token: str = None):
        self.use_mock = use_mock

        if not use_mock:
            self.api = TaigaAPI()
            if token:
                self.api = TaigaAPI(token=token)
            elif username and password:
                self.api.auth(username=username, password=password)
            else:
                raise ValueError("Provide token or username/password for real auth")

    def get_projects(self):
        if self.use_mock:
            return [{"id": 1, "name": "Backend", "slug": "backend"}]
        return self.api.projects.list()

    def get_active_sprint(self, project_slug):
        if self.use_mock:
            return {"id": 99, "name": "Sprint 24", "is_closed": False}
        sprints = self.api.milestones.list(project=project_slug)
        active = [s for s in sprints if not s.is_closed]
        return active[0] if active else None

    def get_issues(self, project_slug, sprint_id):
        if self.use_mock:
            return [
                Issue(
                    key="PROJ-101",
                    summary="Implement login",
                    status="In Progress",
                    assignee="Abhi",
                    story_points=5,
                    created="2025-02-01T10:00:00Z",
                    updated="2025-02-15T14:05:00Z",
                ),
                Issue(
                    key="PROJ-102",
                    summary="Validation bug",
                    status="To Do",
                    assignee="John",
                    story_points=3,
                    created="2025-02-02T09:00:00Z",
                    updated="2025-02-10T11:20:00Z",
                ),
            ]

        # real implementation later:
        stories = self.api.user_stories.list(project=project_slug)
        return [
            Issue(
                key=str(s.id),
                summary=s.subject,
                status=s.status,
                assignee=s.assigned_to.get("username") if s.assigned_to else None,
                story_points=s.points,
                created=s.created_date,
                updated=s.modified_date,
            )
            for s in stories
        ]
