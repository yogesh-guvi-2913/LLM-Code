import logging
import json
import re
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Set
import os

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path(os.getenv("SESSIONS_DIR", "/sessions"))

NPM_IMPORT_REGEX = re.compile(
    r'''import\s+(?:[^'"]+\s+from\s+)?['"]([^'"]+)['"]'''
)

BUILT_IN_MODULES = {
    'react', 'react-dom', 'react-dom/client',
    'fs', 'path', 'os', 'crypto', 'http', 'https', 'url', 'util',
    'stream', 'events', 'buffer', 'process', 'child_process',
    'assert', 'constants', 'domain', 'net', 'querystring', 'readline',
    'repl', 'tls', 'tty', 'v8', 'vm', 'zlib', 'worker_threads',
    'console', 'setTimeout', 'setInterval', 'setImmediate',
    'clearTimeout', 'clearInterval', 'clearImmediate',
    'module', 'require', 'exports', 'global', '__dirname', '__filename',
}

LOCAL_IMPORT_PREFIXES = ('./', '../', '@/', '~/', '#')

def extract_npm_imports(content: str) -> Set[str]:
    imports = set()
    for match in NPM_IMPORT_REGEX.findall(content):
        pkg = match.split('/')[0] if '/' in match and not match.startswith('@') else match
        pkg = pkg.split('/')[0] if '/' in pkg else pkg
        if pkg in BUILT_IN_MODULES or pkg.startswith(LOCAL_IMPORT_PREFIXES):
            continue
        if not pkg or pkg in ('.', '..', '..'):
            continue
        if not re.match(r'^[@a-zA-Z][a-zA-Z0-9._-]*$', pkg):
            continue
        imports.add(pkg)
    return imports

def get_container_name(session_id: str) -> str | None:
    try:
        result = subprocess.run(
            ["docker-compose", "-p", session_id, "ps", "--format", "{{.Name}}"],
            cwd=str(SESSIONS_DIR / session_id),
            capture_output=True,
            text=True,
            timeout=15
        )
        names = [n.strip() for n in result.stdout.strip().split('\n') if n.strip()]
        for name in names:
            if "frontend" in name:
                return name
        return names[0] if names else None
    except Exception:
        return None

def get_container_node_modules(session_id: str) -> Set[str]:
    container = get_container_name(session_id)
    if not container:
        return set()
    try:
        result = subprocess.run(
            ["docker", "exec", container, "ls", "1>/dev/null", "/app/node_modules"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            return set()
        result = subprocess.run(
            ["docker", "exec", container, "ls", "/app/node_modules"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return set(line.strip() for line in result.stdout.split('\n') if line.strip())
    except Exception:
        return set()

def update_package_json(session_dir: Path, packages: Set[str]) -> None:
    package_json = session_dir / "frontend" / "package.json"
    if not package_json.exists():
        package_json = session_dir / "package.json"

    if not package_json.exists():
        return

    valid_packages = set()
    for pkg in packages:
        if pkg and pkg not in ('.', '..', '..') and re.match(r'^[@a-zA-Z][a-zA-Z0-9._-]*$', pkg):
            valid_packages.add(pkg)

    if not valid_packages:
        return

    try:
        data = json.loads(package_json.read_text())
        deps = data.setdefault("dependencies", {})
        for pkg in sorted(valid_packages):
            if pkg not in deps:
                deps[pkg] = "latest"
        package_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Updated package.json with: {', '.join(sorted(valid_packages))}")
    except Exception as e:
        logger.warning(f"Could not update package.json: {e}")

async def install_missing_packages(session_id: str, packages: Set[str], session_dir: Path = None) -> bool:
    if not packages:
        return True

    if session_dir is None:
        session_dir = SESSIONS_DIR / session_id

    update_package_json(session_dir, packages)

    container = get_container_name(session_id)
    if not container:
        logger.warning(f"No container found for session {session_id}")
        return False

    pkg_list = " ".join(sorted(packages))
    logger.info(f"Running npm install in {container} for: {pkg_list}")

    try:
        result = subprocess.run(
            ["docker", "exec", container, "npm", "install", "--silent"],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            logger.info(f"npm install completed successfully")

            # Clear Vite's dependency optimization cache so it re-resolves new packages
            try:
                subprocess.run(
                    ["docker", "exec", container, "rm", "-rf", "/app/node_modules/.vite"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                logger.info("Cleared Vite dependency cache")

                # Force Vite to re-optimize by touching the newly installed package
                subprocess.run(
                    ["docker", "exec", container, "npx", "vite", "optimize"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                logger.info("Vite re-optimized dependencies")
            except Exception as e:
                logger.warning(f"Could not clear Vite cache: {e}")

            return True
        else:
            logger.warning(f"npm install failed: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.warning(f"npm install timed out")
        return False
    except Exception as e:
        logger.error(f"Error installing packages: {e}")
        return False

def scan_frontend_files(session_dir: Path) -> Set[str]:
    frontend_dir = session_dir / "frontend"
    if not frontend_dir.exists():
        frontend_dir = session_dir

    all_imports = set()
    extensions = {'.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs'}

    for ext in extensions:
        for filepath in frontend_dir.rglob(f"*{ext}"):
            if ".git" in filepath.parts or "node_modules" in filepath.parts:
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
                all_imports.update(extract_npm_imports(content))
            except Exception:
                pass

    return all_imports

def extract_new_imports(changes: List[Dict[str, Any]]) -> Set[str]:
    new_imports = set()
    for change in changes:
        if change.get("action") == "delete":
            continue
        path = change.get("path", "")
        content = change.get("content", "")
        if not content:
            continue
        if any(path.endswith(ext) for ext in ['.js', '.jsx', '.ts', '.tsx', '.mjs', '.cjs']):
            new_imports.update(extract_npm_imports(content))
    return new_imports

async def sync_files_to_session(session_id: str, changes: List[Dict[str, Any]]) -> bool:
    session_dir = SESSIONS_DIR / session_id

    if not session_dir.exists():
        logger.error(f"Session directory not found: {session_id}")
        return False

    new_imports = extract_new_imports(changes)

    if new_imports:
        container_modules = get_container_node_modules(session_id)
        missing = new_imports - container_modules

        if missing:
            logger.info(f"Packages missing from container node_modules: {missing}")
            logger.info(f"Pre-installing before file sync...")
            await install_missing_packages(session_id, missing, session_dir)

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