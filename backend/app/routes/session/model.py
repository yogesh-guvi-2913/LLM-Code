from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class SessionStartRequest(BaseModel):
    authToken: str
    testId: str


class SessionStopRequest(BaseModel):
    authToken: str
    sessionId: str


class FileChangeItem(BaseModel):
    path: str
    content: str = ""
    action: str = "update"


class SyncFilesRequest(BaseModel):
    sessionId: str
    changes: List[FileChangeItem]


class CreateTestRequest(BaseModel):
    authToken: str
    testId: str
    name: str
    description: str = ""
    duration: int = 3600
    codeEdit: int = 0
    requirements: List[Dict[str, Any]] = []
    checks: List[Dict[str, Any]] = []
    techStack: Dict[str, str] = {}
    flashTemplateId: Optional[str] = Field(default=None, description="Flash sandbox template ID")
    flashScoringEnabled: bool = Field(default=True, description="Enable Flash automated scoring")
