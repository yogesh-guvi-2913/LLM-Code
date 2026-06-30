from pydantic import BaseModel
from typing import Dict, Any, List


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
