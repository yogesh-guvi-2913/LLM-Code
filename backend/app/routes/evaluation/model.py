from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum


class SubmissionStatus(str, Enum):
    pending = "pending"
    evaluating = "evaluating"
    completed = "completed"
    failed = "failed"


class SubmitTestRequest(BaseModel):
    authToken: str = Field(..., description="User auth token")
    testId: str = Field(..., description="Test ID")
    answers: Dict[str, Any] = Field(default_factory=dict)
    files: Dict[str, Any] = Field(default_factory=dict, description="Final file state")
    chatHistory: List[Dict[str, str]] = Field(
        default_factory=list, description="Chat messages [{role, content}]"
    )


class CategoryScore(BaseModel):
    name: str
    score: float = Field(..., ge=0, le=10)
    maxScore: float = Field(default=10)
    feedback: str = ""


class EvaluationResult(BaseModel):
    overallScore: float = Field(..., ge=0, le=10)
    categories: List[CategoryScore] = Field(default_factory=list)
    summary: str = ""
    strengths: List[str] = Field(default_factory=list)
    improvements: List[str] = Field(default_factory=list)
    requirementBreakdown: List[Dict[str, Any]] = Field(default_factory=list)


class SubmissionResponse(BaseModel):
    success: bool
    submissionId: Optional[str] = None
    status: SubmissionStatus = SubmissionStatus.pending
    message: str = ""


class ResultsResponse(BaseModel):
    success: bool
    status: SubmissionStatus = SubmissionStatus.pending
    testId: str = ""
    testName: str = ""
    evaluation: Optional[EvaluationResult] = None
    screenshot: Optional[str] = Field(
        None, description="Base64 encoded desktop screenshot"
    )
    screenshotMobile: Optional[str] = Field(
        None, description="Base64 encoded mobile screenshot"
    )
    consoleErrors: List[str] = Field(default_factory=list)
    runtimeError: Optional[str] = None
    files: Optional[Dict[str, Any]] = None
    promptCount: int = 0
    message: str = ""
