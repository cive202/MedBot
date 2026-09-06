from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from fastapi_users import BaseUserManager, FastAPIUsers, UUIDIDMixin
from fastapi_users.db import SQLAlchemyUserDatabase
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.strategy import auth_backend
from app.config import get_settings
from app.db import get_session
from app.models.user import OAuthAccount, User
from app.schemas.user import UserCreate

settings = get_settings()


async def get_user_db(
    session: AsyncSession = Depends(get_session),
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
    reset_password_token_secret = settings.secret_key
    verification_token_secret = settings.secret_key

    async def create(
        self,
        user_create: UserCreate,
        safe: bool = False,
        request: Request | None = None,
    ) -> User:
        # Pre-check the username uniqueness so we return 409 instead of a
        # generic IntegrityError on the underlying UNIQUE index.
        username = getattr(user_create, "username", None)
        if username:
            session: AsyncSession = self.user_db.session  # type: ignore[assignment]
            existing = await session.execute(
                select(User).where(User.username == username)
            )
            if existing.scalar_one_or_none() is not None:
                raise HTTPException(
                    status_code=409,
                    detail="That username is already taken.",
                )
        return await super().create(user_create, safe, request)

    async def on_after_register(self, user: User, request: Request | None = None) -> None:
        # Hook point: send welcome email, audit log, etc. Stubbed.
        pass

    async def on_after_forgot_password(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        pass

    async def on_after_request_verify(
        self, user: User, token: str, request: Request | None = None
    ) -> None:
        pass


async def get_user_manager(
    user_db: SQLAlchemyUserDatabase = Depends(get_user_db),
) -> AsyncGenerator[UserManager, None]:
    yield UserManager(user_db)


fastapi_users = FastAPIUsers[User, uuid.UUID](get_user_manager, [auth_backend])

current_active_user = fastapi_users.current_user(active=True)
current_optional_user = fastapi_users.current_user(active=True, optional=True)
