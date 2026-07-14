from pydantic import BaseModel
from typing import Optional, List

class TestEndpointRequestModel(BaseModel):
    authToken: str
    testParams: Optional[dict]

class TestMapperRequestModel(BaseModel):
    authToken: str
    testId: str
    userHashes: List[str]

class RemoveTestMapperRequestModel(BaseModel):
    authToken: str
    testId: str
    userHash: str