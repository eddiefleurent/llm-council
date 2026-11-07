"""API access controls: CORS allowlist, bearer-token auth, and request limits."""

import logging
import os
import secrets
import urllib.parse
from pathlib import Path

from fastapi import HTTPException, Request

logger = logging.getLogger(__name__)

API_TOKEN_ENV = "LLM_COUNCIL_API_TOKEN"
CORS_ORIGINS_ENV = "LLM_COUNCIL_CORS_ORIGINS"
API_TOKEN_FILE = "data/api_token"
API_URL_FILE = "data/api_url"
DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
MAX_COUNCIL_MODELS = 12

_generated_token: str | None = None


def get_cors_origins() -> list[str]:
    """Return the browser origins allowed to call the API."""
    raw = os.getenv(CORS_ORIGINS_ENV, "")
    origins = [origin.strip().rstrip("/") for origin in raw.split(",")]
    origins = [origin for origin in origins if origin]
    if "*" in origins:
        raise RuntimeError(
            f"{CORS_ORIGINS_ENV} must list explicit origins; '*' is not allowed."
        )
    return origins or list(DEFAULT_CORS_ORIGINS)


def _load_or_create_token_file() -> str:
    path = Path(API_TOKEN_FILE)
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if token:
            try:
                os.chmod(path, 0o600)
            except OSError as e:
                logger.warning(f"Could not restrict permissions on {path}: {e}")
            return token
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(token + "\n")
    return token


def get_api_token() -> str:
    """Return the API token from the environment, or a persisted generated one."""
    global _generated_token
    env_token = os.getenv(API_TOKEN_ENV, "").strip()
    if env_token:
        return env_token
    if _generated_token is None:
        _generated_token = _load_or_create_token_file()
    return _generated_token


async def require_api_token(request: Request) -> None:
    """Reject /api requests that do not carry the configured bearer token."""
    if not request.url.path.startswith("/api"):
        return
    scheme, _, credentials = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(
        credentials.strip().encode(), get_api_token().encode()
    ):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def write_login_link(frontend_origin: str) -> str:
    """Persist the one-click UI login link (token included) next to the token."""
    path = Path(API_URL_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    token = urllib.parse.quote(get_api_token(), safe="")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(f"{frontend_origin}/?token={token}\n")
    try:
        os.chmod(path, 0o600)
    except OSError as e:
        logger.warning(f"Could not restrict permissions on {path}: {e}")
    return str(path)
