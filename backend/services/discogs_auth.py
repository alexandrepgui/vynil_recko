"""Discogs OAuth 1.0a authentication service.

Handles the three-legged OAuth flow:
  1. Get request token → redirect user to Discogs authorize URL
  2. User authorizes → Discogs redirects back with verifier
  3. Exchange verifier for access token

Uses PLAINTEXT signature method (Discogs default, safe over HTTPS).
"""

import os
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs

import requests

from config import DISCOGS_BASE_URL, DISCOGS_USER_AGENT
from logger import get_logger

log = get_logger("services.discogs_auth")

REQUEST_TOKEN_URL = f"{DISCOGS_BASE_URL}/oauth/request_token"
AUTHORIZE_URL = "https://www.discogs.com/oauth/authorize"
ACCESS_TOKEN_URL = f"{DISCOGS_BASE_URL}/oauth/access_token"

_PENDING_TTL = 600  # seconds — purge unfinished OAuth flows after 10 minutes


@dataclass
class OAuthTokens:
    access_token: str
    access_token_secret: str
    username: str | None = None


@dataclass
class PendingOAuth:
    """Temporary state held between request-token and access-token steps."""
    request_token: str
    request_token_secret: str
    created_at: float = field(default_factory=time.time)


# In-memory store. Single-user app, so one slot is sufficient.
_pending: dict[str, PendingOAuth] = {}  # keyed by request_token
_current_tokens: OAuthTokens | None = None


def _consumer_key() -> str:
    return os.getenv("DISCOGS_CONSUMER_KEY", "")


def _consumer_secret() -> str:
    return os.getenv("DISCOGS_CONSUMER_SECRET", "")


def _plaintext_signature(consumer_secret: str, token_secret: str = "") -> str:
    """PLAINTEXT signature = consumer_secret&token_secret (RFC 5849 §3.4.4)."""
    return f"{consumer_secret}&{token_secret}"


def _build_auth_params(token_secret: str = "", **extra: str) -> dict:
    """Common OAuth params shared by all OAuth calls."""
    return {
        "oauth_consumer_key": _consumer_key(),
        "oauth_nonce": secrets.token_hex(16),
        "oauth_signature": _plaintext_signature(_consumer_secret(), token_secret),
        "oauth_signature_method": "PLAINTEXT",
        "oauth_timestamp": str(int(time.time())),
        **extra,
    }


def _oauth_header(params: dict) -> str:
    """Build an OAuth Authorization header string."""
    pairs = ", ".join(f'{k}="{v}"' for k, v in sorted(params.items()))
    return f"OAuth {pairs}"


def _parse_form_body(text: str) -> dict[str, str]:
    """Parse an x-www-form-urlencoded response body into a flat dict."""
    parsed = parse_qs(text, strict_parsing=True)
    return {k: v[0] for k, v in parsed.items()}


def _purge_stale_pending() -> None:
    """Remove pending OAuth entries older than _PENDING_TTL."""
    now = time.time()
    stale = [k for k, v in _pending.items() if now - v.created_at > _PENDING_TTL]
    for k in stale:
        del _pending[k]


def is_configured() -> bool:
    """Return True if consumer credentials are set in the environment."""
    return bool(_consumer_key() and _consumer_secret())


def get_current_tokens() -> OAuthTokens | None:
    """Return the stored OAuth access tokens, if available."""
    return _current_tokens


def set_tokens(tokens: OAuthTokens) -> None:
    """Restore OAuth tokens (e.g. from database on startup)."""
    global _current_tokens
    _current_tokens = tokens
    log.info("OAuth tokens restored for user=%s", tokens.username)


def clear_tokens() -> None:
    """Clear stored OAuth tokens (logout)."""
    global _current_tokens
    _current_tokens = None
    log.info("OAuth tokens cleared")


def get_request_token(callback_url: str) -> tuple[str, str]:
    """Step 1: Obtain a request token and return (request_token, authorize_url).

    Args:
        callback_url: The URL Discogs will redirect to after authorization.

    Returns:
        Tuple of (request_token, full_authorize_url).
    """
    _purge_stale_pending()

    auth_params = _build_auth_params(oauth_callback=callback_url)

    resp = requests.get(
        REQUEST_TOKEN_URL,
        headers={
            "User-Agent": DISCOGS_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": _oauth_header(auth_params),
        },
    )
    resp.raise_for_status()

    body = _parse_form_body(resp.text)
    request_token = body["oauth_token"]
    request_token_secret = body["oauth_token_secret"]

    _pending[request_token] = PendingOAuth(
        request_token=request_token,
        request_token_secret=request_token_secret,
    )

    authorize_url = f"{AUTHORIZE_URL}?oauth_token={request_token}"
    log.info("Request token obtained, authorize URL: %s", authorize_url)
    return request_token, authorize_url


def exchange_verifier(oauth_token: str, oauth_verifier: str) -> OAuthTokens:
    """Step 3: Exchange the request token + verifier for an access token.

    Args:
        oauth_token: The request token returned by Discogs in the callback.
        oauth_verifier: The verifier code from the callback.

    Returns:
        OAuthTokens with the permanent access token and secret.
    """
    global _current_tokens

    pending = _pending.pop(oauth_token, None)
    if not pending:
        raise ValueError(f"No pending OAuth flow found for token {oauth_token!r}")

    auth_params = _build_auth_params(
        token_secret=pending.request_token_secret,
        oauth_token=oauth_token,
        oauth_verifier=oauth_verifier,
    )

    resp = requests.post(
        ACCESS_TOKEN_URL,
        headers={
            "User-Agent": DISCOGS_USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": _oauth_header(auth_params),
        },
    )
    resp.raise_for_status()

    body = _parse_form_body(resp.text)
    tokens = OAuthTokens(
        access_token=body["oauth_token"],
        access_token_secret=body["oauth_token_secret"],
    )

    _current_tokens = tokens
    log.info("OAuth access token obtained successfully")
    return tokens


def build_oauth_headers(tokens: OAuthTokens) -> dict:
    """Build request headers for an authenticated API call using OAuth tokens."""
    auth_params = _build_auth_params(
        token_secret=tokens.access_token_secret,
        oauth_token=tokens.access_token,
    )
    return {
        "User-Agent": DISCOGS_USER_AGENT,
        "Authorization": _oauth_header(auth_params),
    }
