from typing import List, Dict, Tuple
from sqlalchemy.orm import Session
from .models import Tender, RiskFlag


def compute_risk_for_tender(
    db: Session, tender: Tender
) -> Tuple[float, str, List[Dict]]:
    """
    Простая rule-based логика для MVP.
    Возвращает: (risk_score, risk_level, список флагов в виде dict).
    """
    flags: List[Dict] = []
    score = 0.0

    # Правило 1: завышенная цена относительно похожих тендеров
    if tender.price_amount and tender.category:
        similar = (
            db.query(Tender)
            .filter(
                Tender.category == tender.category,
                Tender.id != tender.id,
                Tender.price_amount.isnot(None),
            )
            .all()
        )
        if len(similar) >= 3:
            avg_price = sum(t.price_amount for t in similar) / len(similar)
            if avg_price > 0 and tender.price_amount > avg_price * 1.3:
                delta = tender.price_amount - avg_price
                flags.append(
                    {
                        "code": "OVERPRICE",
                        "description": f"Цена выше средней по категории на {delta:.0f}",
                        "weight": 25.0,
                    }
                )
                score += 25.0

    # Правило 2: очень короткий срок подачи заявок
    if tender.bid_start_date and tender.bid_end_date:
        days = (tender.bid_end_date - tender.bid_start_date).days
        if days <= 3:
            flags.append(
                {
                    "code": "SHORT_BID_PERIOD",
                    "description": "Очень короткий срок подачи заявок",
                    "weight": 20.0,
                }
            )
            score += 20.0

    # !!! Здесь можно добавлять новые правила (аффилированность, конкуренция и т.д.)

    # Нормализация и уровень риска
    score = min(score, 100.0)
    if score >= 60:
        level = "high"
    elif score >= 30:
        level = "medium"
    else:
        level = "low"

    # Сохранение флагов и обновление тендера
    # Сначала удаляем старые флаги
    db.query(RiskFlag).filter(RiskFlag.tender_id == tender.id).delete()

    for f in flags:
        rf = RiskFlag(
            tender_id=tender.id,
            code=f["code"],
            description=f["description"],
            weight=f["weight"],
        )
        db.add(rf)

    tender.risk_score = score
    tender.risk_level = level
    db.add(tender)
    db.commit()

    return score, level, flags
