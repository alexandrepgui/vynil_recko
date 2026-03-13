"""User profile routes.

Provides:
  GET  /api/me          — return authenticated user's profile info + Discogs status
  GET  /api/me/settings — return current user settings
  PUT  /api/me/settings — update user settings
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from auth import User, get_current_user
from config import DEFAULT_USER_SETTINGS
from deps import get_repo
from repository.mongo import MongoRepository
from services.discogs_auth import is_configured

router = APIRouter(prefix="/api/me", tags=["profile"])


@router.get("")
async def get_profile(
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Return the authenticated user's profile and Discogs connection status."""
    # Keep avatar_url in user_settings so the public collection endpoint can use it
    if user.avatar_url:
        repo.update_user_settings(user.id, {"avatar_url": user.avatar_url})
    saved = repo.load_oauth_tokens(user.id)
    return {
        "user_id": user.id,
        "email": user.email,
        "name": user.name,
        "avatar_url": user.avatar_url,
        "discogs": {
            "oauth_configured": is_configured(),
            "connected": saved is not None,
            "username": saved.get("username") if saved else None,
        },
    }


@router.get("/settings")
async def get_settings(
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Return the authenticated user's settings."""
    return repo.get_user_settings(user.id)


class UpdateSettingsRequest(BaseModel):
    collection_public: bool | None = None
    dark_mode: bool | None = None


@router.put("/settings")
async def update_settings(
    body: UpdateSettingsRequest,
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Update the authenticated user's settings."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        return repo.get_user_settings(user.id)
    repo.update_user_settings(user.id, updates)
    # Merge updates into defaults to avoid an extra DB round-trip
    return {**DEFAULT_USER_SETTINGS, **updates}
