"""Discogs OAuth routes (per-user).

Provides endpoints for:
  GET  /api/discogs/status   — check if authenticated user has linked Discogs
  GET  /api/discogs/login    — initiate OAuth flow (requires Supabase JWT)
  GET  /api/discogs/callback — handle Discogs redirect after user authorizes
  POST /api/discogs/logout   — remove stored Discogs OAuth tokens
"""

import os
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from auth import User, get_current_user
from deps import get_repo
from logger import get_logger
from repository.mongo import MongoRepository
from services.discogs_auth import (
    OAuthTokens,
    exchange_verifier,
    get_request_token,
    is_configured,
)

log = get_logger("routes.discogs_oauth")

# Hosts allowed for redirect URLs.  Extend with your production domain(s).
ALLOWED_REDIRECT_HOSTS: set[str] = {"localhost", "127.0.0.1"}

_DEFAULT_FRONTEND_URL = "http://localhost:5173"
_DEFAULT_CALLBACK_URL: str | None = None  # fall back to request.url_for()


def validate_redirect_url(
    url: str,
    allowed_hosts: set[str],
    allow_http: bool = False,
) -> bool:
    """Return True if *url* has an allowed scheme and hostname.

    - ``https`` is always accepted when the hostname is in *allowed_hosts*.
    - ``http`` is only accepted when *allow_http* is True (dev / localhost).
    """
    try:
        parsed = urlparse(url)
        allowed_schemes = {"https"} | ({"http"} if allow_http else set())
        return parsed.scheme in allowed_schemes and parsed.hostname in allowed_hosts
    except Exception:
        return False


router = APIRouter(prefix="/api/discogs", tags=["discogs"])


@router.get("/status")
async def discogs_status(
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Return whether the authenticated user has linked their Discogs account."""
    saved = repo.load_oauth_tokens(user.id)
    return {
        "oauth_configured": is_configured(),
        "authenticated": saved is not None,
        "username": saved.get("username") if saved else None,
    }


@router.get("/login")
async def discogs_login(
    request: Request,
    user: User = Depends(get_current_user),
):
    """Initiate the Discogs OAuth flow. Returns the authorize URL."""
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="Discogs OAuth not configured. Set DISCOGS_CONSUMER_KEY and DISCOGS_CONSUMER_SECRET in .env",
        )

    callback_url = os.getenv("OAUTH_CALLBACK_URL") or _DEFAULT_CALLBACK_URL
    if callback_url and not validate_redirect_url(callback_url, ALLOWED_REDIRECT_HOSTS, allow_http=True):
        log.warning("Invalid OAUTH_CALLBACK_URL ignored: %s", callback_url)
        callback_url = None
    # Fall back to auto-detected callback from the request
    if not callback_url:
        callback_url = str(request.url_for("discogs_callback"))
    log.info("Starting Discogs OAuth for user_id=%s callback=%s", user.id, callback_url)

    try:
        _request_token, authorize_url = get_request_token(user.id, callback_url)
    except Exception as e:
        log.error("Failed to get request token: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to start OAuth flow. Please try again.")

    return {"authorize_url": authorize_url}


@router.get("/callback", name="discogs_callback")
async def discogs_callback(
    oauth_token: str = Query(...),
    oauth_verifier: str = Query(...),
    repo: MongoRepository = Depends(get_repo),
):
    """Handle the callback from Discogs after user authorization.

    This endpoint is NOT authenticated via JWT (it's a browser redirect from Discogs).
    The user_id is recovered from the pending OAuth state.
    """
    try:
        tokens, user_id = exchange_verifier(oauth_token, oauth_verifier)
    except ValueError as e:
        log.error("OAuth exchange failed (bad state): %s", e)
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth token.")
    except Exception as e:
        log.error("OAuth exchange failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail="Failed to complete OAuth. Please try again.")

    # Fetch the username now that we have valid tokens
    from services.discogs import get_identity

    try:
        tokens.username = get_identity(tokens)
    except Exception as e:
        log.warning("Got OAuth tokens but failed to fetch identity: %s", e)

    repo.save_oauth_tokens(user_id, tokens.access_token, tokens.access_token_secret, tokens.username)
    log.info("Discogs OAuth completed for user_id=%s username=%s", user_id, tokens.username)

    # Redirect back to the frontend app
    frontend_url = os.getenv("FRONTEND_URL", _DEFAULT_FRONTEND_URL)
    if not validate_redirect_url(frontend_url, ALLOWED_REDIRECT_HOSTS, allow_http=True):
        log.warning("Invalid FRONTEND_URL ignored: %s", frontend_url)
        frontend_url = _DEFAULT_FRONTEND_URL
    return RedirectResponse(url=frontend_url)


@router.post("/logout")
async def discogs_logout(
    user: User = Depends(get_current_user),
    repo: MongoRepository = Depends(get_repo),
):
    """Remove the authenticated user's Discogs OAuth tokens."""
    repo.delete_oauth_tokens(user.id)
    return {"ok": True}
