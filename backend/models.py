from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Date,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.orm import relationship
from .db import Base


class Tender(Base):
    __tablename__ = "tenders"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String, index=True, nullable=True)
    platform = Column(String, nullable=True)
    customer_name = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    description_raw = Column(Text, nullable=True)

    price_amount = Column(Float, nullable=True)
    price_currency = Column(String, default="KZT")

    bid_start_date = Column(Date, nullable=True)
    bid_end_date = Column(Date, nullable=True)
    delivery_deadline = Column(Date, nullable=True)

    requirements_text = Column(Text, nullable=True)
    category = Column(String, index=True, nullable=True)
    region = Column(String, index=True, nullable=True)

    risk_score = Column(Float, default=0.0)
    risk_level = Column(String, default="low")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    risk_flags = relationship("RiskFlag", back_populates="tender")
    tender_suppliers = relationship("TenderSupplier", back_populates="tender")


class Supplier(Base):
    __tablename__ = "suppliers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    bin_iin = Column(String, nullable=True)
    region = Column(String, nullable=True)
    categories = Column(Text, nullable=True)  # например, "IT,Услуги"
    avg_contract_size = Column(Float, nullable=True)
    contracts_count = Column(Integer, nullable=True)
    win_rate = Column(Float, nullable=True)  # 0..1
    risk_score = Column(Float, default=0.0)

    tender_suppliers = relationship("TenderSupplier", back_populates="supplier")


class TenderSupplier(Base):
    __tablename__ = "tender_suppliers"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("tenders.id"))
    supplier_id = Column(Integer, ForeignKey("suppliers.id"))
    match_score = Column(Float, default=0.0)

    tender = relationship("Tender", back_populates="tender_suppliers")
    supplier = relationship("Supplier", back_populates="tender_suppliers")


class RiskFlag(Base):
    __tablename__ = "risk_flags"

    id = Column(Integer, primary_key=True, index=True)
    tender_id = Column(Integer, ForeignKey("tenders.id"))
    code = Column(String)
    description = Column(Text)
    weight = Column(Float, default=0.0)

    tender = relationship("Tender", back_populates="risk_flags")
