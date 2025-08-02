
from pydantic import BaseModel


from app.schemas.user import UserOut


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id:  str|None=None
    exp:float|None=None


    
class TokenRequest(BaseModel):
    token: str

class TokenExpires(BaseModel):
    expires_in: int
    

class UserToken(BaseModel):
    user:UserOut
    token: TokenExpires



