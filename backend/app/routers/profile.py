from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.deps import current_active_user
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/me", response_model=UserRead)
async def get_me(user: User = Depends(current_active_user)) -> User:
    return user


@router.patch("/me", response_model=UserRead)
async def patch_me(
    payload: UserUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> User:
    data = payload.model_dump(exclude_unset=True, exclude={"password", "email", "is_active", "is_superuser", "is_verified"})
    for k, v in data.items():
        # Pydantic objects (LocationIn, HistoryIn) need to be plain dicts for the JSON column.
        if hasattr(v, "model_dump"):
            v = v.model_dump()
        setattr(user, k, v)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user
