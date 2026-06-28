from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class CodeAction(str, Enum):
    update = "update"
    create = "create"
    delete = "delete"

class FileChange(BaseModel):
    path: str = Field(..., description="File path relative to project root")
    action: CodeAction = Field(default=CodeAction.update)
    content: Optional[str] = Field(None, description="File content for update/create")

class ChatMessage(BaseModel):
    role: str = Field(..., description="user or assistant")
    content: str = Field(..., description="Message content")

class AIRequest(BaseModel):
    message: str = Field(..., description="User's prompt")
    currentFiles: Dict[str, Any] = Field(default_factory=dict, description="Current file state")

class AIResponse(BaseModel):
    type: str = Field(..., description="Response type: text, code, done, error")
    content: Optional[str] = Field(None, description="Text content for text type")
    files: Optional[List[FileChange]] = Field(None, description="Code changes for code type")
    error: Optional[str] = Field(None, description="Error message for error type")

class PromptHistory(BaseModel):
    timestamp: str
    userMessage: str
    aiResponse: str
    codeChanges: List[FileChange] = Field(default_factory=list)

class WebSocketMessage(BaseModel):
    type: str = Field(..., description="Message type: message, ping, pong")
    message: Optional[str] = Field(None)
    currentFiles: Optional[Dict[str, Any]] = Field(None)