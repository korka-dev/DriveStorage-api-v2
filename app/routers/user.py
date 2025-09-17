from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.schemas.user import UserCreate, UserOut, VerifyCodeRequest, ResetPasswordRequest
from app.models.user import User
from app.models.user import StorageUsage, Plan, Subscription, PlanType, SubscriptionStatus
from app.utils import generate_otp, send_email, hashed, send_forgot_password_email
from app.postgres_connect import get_db_session
from datetime import datetime

router = APIRouter(prefix="/users", tags=["Users"])

otp_store = {}

@router.post("/create", response_model=UserOut)
async def register_user(user: UserCreate, background_tasks: BackgroundTasks,
                        db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(User).where(User.email == user.email))
    existing_user = result.scalar_one_or_none()
    
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email déjà utilisé")

    hashed_pw = hashed(user.password)
    new_user = User(name=user.name, email=user.email, password=hashed_pw)
    db.add(new_user)
    
    await db.commit() 
    await db.refresh(new_user)

    storage_usage = StorageUsage(user_id=new_user.id, used_storage_mb=0.0)
    db.add(storage_usage)
    
    free_plan_result = await db.execute(
        select(Plan).where(Plan.plan_type == PlanType.FREE)
    )
    free_plan = free_plan_result.scalar_one_or_none()
    
    if free_plan:
        free_subscription = Subscription(
            user_id=new_user.id,
            plan_id=free_plan.id,
            status=SubscriptionStatus.ACTIVE,
            start_date=datetime.utcnow(),
            end_date=None,  # Plan gratuit sans date d'expiration
            is_yearly=False
        )
        db.add(free_subscription)
    
    await db.commit()

    otp = generate_otp()
    otp_store[str(new_user.email)] = otp  

    background_tasks.add_task(send_email, new_user.email, otp)

    return new_user

@router.post("/verify/{email}", response_model=UserOut)
async def verify_user(request: VerifyCodeRequest, email: str, db: AsyncSession = Depends(get_db_session)):
    otp_expected = otp_store.get(email)
    if not otp_expected or request.code != otp_expected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, 
                            detail="Code OTP invalide ou expiré")

    # Récupérer l'utilisateur de manière asynchrone
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur non trouvé")

    user.is_active = True
    await db.commit()
    return user

@router.post("/forgot-password")
async def forgot_password(email: str, db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Utilisateur introuvable")

    otp = generate_otp()
    otp_store[str(user.email)] = otp
    await send_forgot_password_email(user.email, otp)

    return {"message": "Code OTP envoyé par email"}


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, email: str, db: AsyncSession = Depends(get_db_session)):
    otp_expected = otp_store.get(email)
    if not otp_expected or data.code != otp_expected:
        raise HTTPException(status_code=400, detail="Code invalide")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")

    user.password = hashed(data.new_password)
    await db.commit()
    return {"message": "Mot de passe réinitialisé avec succès"}


@router.get("/all", response_model=List[UserOut])
async def get_all_users(db: AsyncSession = Depends(get_db_session)):
    # Exécuter la requête asynchrone et récupérer tous les résultats
    result = await db.execute(select(User))
    users = result.scalars().all()
    return users

