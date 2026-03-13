import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import UPLOADS_DIR


def create_retry_session(user_agent: str | None = None) -> requests.Session:
    """Create a requests.Session with retry logic on 502/503/504."""
    session = requests.Session()
    session.mount(
        "https://",
        HTTPAdapter(max_retries=Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])),
    )
    if user_agent:
        session.headers["User-Agent"] = user_agent
    return session


def save_upload_image(item_id: str, filename: str, image_bytes: bytes, user_id: str = "") -> str:
    """Save an uploaded image to disk and return its URL path.

    Images are stored in per-user subdirectories under UPLOADS_DIR.
    """
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    if user_id:
        user_dir = UPLOADS_DIR / user_id
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / f"{item_id}{ext}").write_bytes(image_bytes)
        return f"/api/uploads/{user_id}/{item_id}{ext}"
    (UPLOADS_DIR / f"{item_id}{ext}").write_bytes(image_bytes)
    return f"/api/uploads/{item_id}{ext}"
