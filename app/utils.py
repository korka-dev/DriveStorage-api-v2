import os
import httpx
from passlib.context import CryptContext
from random import randint
from dotenv import load_dotenv
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.user import StorageUsage
from app.models.file import File
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SENDINBLUE_API_KEY = os.getenv("SENDINBLUE_API_KEY")

def hashed(password: str):
    return pwd_context.hash(password)

def verify(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def generate_otp():
    return f"{randint(100000, 999999)}"

async def send_email(to_email: str, otp: str):

    if not SENDINBLUE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration email manquante"
        )
    
    url = "https://api.brevo.com/v3/smtp/email"
    subject = "👋 Bienvenue ! Voici votre code de vérification"
    html_content = f"""
    <div style="font-family: Arial, sans-serif;">
      <h2>Bienvenue sur Drive Storage 👋</h2>
      <p>Pour finaliser la création de votre compte, veuillez saisir le code OTP ci-dessous :</p>
      <h1 style="letter-spacing: 4px;">{otp}</h1>
      <p>Ce code est valable pendant 10 minutes.</p>
      <p>Si vous n'avez pas demandé à créer un compte, vous pouvez ignorer cet e-mail.</p>
    </div>
    """
    data = {
        "sender": {
            "name": "Support Drive Storage",
            "email": "diallo30amadoukorka@gmail.com"
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    headers = {
        "api-key": SENDINBLUE_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Erreur de configuration email - Clé API invalide"
                )
            elif response.status_code == 400:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Adresse email invalide ou données incorrectes"
                )
            
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service email temporairement indisponible"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur lors de l'envoi de l'email: {e.response.status_code}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'envoi de l'email"
        )

async def send_forgot_password_email(to_email: str, otp: str):
    # Vérifier que la clé API est configurée
    if not SENDINBLUE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration email manquante"
        )
    
    url = "https://api.brevo.com/v3/smtp/email"
    subject = "🔐 Code de réinitialisation de mot de passe"
    html_content = f"""
    <div style="font-family: Arial, sans-serif;">
      <h2>Demande de réinitialisation de mot de passe</h2>
      <p>Vous avez demandé à réinitialiser votre mot de passe.</p>
      <p>Voici votre code OTP :</p>
      <h1 style="letter-spacing: 4px;">{otp}</h1>
      <p>Ce code est valable pendant 10 minutes.</p>
      <p>Si vous n'avez pas fait cette demande, vous pouvez ignorer cet e-mail.</p>
    </div>
    """
    data = {
        "sender": {
            "name": "Support Drive Storage",
            "email": "diallo30amadoukorka@gmail.com"
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    headers = {
        "api-key": SENDINBLUE_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 401:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Erreur de configuration email - Clé API invalide"
                )
            elif response.status_code == 400:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Adresse email invalide ou données incorrectes"
                )
            
            response.raise_for_status()
            return response.json()
            
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Service email temporairement indisponible"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Erreur lors de l'envoi de l'email: {e.response.status_code}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'envoi de l'email"
        )

def get_filename(filename: str) -> str:
    base, ext = os.path.splitext(filename)
    return f"{base}_{datetime.now()}{ext}"
async def calculate_user_storage_usage(
    user_id: str,
    db: AsyncSession,
    gridfs_bucket: AsyncIOMotorGridFSBucket
) -> float:
    """Calcule l'utilisation totale du stockage pour un utilisateur"""
    try:
        # Récupérer tous les fichiers de l'utilisateur via Beanie
        files = await File.find(File.owner_id == user_id).to_list()

        total_size_bytes = sum(f.file_size_bytes for f in files)

        # Convertir en MB
        total_size_mb = total_size_bytes / (1024 * 1024)

        # Mettre à jour l'enregistrement d'utilisation dans PostgreSQL
        usage_result = await db.execute(
            select(StorageUsage).where(StorageUsage.user_id == user_id)
        )
        usage = usage_result.scalars().first()

        if usage:
            usage.used_storage_mb = total_size_mb
            usage.last_calculated = datetime.utcnow()
        else:
            usage = StorageUsage(
                user_id=user_id,
                used_storage_mb=total_size_mb,
                last_calculated=datetime.utcnow()
            )
            db.add(usage)

        await db.commit()
        return total_size_mb

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du calcul de l'utilisation du stockage: {str(e)}"
        )


async def check_storage_quota(
    user_id: str,
    file_size_bytes: int,
    db: AsyncSession
) -> bool:
    """Vérifie si l'utilisateur peut uploader un fichier selon son quota"""
    from app.models.user import User
    from app.models.user import Subscription, Plan, SubscriptionStatus
    
    # Récupérer l'utilisateur
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalars().first()
    
    if not user:
        return False
    
    # Récupérer l'utilisation actuelle
    usage_result = await db.execute(
        select(StorageUsage).where(StorageUsage.user_id == user_id)
    )
    usage = usage_result.scalars().first()
    current_usage_mb = usage.used_storage_mb if usage else 0.0
    
    # Récupérer la limite de stockage
    subscription_result = await db.execute(
        select(Subscription)
        .where(Subscription.user_id == user_id)
        .where(Subscription.status == SubscriptionStatus.ACTIVE)
        .order_by(Subscription.created_at.desc())
    )
    subscription = subscription_result.scalars().first()
    
    if subscription:
        plan_result = await db.execute(
            select(Plan).where(Plan.id == subscription.plan_id)
        )
        plan = plan_result.scalars().first()
        storage_limit_mb = plan.storage_limit_mb if plan else user.storage_quota_mb
    else:
        storage_limit_mb = user.storage_quota_mb
    
    # Convertir la taille du fichier en MB
    file_size_mb = file_size_bytes / (1024 * 1024)
    
    # Vérifier si l'ajout du fichier dépasse la limite
    return (current_usage_mb + file_size_mb) <= storage_limit_mb


async def send_subscription_confirmation_email(to_email: str, plan_name: str, storage_limit_mb: int, end_date: datetime, is_yearly: bool):
    if not SENDINBLUE_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configuration email manquante"
        )

    url = "https://api.brevo.com/v3/smtp/email"
    subject = "✅ Confirmation de votre abonnement"
    period = "Annuel" if is_yearly else "Mensuel"
    html_content = f"""
    <div style="font-family: Arial, sans-serif;">
      <h2>🎉 Félicitations, votre abonnement est activé !</h2>
      <p>Merci d'avoir choisi <b>Drive Storage</b>. Voici les détails de votre abonnement :</p>
      <ul>
        <li><b>Plan :</b> {plan_name}</li>
        <li><b>Période :</b> {period}</li>
        <li><b>Stockage :</b> {storage_limit_mb} MB</li>
        <li><b>Date d'expiration :</b> {end_date.strftime("%d-%m-%Y")}</li>
      </ul>
      <p>Vous pouvez désormais profiter pleinement de votre espace de stockage 🚀.</p>
    </div>
    """

    data = {
        "sender": {
            "name": "Support Drive Storage",
            "email": "diallo30amadoukorka@gmail.com"
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    headers = {
        "api-key": SENDINBLUE_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'envoi de l'email de confirmation: {str(e)}"
        )


