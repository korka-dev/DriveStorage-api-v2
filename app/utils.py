import os
import httpx
from passlib.context import CryptContext
from random import randint
from dotenv import load_dotenv
from datetime import datetime

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

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()



async def send_forgot_password_email(to_email: str, otp: str):
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

    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.json()


def get_filename(filename: str) -> str:
    base, ext = os.path.splitext(filename)

    return f"{base}_{datetime.now()}{ext}"

