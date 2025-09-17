from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from app.schemas.user import UserOut

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

class TokenData(BaseModel):
    user_id: Optional[str] = None
    exp: Optional[float] = None

class TokenExpires(BaseModel):
    expires_in: int

class UserToken(BaseModel):
    user: UserOut
    token: TokenExpires


