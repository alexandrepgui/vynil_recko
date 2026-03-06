"""Discogs OAuth routes.

Provides endpoints for:
  GET  /api/auth/status   — check if user is authenticated
  GET  /api/auth/login    — initiate OAuth flow (returns authorize URL)
  GET  /api/auth/callback — handle Discogs redirect after user authorizes
  POST /api/auth/logout   — clear stored OAuth tokens
"""

import os

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse

from logger import get_logger
from services.discogs_auth import (
    clear_tokens,
    exchange_verifier,
    get_current_tokens,
    get_request_token,
    is_configured,
)

log = get_logger("routes.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
async def auth_status():
    """Return current authentication status."""
    tokens = get_current_tokens()
    return {
        "oauth_configured": is_configured(),
        "authenticated": tokens is not None,
        "username": tokens.username if tokens else None,
    }


@router.get("/login")
async def login(request: Request):
    """Initiate the OAuth flow. Returns the Discogs authorize URL."""
    if not is_configured():
        raise HTTPException(
            status_code=503,
            detail="Discogs OAuth not configured. Set DISCOGS_CONSUMER_KEY and DISCOGS_CONSUMER_SECRET in .env",
        )

    # In Docker, request.url_for() uses the container hostname (e.g. "backend")
    # which the browser can't resolve. Allow overriding via OAUTH_CALLBACK_URL.
    callback_url = os.getenv("OAUTH_CALLBACK_URL") or str(request.url_for("oauth_callback"))
    log.info("Starting OAuth flow with callback: %s", callback_url)

    try:
        _request_token, authorize_url = get_request_token(callback_url)
    except Exception as e:
        log.error("Failed to get request token: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to start OAuth flow: {e}")

    return {"authorize_url": authorize_url}


@router.get("/callback", name="oauth_callback")
async def oauth_callback(
    oauth_token: str = Query(...),
    oauth_verifier: str = Query(...),
):
    """Handle the callback from Discogs after user authorization.

    Exchanges the request token + verifier for a permanent access token,
    then returns an HTML page that closes itself / redirects to the app.
    """
    try:
        tokens = exchange_verifier(oauth_token, oauth_verifier)
    except ValueError as e:
        log.error("OAuth exchange failed (bad state): %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error("OAuth exchange failed: %s", e, exc_info=True)
        raise HTTPException(status_code=502, detail=f"Failed to complete OAuth: {e}")

    # Fetch the username now that we have valid tokens
    # Deferred import to avoid circular dependency: discogs → discogs_auth → discogs
    from services.discogs import get_identity

    try:
        tokens.username = get_identity()
    except Exception as e:
        log.warning("Got OAuth tokens but failed to fetch identity: %s", e)

    log.info("OAuth completed for user: %s", tokens.username)

    # Redirect back to the frontend app
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:5173")
    return RedirectResponse(url=frontend_url)


@router.post("/logout")
async def logout():
    """Clear stored OAuth tokens."""
    clear_tokens()
    return {"ok": True}
