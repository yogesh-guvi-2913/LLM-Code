"""Official Python SDK for the Flash sandbox engine.

Quick start::

    from flash import Flash

    client = Flash()  # FLASH_API_KEY / FLASH_BASE_URL from env
    with client.sandboxes.create(template="q1") as sbx:
        res = sbx.run("node -e 'console.log(40+2)'")
        print(res.stdout)  # "42\\n"
"""

from .client import (
    APIError,
    APIKey,
    CreatedAPIKey,
    ExecResult,
    Flash,
    Sandbox,
    Session,
    Submission,
    Template,
)

__all__ = [
    "Flash",
    "Sandbox",
    "ExecResult",
    "Template",
    "APIKey",
    "CreatedAPIKey",
    "Session",
    "Submission",
    "APIError",
]

__version__ = "0.1.0"
