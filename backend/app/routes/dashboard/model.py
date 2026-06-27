from pydantic import BaseModel, Field

class DashboardRequestModel(BaseModel):
    authToken: str = Field(..., description="Authentication token to invalidate")