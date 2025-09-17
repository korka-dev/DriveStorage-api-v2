from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timedelta
import uuid

from app.postgres_connect import get_db_session
from app.models.user import User
from app.models.user import Plan, Subscription, SubscriptionStatus
from app.oauth2 import get_current_user
from app.utils import send_subscription_confirmation_email

router = APIRouter(prefix="/payments", tags=["Payments"])

@router.get("/get-payment-link/{plan_id}")
async def get_wave_payment_link(
    plan_id: str,
    is_yearly: bool = False,
    current_user: Annotated[User, Depends(get_current_user)] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """Récupérer le lien de paiement Wave pour un plan spécifique"""
    
    # Vérifier que le plan existe
    plan_result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = plan_result.scalars().first()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan non trouvé"
        )
    
    payment_link = plan.wave_payment_link_yearly if is_yearly else plan.wave_payment_link_monthly
    price = plan.price_yearly if is_yearly else plan.price_monthly
    
    if not payment_link:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Lien de paiement non disponible pour ce plan"
        )
    
    return {
        "payment_link": payment_link,
        "plan_name": plan.name,
        "price": price,
        "currency": "FCFA",
        "period": "Annuel" if is_yearly else "Mensuel",
        "storage_limit_mb": plan.storage_limit_mb,
        "user_id": str(current_user.id),
        "plan_id": str(plan_id),
        "is_yearly": is_yearly
    }

@router.post("/confirm-payment")
async def confirm_wave_payment(
    plan_id: str,
    is_yearly: bool,
    transaction_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    """Confirmer un paiement Wave et activer l'abonnement"""
    
    # Vérifier que le plan existe
    plan_result = await db.execute(
        select(Plan).where(Plan.id == plan_id)
    )
    plan = plan_result.scalars().first()
    
    if not plan:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan non trouvé"
        )
    
    existing_sub_result = await db.execute(
        select(Subscription).where(Subscription.wave_transaction_id == transaction_id)
    )
    existing_sub = existing_sub_result.scalars().first()
    
    if existing_sub:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cette transaction a déjà été utilisée"
        )
    
    # Désactiver l'abonnement actuel s'il existe
    current_subscription_result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
    )
    current_subscription = current_subscription_result.scalars().first()
    
    if current_subscription:
        current_subscription.status = SubscriptionStatus.CANCELLED
        current_subscription.end_date = datetime.utcnow()
    
    end_date = datetime.utcnow() + timedelta(days=365 if is_yearly else 30)
    
    new_subscription = Subscription(
        user_id=current_user.id,
        plan_id=uuid.UUID(plan_id),
        status=SubscriptionStatus.ACTIVE,
        start_date=datetime.utcnow(),
        end_date=end_date,
        is_yearly=is_yearly,
        wave_transaction_id=transaction_id
    )
    
    db.add(new_subscription)
    await db.commit()
    
    await send_subscription_confirmation_email(
    to_email=current_user.email,
    plan_name=plan.name,
    storage_limit_mb=plan.storage_limit_mb,
    end_date=end_date,
    is_yearly=is_yearly
    )
    
    return {
        "success": True,
        "message": "Abonnement activé avec succès",
        "plan_name": plan.name,
        "storage_limit_mb": plan.storage_limit_mb,
        "end_date": end_date,
        "transaction_id": transaction_id
    }

@router.get("/subscription-status")
async def get_subscription_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: AsyncSession = Depends(get_db_session)
):
    """Vérifier le statut d'abonnement de l'utilisateur connecté"""
    result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == current_user.id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
        .order_by(Subscription.created_at.desc())
    )
    subscription = result.scalars().first()
    
    if subscription:
        # Vérifier si l'abonnement n'a pas expiré
        if subscription.end_date and subscription.end_date < datetime.utcnow():
            subscription.status = SubscriptionStatus.EXPIRED
            await db.commit()
            return {"has_active_subscription": False, "status": "expired"}
        
        plan_result = await db.execute(
            select(Plan).where(Plan.id == subscription.plan_id)
        )
        plan = plan_result.scalars().first()
        
        return {
            "has_active_subscription": True,
            "status": subscription.status,
            "plan_name": plan.name if plan else "Unknown",
            "storage_limit_mb": plan.storage_limit_mb if plan else 300,
            "end_date": subscription.end_date,
            "is_yearly": subscription.is_yearly
        }
    
    return {"has_active_subscription": False, "status": "none"}

