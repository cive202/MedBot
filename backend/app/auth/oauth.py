from __future__ import annotations

from httpx_oauth.clients.google import GoogleOAuth2

from app.config import get_settings

settings = get_settings()


def get_google_client() -> GoogleOAuth2 | None:
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        return None
    return GoogleOAuth2(
        client_id=settings.google_oauth_client_id,
        client_secret=settings.google_oauth_client_secret,
    )
