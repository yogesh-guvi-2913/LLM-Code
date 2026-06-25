from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging
# from app.utils.middleware import AuthenticationMiddleware
from app.setup.postgres import initPostgreSQLSchema
from app.setup.logging import initLogging

from app.routes.admin.admin import router as admin

initLogging()
logger = logging.getLogger(__name__)

# Lifespan is used to manage startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    
    # Initialize setup tasks
    initPostgreSQLSchema()

    yield
    # For cleaning up the loaded process after the application closes
    logger.info("Stopping application...")

app = FastAPI(lifespan=lifespan)

# app.add_middleware(AuthenticationMiddleware)

origins = ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

## This below is for including all routes
app.include_router(admin)