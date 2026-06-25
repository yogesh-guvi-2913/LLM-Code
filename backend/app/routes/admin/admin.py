from fastapi import APIRouter
import logging
from app.routes.admin.model import *

logger = logging.getLogger(__name__)

router = APIRouter()

def initTestEndpoint(requestBody):
    logger.info(f"Received request for testEndpoint with body: {requestBody}")
    # Placeholder for the actual implementation
    # You can add your logic here to process the request and return the appropriate response
    return {"message": "testEndpoint endpoint is under construction", "receivedData": requestBody}

@router.post('/admin/testEndpoint')
def testEndpoint(requestBody: TestEndpointRequestModel):
    requestBody = requestBody.model_dump()
    return initTestEndpoint(requestBody)