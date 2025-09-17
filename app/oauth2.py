from jose import jwt, JWTError
from fastapi import Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession # Utiliser la session asynchrone
from sqlalchemy.future import select # Utiliser select pour les requêtes asynchrones
from typing import Annotated

from datetime import datetime, timedelta

from app.config import settings
from app.postgres_connect import get_db_session
from app.models.user import User
from app.schemas.token import TokenData

oauth2_schema = OAuth2PasswordBearer(tokenUrl="auth/login")

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# Rendre la fonction de dépendance asynchrone
async def get_current_user(
    token: Annotated[str, Depends(oauth2_schema)],
    db: Annotated[AsyncSession, Depends(get_db_session)] # Utiliser la dépendance asynchrone
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )

    payload = verify_token(token)

    try:
        token_data = TokenData(**payload)
        
        # Exécuter la requête de manière asynchrone
        result = await db.execute(select(User).where(User.id == token_data.user_id))
        user = result.scalars().first()

        if user is None:
            raise credentials_exception
        return user
    except Exception:
        raise credentials_exception
    