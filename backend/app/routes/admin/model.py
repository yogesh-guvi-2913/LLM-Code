from pydantic import BaseModel
from typing import Optional, List, Literal

class TestEndpointRequestModel(BaseModel):
    authToken: str
    testParams: Optional[dict]