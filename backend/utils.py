import os

from config import UPLOADS_DIR


def save_upload_image(item_id: str, filename: str, image_bytes: bytes) -> str:
    """Save an uploaded image to disk and return its URL path."""
    ext = os.path.splitext(filename)[1].lower() or ".jpg"
    (UPLOADS_DIR / f"{item_id}{ext}").write_bytes(image_bytes)
    return f"/api/uploads/{item_id}{ext}"
