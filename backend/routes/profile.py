"""User profile routes.

Provides:
  GET /api/me — return authenticated user's profile info + Discogs status
"""

from fastapi import APIRouter, Depends

from auth import User, get_current_user
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
