from fastapi import APIRouter

from app.auth.oauth import get_google_client
from app.auth.strategy import auth_backend
from app.auth.users import fastapi_users
from app.config import get_settings
from app.schemas.user import UserCreate, UserRead, UserUpdate

settings = get_settings()
router = APIRouter()

router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)

# Optional Google OAuth — only mounted when credentials are configured.
_google = get_google_client()
if _google is not None:
    router.include_router(
        fastapi_users.get_oauth_router(
            _google,
            auth_backend,
            settings.secret_key,
            associate_by_email=True,
            is_verified_by_default=True,
        ),
        prefix="/auth/google",
        tags=["auth"],
    )
    router.include_router(
        fastapi_users.get_oauth_associate_router(_google, UserRead, settings.secret_key),
        prefix="/auth/google/associate",
        tags=["auth"],
    )

