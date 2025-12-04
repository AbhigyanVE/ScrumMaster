from pydantic import BaseModel
from typing import Optional

class Issue(BaseModel):
    key: str
    summary: str
    status: str
    assignee: Optional[str]
    story_points: Optional[int]
    created: Optional[str]
    updated: Optional[str]