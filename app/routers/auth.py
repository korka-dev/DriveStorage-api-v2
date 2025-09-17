from typing import Annotated

from fastapi import APIRouter, Depends, status, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app import oauth2, utils
from app.postgres_connect import get_db_session
from app.models.user import User
from app.schemas.token import Token


router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Token)
async def login_for_access_token(
    user_credentials: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db_session)]
):
    result = await db.execute(select(User).filter_by(email=user_credentials.username))
    user = result.scalars().first()

    if user is None or not utils.verify(user_credentials.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Credentials"
        )

    access_token = oauth2.create_access_token(
        data={"user_id": str(user.id), "user_name": user.name}
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user_name": user.name
    }
    