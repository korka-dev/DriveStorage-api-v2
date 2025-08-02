from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from sqlalchemy.orm import Session
from app.schemas.user import UserCreate, UserOut, VerifyCodeRequest, ResetPasswordRequest
from app.models.user import User
from app.utils import generate_otp, send_email, hashed, send_forgot_password_email
from app.postgres_connect import get_db

router = APIRouter(prefix="/users", tags=["Users"])


otp_store = {}

@router.post("/create", response_model=UserOut)
async def register_user(user: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                            detail="Email déjà utilisé")

    hashed_pw = hashed(user.password)
    new_user = User(name=user.name, email=user.email, password=hashed_pw)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    otp = generate_otp()
    otp_store[str(new_user.email)] = otp  
    await send_email(new_user.email, otp)

    return new_user

@router.post("/verify/{email}", response_model=UserOut)
def verify_user(request: VerifyCodeRequest, email: str, db: Session = Depends(get_db)):
    otp_expected = otp_store.get(email)
    if not otp_expected or request.code != otp_expected:
        raise HTTPException(status_code= status.HTTP_400_BAD_REQUEST, 
                            detail="Code OTP invalide ou expiré")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    user.is_active = True
    db.commit()
    return user

@router.post("/forgot-password")
async def forgot_password(email: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, 
                            detail="Utilisateur introuvable")

    otp = generate_otp()
    otp_store[str(user.email)] = otp
    await send_forgot_password_email(user.email, otp)

    return {"message": "Code OTP envoyé par email"}


@router.post("/reset-password")
def reset_password(data: ResetPasswordRequest, email: str, db: Session = Depends(get_db)):
    otp_expected = otp_store.get(email)
    if not otp_expected or data.code != otp_expected:
        raise HTTPException(status_code=400, detail="Code invalide")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    user.password = hashed(data.new_password)
    db.commit()
    return {"message": "Mot de passe réinitialisé avec succès"}



@router.get("/all", response_model=List[UserOut])
def get_all_users(db: Session = Depends(get_db)):
    users = db.query(User).all()
    return users
