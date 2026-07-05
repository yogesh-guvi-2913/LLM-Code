from pydantic import BaseModel
from typing import Optional, List


class TestEndpointRequestModel(BaseModel):
    authToken: str
    testParams: Optional[dict] = None


class TestMapperAssignRequest(BaseModel):
    authToken: str
    hash: str
    testId: str


class TestMapperRemoveRequest(BaseModel):
    authToken: str
    hash: str
    testId: str


class TestMapperListRequest(BaseModel):
    authToken: str
    hash: Optional[str] = None
    testId: Optional[str] = None