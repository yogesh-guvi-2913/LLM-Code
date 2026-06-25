import hashlib
import re
import logging

logger = logging.getLogger(__name__)

def validate_email(email: str) -> bool:
    """Validate email format using regex"""
    email_regex = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    return re.match(email_regex, email) is not None

def validate_password(password: str) -> tuple[bool, str]:
    """
    Validate password requirements:
    - At least 5 characters long
    - At least one uppercase letter
    - At least one special character
    - At least one number
    Returns (is_valid, error_message)
    """
    if len(password) < 5:
        return False, "Password must be at least 5 characters long"

    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"

    if not re.search(r'[!@#$%^&*()_+\-=\[\]{};:\'"\\|,.<>\/?]', password):
        return False, "Password must contain at least one special character"

    if not re.search(r'[0-9]', password):
        return False, "Password must contain at least one number"

    return True, ""

def sha512_hash(text: str) -> str:
    """Convert text to SHA512 hash"""
    return hashlib.sha512(text.encode('utf-8')).hexdigest()

def hash_password(password: str) -> str:
    """Hash password using SHA512"""
    return sha512_hash(password)