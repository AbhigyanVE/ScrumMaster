from taiga import TaigaAPI
from typing import List
from src.models.issue_models import Issue  # reuse your Issue model (or adapt)

class TaigaClient:
    def __init__(self, api_url: str = None, token: str = None, username: str = None, password: str = None):
        self.api = TaigaAPI(api_url=api_url) if api_url else TaigaAPI()
        if token:
            self.api = TaigaAPI(token=token)
        elif username and password:
            self.api.auth(username=username, password=password)
        else:
            raise ValueError("Need Taiga credentials")

    def get_projects(self):
        return list(self.api.projects.list())

    def get_active_sprint(self, project_slug_or_id) -> dict:
        # Depends on how your organization uses Taiga: they may call them "milestones" or similar.
        # For simplicity, you might fetch all sprints/milestones and pick one marked “active”.
        sprints = list(self.api.milestones.list(project=project_slug_or_id))
        active = [s for s in sprints if s.get('is_closed') == False]
        return active[0] if active else None

    def get_issues(self, project_slug_or_id, sprint_id=None) -> List[Issue]:
        # There are multiple entities in Taiga: user stories, tasks, issues.
        # For a quick demo, fetch user-stories or tasks associated with sprint/project
        # Example:
        stories = list(self.api.user_stories.list(project=project_slug_or_id))
        issues = []
        for s in stories:
            # naive conversion — adapt as appropriate
            issues.append(Issue(
                key=str(s.get('id')),
                summary=s.get('subject'),
                status=s.get('status'),
                assignee=s.get('assigned_to', {}).get('username') if s.get('assigned_to') else None,
                priority=None,  # Taiga may or may not use priority the same way
                story_points=s.get('points'),
                created=s.get('created_date'),
                updated=s.get('modified_date'),
            ))
        return issues