import subprocess
import logging
from pathlib import Path
import os

logger = logging.getLogger(__name__)

NGINX_SESSIONS_DIR = Path(os.getenv("NGINX_SESSIONS_DIR", "/etc/nginx/sessions"))
NGINX_CONTAINER_NAME = os.getenv("NGINX_CONTAINER_NAME", "nginx_container")

SESSION_LOCATION_TEMPLATE = """
# Auto-generated for session: {session_id}
location /session/{session_id}/ {{
    resolver 127.0.0.11 valid=30s;
    set $frontend_{var_name} "{frontend_host}";
    proxy_pass http://$frontend_{var_name}:{frontend_port};
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 86400;
}}

location ~ ^/session/{session_id_regex}/api/(.*)$ {{
    resolver 127.0.0.11 valid=30s;
    set $backend_{var_name} "{backend_host}";
    proxy_pass http://$backend_{var_name}:{backend_port}/$1$is_args$args;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}}
"""


def create_session_config(
    session_id: str,
    frontend_host: str | None = None,
    frontend_port: int = 5173,
    backend_host: str | None = None,
    backend_port: int = 7000,
) -> bool:
    NGINX_SESSIONS_DIR.mkdir(parents=True, exist_ok=True)

    if frontend_host is None:
        frontend_host = f"{session_id}-frontend-1"
    if backend_host is None:
        backend_host = f"{session_id}-backend-1"
    
    var_name = session_id.replace("-", "_").replace(".", "_")
    session_id_regex = session_id.replace("-", r"\-")

    config_content = SESSION_LOCATION_TEMPLATE.format(
        session_id=session_id,
        session_id_regex=session_id_regex,
        frontend_host=frontend_host,
        frontend_port=frontend_port,
        backend_host=backend_host,
        backend_port=backend_port,
        var_name=var_name,
    )

    config_file = NGINX_SESSIONS_DIR / f"{session_id}.conf"
    config_file.write_text(config_content)
    logger.info(f"Created Nginx config for session: {session_id}")

    return reload_nginx()


def remove_session_config(session_id: str) -> bool:
    config_file = NGINX_SESSIONS_DIR / f"{session_id}.conf"

    if config_file.exists():
        config_file.unlink()
        logger.info(f"Removed Nginx config for session: {session_id}")
        return reload_nginx()

    return True


def reload_nginx() -> bool:
    try:
        result = subprocess.run(
            ["docker", "exec", NGINX_CONTAINER_NAME, "nginx", "-s", "reload"],
            capture_output=True,
            timeout=10
        )
        if result.returncode == 0:
            logger.info("Nginx reloaded successfully via docker exec")
            return True
        else:
            stderr = result.stderr.decode() if result.stderr else "unknown error"
            if "is restarting" in stderr or "not running" in stderr:
                logger.warning("Nginx container is restarting/not running, attempting restart")
                restart_result = subprocess.run(
                    ["docker", "restart", NGINX_CONTAINER_NAME],
                    capture_output=True,
                    timeout=30
                )
                if restart_result.returncode == 0:
                    logger.info("Nginx container restarted successfully")
                    return True
                logger.error(f"Failed to restart nginx: {restart_result.stderr.decode()}")
                return False
            logger.error(f"Failed to reload Nginx: {stderr}")
            return False
    except subprocess.TimeoutExpired:
        logger.error("Nginx reload timed out")
        return False
    except Exception as e:
        logger.error(f"Failed to reload Nginx: {e}")
        return False
