"""Register templates with Flash orchestrator"""

import sys
import os
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../sandbox/sdk/python"))

from flash import Flash, Template

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def register_templates():
    """Register all custom templates with Flash"""
    
    flash_url = os.getenv("FLASH_BASE_URL", "http://127.0.0.1:8090")
    client = Flash(base_url=flash_url)
    
    templates = [
        Template(
            id="q1-express-api",
            image="q1-express-api:latest",
            title="Express API - CRUD REST API",
            language="javascript",
            description="Build a RESTful CRUD API using Express.js with in-memory storage",
            kind="api",
            dev_cmd="npm start",
            min_warm=2,
            vcpu=0.5,
            memory_mb=256,
            pids_limit=100,
        ),
        Template(
            id="q2-flask-api",
            image="q2-flask-api:latest",
            title="Flask API - CRUD REST API",
            language="python",
            description="Build a RESTful CRUD API using Flask with in-memory storage",
            kind="api",
            dev_cmd="python src/app.py",
            min_warm=2,
            vcpu=0.5,
            memory_mb=256,
            pids_limit=100,
        ),
        Template(
            id="q3-react-vite",
            image="q3-react-vite:latest",
            title="React + Vite - Todo App",
            language="javascript",
            description="Build a Todo application using React and Vite",
            kind="frontend",
            dev_cmd="npm run dev -- --host 0.0.0.0",
            min_warm=2,
            vcpu=0.5,
            memory_mb=512,
            pids_limit=100,
        ),
    ]
    
    for template in templates:
        try:
            logger.info(f"Registering template: {template.id}")
            result = client.templates.create(template)
            logger.info(f"Registered: {result.id} (warm pool: {result.warm})")
        except Exception as e:
            logger.error(f"Failed to register {template.id}: {e}")
    
    logger.info("\nRegistered templates:")
    for t in client.templates.list():
        logger.info(f"  - {t.id}: {t.title} (warm: {t.warm})")


if __name__ == "__main__":
    register_templates()