"""
Script pour initialiser les plans d'abonnement par défaut avec les liens Wave
"""
import asyncio
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.postgres_connect import AsyncSessionLocal
from app.models.user import Plan, PlanType

async def create_default_plans():
    """Créer les plans d'abonnement par défaut avec les liens Wave"""
    
    plans_data = [
        {
            "name": "Gratuit",
            "plan_type": PlanType.FREE,
            "storage_limit_mb": 300,
            "price_monthly": 0.0,
            "price_yearly": 0.0,
            "wave_payment_link_monthly": None,
            "wave_payment_link_yearly": None,
            "is_active": True
        },
        {
            "name": "Basique",
            "plan_type": PlanType.BASIC,
            "storage_limit_mb": 5120,  # 5GB
            "price_monthly": 2000.0,  # 2.000 FCFA
            "price_yearly": 20000.0,  # 20.000 FCFA
            "wave_payment_link_monthly": "https://pay.wave.com/m/M_sn_nipMFngsi-Fy/c/sn/?amount=2000",
            "wave_payment_link_yearly": "https://pay.wave.com/m/M_sn_nipMFngsi-Fy/c/sn/?amount=20000",
            "is_active": True
        },
        {
            "name": "Premium",
            "plan_type": PlanType.PREMIUM,
            "storage_limit_mb": 51200,  # 50GB
            "price_monthly": 5000.0,  # 5.000 FCFA
            "price_yearly": 50000.0,  # 50.000 FCFA
            "wave_payment_link_monthly": "https://wave.com/pay/premium-monthly-5000fcfa",
            "wave_payment_link_yearly": "https://wave.com/pay/premium-yearly-50000fcfa",
            "is_active": True
        },
        {
            "name": "Entreprise",
            "plan_type": PlanType.ENTERPRISE,
            "storage_limit_mb": 512000,  # 500GB
            "price_monthly": 15000.0,  # 15.000 FCFA
            "price_yearly": 150000.0,  # 150.000 FCFA
            "wave_payment_link_monthly": "https://wave.com/pay/enterprise-monthly-15000fcfa",
            "wave_payment_link_yearly": "https://wave.com/pay/enterprise-yearly-150000fcfa",
            "is_active": True
        }
    ]
    
    async with AsyncSessionLocal() as session:
        try:
            for plan_data in plans_data:
                # Vérifier si le plan existe déjà
                from sqlalchemy.future import select
                result = await session.execute(
                    select(Plan).where(Plan.name == plan_data["name"])
                )
                existing_plan = result.scalars().first()
                
                if not existing_plan:
                    plan = Plan(**plan_data)
                    session.add(plan)
                    print(f"✅ Plan '{plan_data['name']}' créé avec liens Wave")
                else:
                    existing_plan.wave_payment_link_monthly = plan_data["wave_payment_link_monthly"]
                    existing_plan.wave_payment_link_yearly = plan_data["wave_payment_link_yearly"]
                    print(f"⚠️  Plan '{plan_data['name']}' mis à jour avec liens Wave")
            
            await session.commit()
            print("🎉 Initialisation des plans avec Wave terminée avec succès!")
            
        except Exception as e:
            await session.rollback()
            print(f"❌ Erreur lors de l'initialisation des plans: {e}")
            raise

if __name__ == "__main__":
    asyncio.run(create_default_plans())
