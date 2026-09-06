from fastapi_users.authentication import AuthenticationBackend, CookieTransport, JWTStrategy

from app.config import get_settings

settings = get_settings()

cookie_transport = CookieTransport(
    cookie_name="health_chatbot_auth",
    cookie_max_age=settings.jwt_lifetime_seconds,
    cookie_secure=settings.cookie_secure,
    cookie_httponly=True,
    cookie_samesite=settings.cookie_samesite,  # type: ignore[arg-type]
)


def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(
        secret=settings.secret_key,
        lifetime_seconds=settings.jwt_lifetime_seconds,
    )


auth_backend = AuthenticationBackend(
    name="cookie-jwt",
    transport=cookie_transport,
    get_strategy=get_jwt_strategy,
)
