from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from datetime import datetime, timedelta
from app.postgres_connect import get_db_session
from app.models.user import User, Plan, Subscription, StorageUsage, SubscriptionStatus
from app.schemas.subscription import (
    PlanOut,
    SubscriptionOut,
    SubscriptionCreate,
    StorageUsageOut,
    WavePaymentResponse,
    PaymentConfirmationRequest,
    PlanDisplayOut
)
from app.oauth2 import get_current_user

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])

# -------------------- Plans --------------------
@router.get("/plans", response_model=List[PlanOut])
async def get_available_plans(db: AsyncSession = Depends(get_db_session)):
    result = await db.execute(select(Plan).where(Plan.is_active == True).order_by(Plan.storage_limit_mb))
    plans = result.scalars().all()
    return plans

@router.post("/plans", response_model=PlanOut)
async def create_plan(
    plan_data: dict,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé. Droits administrateur requis."
        )
    new_plan = Plan(**plan_data)
    db.add(new_plan)
    await db.commit()
    await db.refresh(new_plan)
    return new_plan

# -------------------- Subscriptions --------------------
@router.get("/my-subscription", response_model=SubscriptionOut)
async def get_my_subscription(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.user_id == current_user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalars().first()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun abonnement actif trouvé"
        )
    return SubscriptionOut.from_orm(subscription)

@router.get("/storage-usage", response_model=StorageUsageOut)
async def get_storage_usage(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(
        select(StorageUsage).where(StorageUsage.user_id == current_user.id)
    )
    usage = result.scalars().first()
    if not usage:
        usage = StorageUsage(user_id=current_user.id, used_storage_mb=0.0)
        db.add(usage)
        await db.commit()
        await db.refresh(usage)
    return StorageUsageOut.from_orm(usage)  # Utilise le validateur personnalisé

@router.post("/upgrade", response_model=SubscriptionOut)
async def upgrade_subscription(
    subscription_data: SubscriptionCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    plan_result = await db.execute(select(Plan).where(Plan.id == subscription_data.plan_id))
    plan = plan_result.scalars().first()
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan non trouvé"
        )

    # Désactiver l'abonnement actif
    current_sub_result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    )
    current_subscription = current_sub_result.scalars().first()
    if current_subscription:
        current_subscription.status = SubscriptionStatus.CANCELLED
        current_subscription.end_date = datetime.utcnow()

    end_date = datetime.utcnow() + timedelta(days=365 if subscription_data.is_yearly else 30)
    new_subscription = Subscription(
        user_id=current_user.id,
        plan_id=subscription_data.plan_id,
        status=SubscriptionStatus.ACTIVE,
        start_date=datetime.utcnow(),
        end_date=end_date,
        is_yearly=subscription_data.is_yearly
    )
    db.add(new_subscription)
    await db.commit()
    await db.refresh(new_subscription)
    return SubscriptionOut.from_orm(new_subscription)

@router.post("/cancel")
async def cancel_subscription(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    result = await db.execute(
        select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.status == SubscriptionStatus.ACTIVE
        )
    )
    subscription = result.scalars().first()
    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucun abonnement actif à annuler"
        )

    subscription.status = SubscriptionStatus.CANCELLED
    subscription.end_date = datetime.utcnow()
    await db.commit()
    return {"message": "Abonnement annulé avec succès"}

