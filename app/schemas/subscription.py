from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Union
from app.models.user import PlanType, SubscriptionStatus
from uuid import UUID

class PlanBase(BaseModel):
    name: str
    plan_type: PlanType
    storage_limit_mb: int
    price_monthly: float = Field(..., description="Prix mensuel en FCFA")
    price_yearly: float = Field(..., description="Prix annuel en FCFA")

class PlanCreate(PlanBase):
    wave_payment_link_monthly: Optional[str] = None
    wave_payment_link_yearly: Optional[str] = None

class PlanOut(PlanBase):
    id: UUID
    wave_payment_link_monthly: Optional[str] = None
    wave_payment_link_yearly: Optional[str] = None
    is_active: bool
    created_at: datetime

    @property
    def price_monthly_formatted(self) -> str:
        """Prix mensuel formaté en FCFA"""
        if self.price_monthly == 0:
            return "Gratuit"
        return f"{int(self.price_monthly):,} FCFA".replace(",", ".")

    @property
    def price_yearly_formatted(self) -> str:
        """Prix annuel formaté en FCFA"""
        if self.price_yearly == 0:
            return "Gratuit"
        return f"{int(self.price_yearly):,} FCFA".replace(",", ".")

    class Config:
        from_attributes = True

class SubscriptionBase(BaseModel):
    plan_id: str
    is_yearly: bool = False

class SubscriptionCreate(SubscriptionBase):
    pass

class SubscriptionOut(BaseModel):
    id: str
    user_id: str  # Uniformisé en str pour cohérence avec StorageUsageOut
    plan_id: str
    status: SubscriptionStatus
    start_date: datetime
    end_date: Optional[datetime]
    is_yearly: bool
    created_at: datetime

    class Config:
        from_attributes = True

class StorageUsageOut(BaseModel):
    id: UUID
    user_id: str  # Type attendu : str (corrigé)
    used_storage_mb: float
    last_calculated: datetime

    @classmethod
    def from_orm(cls, obj):
        """Convertit automatiquement les UUID en str si nécessaire."""
        if isinstance(obj.user_id, UUID):
            obj.user_id = str(obj.user_id)
        return cls.model_validate(obj)

    class Config:
        from_attributes = True

class CreatePaymentIntentRequest(BaseModel):
    plan_id: str
    is_yearly: bool = False

class WavePaymentResponse(BaseModel):
    payment_link: str
    plan_name: str
    price: float
    currency: str = "FCFA"
    period: str
    storage_limit_mb: int
    user_id: str  # Uniformisé en str (au lieu de UUID)
    plan_id: str
    is_yearly: bool

class PaymentConfirmationRequest(BaseModel):
    plan_id: str
    is_yearly: bool
    transaction_id: str

class PlanDisplayOut(BaseModel):
    id: UUID
    name: str
    plan_type: PlanType
    storage_limit_gb: float  # Affichage en GB
    price_monthly_fcfa: str
    price_yearly_fcfa: str
    wave_payment_link_monthly: Optional[str] = None
    wave_payment_link_yearly: Optional[str] = None
    is_active: bool

    @classmethod
    def from_plan(cls, plan):
        return cls(
            id=plan.id,  # UUID reste UUID ici (car utilisé en interne)
            name=plan.name,
            plan_type=plan.plan_type,
            storage_limit_gb=round(plan.storage_limit_mb / 1024, 1),
            price_monthly_fcfa=f"{int(plan.price_monthly):,} FCFA".replace(",", ".") if plan.price_monthly > 0 else "Gratuit",
            price_yearly_fcfa=f"{int(plan.price_yearly):,} FCFA".replace(",", ".") if plan.price_yearly > 0 else "Gratuit",
            wave_payment_link_monthly=plan.wave_payment_link_monthly,
            wave_payment_link_yearly=plan.wave_payment_link_yearly,
            is_active=plan.is_active
        )

