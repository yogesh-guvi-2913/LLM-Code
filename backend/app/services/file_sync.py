import logging
from pathlib import Path
from typing import List, Dict, Any
import os

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(os.getenv("SESSIONS_DIR", "/sessions"))


async def sync_files_to_session(session_id: str, changes: List[Dict[str, Any]]) -> bool:
    session_dir = SESSIONS_DIR / session_id

    if not session_dir.exists():
        logger.error(f"Session directory not found: {session_id}")
        return False

    synced = 0
    for change in changes:
        path = change.get("path", "")
        content = change.get("content", "")
        action = change.get("action", "update")

        if not path:
            continue

        if path.startswith("/"):
            path = path.lstrip("/")

        full_path = session_dir / path

        if action == "delete":
            if full_path.exists():
                try:
                    full_path.unlink()
                    logger.info(f"Deleted file: {full_path}")
                    synced += 1
                except Exception as e:
                    logger.warning(f"Could not delete {full_path}: {e}")
        else:
            try:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(content, encoding="utf-8")
                logger.info(f"Wrote file: {full_path}")
                synced += 1
            except Exception as e:
                logger.error(f"Could not write {full_path}: {e}")

    logger.info(f"Synced {synced} files to session {session_id}")
    return synced > 0


def get_session_file(session_id: str, file_path: str) -> str | None:
    session_dir = SESSIONS_DIR / session_id
    if file_path.startswith("/"):
        file_path = file_path.lstrip("/")

    full_path = session_dir / file_path
    if full_path.exists() and full_path.is_file():
        try:
            return full_path.read_text(encoding="utf-8")
        except Exception:
            return None
    return None
