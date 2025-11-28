from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class TenderBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    external_id: Optional[str] = None
    platform: Optional[str] = None
    customer_name: Optional[str] = None
    subject: Optional[str] = None
    description_raw: Optional[str] = None
    price_amount: Optional[float] = None
    price_currency: Optional[str] = "KZT"
    bid_start_date: Optional[date] = None
    bid_end_date: Optional[date] = None
    delivery_deadline: Optional[date] = None
    requirements_text: Optional[str] = None
    category: Optional[str] = None
    region: Optional[str] = None


class TenderCreate(TenderBase):
    pass


class TenderOut(TenderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    risk_score: float
    risk_level: str
    created_at: datetime
    updated_at: datetime


class RiskFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    description: str
    weight: float


class SupplierOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    region: str | None = None
    match_score: float | None = None
    avg_contract_size: float | None = None
    win_rate: float | None = None


class TenderReport(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tender: TenderOut
    risk_flags: List[RiskFlagOut]
    suppliers: List[SupplierOut]
