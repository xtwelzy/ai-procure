from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import csv
import io
import re

import ollama
from pydantic import BaseModel

from .db import Base, engine, get_db
from . import models
from .schemas import TenderCreate, TenderOut, TenderReport, RiskFlagOut, SupplierOut
from .risk_engine import compute_risk_for_tender

Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI-Procure")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =====================================================================
#                            ЗАГРУЗКА ДАННЫХ
# =====================================================================


@app.post("/tenders/ingest_csv", response_model=List[TenderOut])
async def ingest_tenders_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db)
):
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    created_tenders: List[models.Tender] = []

    for row in reader:
        data = TenderCreate(
            external_id=row.get("external_id"),
            platform=row.get("platform"),
            customer_name=row.get("customer_name"),
            subject=row.get("subject"),
            description_raw=row.get("description_raw"),
            price_amount=(
                float(row["price_amount"]) if row.get("price_amount") else None
            ),
            price_currency=row.get("price_currency") or "KZT",
            category=row.get("category"),
            region=row.get("region"),
        )

        tender = models.Tender(**data.dict())
        db.add(tender)
        db.commit()
        db.refresh(tender)

        # первичный расчёт риска
        compute_risk_for_tender(db, tender)

        created_tenders.append(tender)

    return created_tenders


@app.post("/suppliers/ingest_csv", response_model=List[SupplierOut])
async def ingest_suppliers_csv(
    file: UploadFile = File(...), db: Session = Depends(get_db)
):
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    suppliers: List[models.Supplier] = []

    for row in reader:
        s = models.Supplier(
            name=row.get("name"),
            bin_iin=row.get("bin_iin"),
            region=row.get("region"),
            categories=row.get("categories"),
            avg_contract_size=(
                float(row["avg_contract_size"])
                if row.get("avg_contract_size")
                else None
            ),
            contracts_count=(
                int(row["contracts_count"]) if row.get("contracts_count") else None
            ),
            win_rate=float(row["win_rate"]) if row.get("win_rate") else None,
            risk_score=float(row["risk_score"]) if row.get("risk_score") else 0.0,
        )
        db.add(s)
        db.commit()
        db.refresh(s)
        suppliers.append(s)

    result = [
        SupplierOut(
            id=s.id,
            name=s.name,
            region=s.region,
            match_score=None,
            avg_contract_size=s.avg_contract_size,
            win_rate=s.win_rate,
        )
        for s in suppliers
    ]
    return result


# =====================================================================
#                            ПРОСМОТР ТЕНДЕРОВ
# =====================================================================


@app.get("/tenders", response_model=List[TenderOut])
def list_tenders(
    db: Session = Depends(get_db),
    category: Optional[str] = Query(None),
    platform: Optional[str] = Query(None),
    risk_level: Optional[str] = Query(None),
):
    q = db.query(models.Tender)
    if category:
        q = q.filter(models.Tender.category == category)
    if platform:
        q = q.filter(models.Tender.platform == platform)
    if risk_level:
        q = q.filter(models.Tender.risk_level == risk_level)

    q = q.order_by(models.Tender.created_at.desc())
    return q.all()


@app.get("/tenders/{tender_id}", response_model=TenderOut)
def get_tender(tender_id: int, db: Session = Depends(get_db)):
    tender = db.query(models.Tender).get(tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")
    return tender


# =====================================================================
#                       ОТЧЁТ ПО ТЕНДЕРУ + ПОДБОР ПОСТАВЩИКОВ
# =====================================================================


@app.get("/tenders/{tender_id}/report", response_model=TenderReport)
def get_tender_report(tender_id: int, db: Session = Depends(get_db)):
    tender = db.query(models.Tender).get(tender_id)
    if not tender:
        raise HTTPException(status_code=404, detail="Tender not found")

    # пересчёт риска
    compute_risk_for_tender(db, tender)

    flags = (
        db.query(models.RiskFlag).filter(models.RiskFlag.tender_id == tender.id).all()
    )

    suppliers_q = db.query(models.Supplier)
    if tender.category:
        suppliers_q = suppliers_q.filter(
            models.Supplier.categories.ilike(f"%{tender.category}%")
        )
    if tender.region:
        suppliers_q = suppliers_q.filter(
            (models.Supplier.region == tender.region)
            | (models.Supplier.region.is_(None))
        )

    suppliers = suppliers_q.limit(5).all()

    supplier_out: List[SupplierOut] = []
    for s in suppliers:
        base_score = 0.5
        if s.avg_contract_size and tender.price_amount:
            ratio = tender.price_amount / s.avg_contract_size
            if 0.5 <= ratio <= 2:
                base_score += 0.3
        if s.win_rate is not None:
            base_score += min(s.win_rate, 0.2)

        supplier_out.append(
            SupplierOut(
                id=s.id,
                name=s.name,
                region=s.region,
                match_score=min(base_score, 1.0),
                avg_contract_size=s.avg_contract_size,
                win_rate=s.win_rate,
            )
        )

    flags_out = [
        RiskFlagOut(id=f.id, code=f.code, description=f.description, weight=f.weight)
        for f in flags
    ]

    tender_out = TenderOut.from_orm(tender)

    return TenderReport(tender=tender_out, risk_flags=flags_out, suppliers=supplier_out)


# =====================================================================
#                      ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ КОНТЕКСТА
# =====================================================================


def build_tender_context(db: Session, tender_id: int) -> Optional[str]:
    """Формирует текстовый контекст по тендеру для ИИ."""
    tender = db.query(models.Tender).get(tender_id)
    if not tender:
        return None

    compute_risk_for_tender(db, tender)

    flags = (
        db.query(models.RiskFlag).filter(models.RiskFlag.tender_id == tender.id).all()
    )

    suppliers_q = db.query(models.Supplier)
    if tender.category:
        suppliers_q = suppliers_q.filter(
            models.Supplier.categories.ilike(f"%{tender.category}%")
        )
    if tender.region:
        suppliers_q = suppliers_q.filter(
            (models.Supplier.region == tender.region)
            | (models.Supplier.region.is_(None))
        )
    suppliers = suppliers_q.limit(5).all()

    parts = []
    parts.append(f"ID (в БД): {tender.id}")
    if tender.external_id:
        parts.append(f"Внешний номер: {tender.external_id}")
    if tender.platform:
        parts.append(f"Площадка: {tender.platform}")
    if tender.customer_name:
        parts.append(f"Заказчик: {tender.customer_name}")
    if tender.subject:
        parts.append(f"Предмет закупки: {tender.subject}")
    if tender.description_raw:
        parts.append(f"Описание: {tender.description_raw}")
    if tender.price_amount:
        parts.append(f"Цена: {tender.price_amount} {tender.price_currency or 'KZT'}")
    if tender.category:
        parts.append(f"Категория: {tender.category}")
    if tender.region:
        parts.append(f"Регион: {tender.region}")

    if flags:
        parts.append("\nФлаги риска:")
        for f in flags:
            parts.append(f"- [{f.code}] {f.description} (вес {f.weight})")
    else:
        parts.append("\nФлаги риска: не найдены.")

    if suppliers:
        parts.append("\nРекомендованные поставщики:")
        for s in suppliers:
            parts.append(
                f"- {s.name} (регион: {s.region or 'не указан'}, "
                f"средний контракт: {s.avg_contract_size or 'N/A'}, "
                f"win_rate: {s.win_rate or 'N/A'})"
            )
    else:
        parts.append("\nПодходящие поставщики: не найдены.")

    return "\n".join(parts)


def extract_tender_id_from_text(text: str) -> Optional[int]:
    """Ищем в тексте что-то вроде 'тендер 5' или 'tender 10'."""
    m = re.search(r"(тендер|tender)\D*(\d+)", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(2))
        except ValueError:
            return None
    return None


# =====================================================================
#                          AI: АНАЛИЗ ТЕНДЕРА
# =====================================================================


class AIAnalysisResponse(BaseModel):
    tender_id: int
    analysis: str


@app.get("/ai/analyze_tender/{tender_id}", response_model=AIAnalysisResponse)
def ai_analyze_tender(tender_id: int, db: Session = Depends(get_db)):
    context = build_tender_context(db, tender_id)
    if not context:
        raise HTTPException(status_code=404, detail="Tender not found")

    prompt = f"""
Ты — AI-ассистент по тендерам и закупкам банка.
Ниже приведены данные по конкретному тендеру.

ДАННЫЕ ТЕНДЕРА:
{context}

Задача:
1. Кратко перескажи суть закупки.
2. Оцени потенциальные риски (аффилированность, завышенная цена, слабая конкуренция и т.п.).
3. Дай рекомендации: участвовать / отказаться, на что обратить внимание, какие документы проверить.
4. Если каких-то данных нет в описании (даты, точные условия и т.д.) — честно скажи, что в данных это не указано.
Не придумывай факты, которых нет в контексте.
"""

    res = ollama.generate(
        model="llama3",
        prompt=prompt,
    )

    return AIAnalysisResponse(tender_id=tender_id, analysis=res["response"])


# =====================================================================
#                          AI: ЧАТ-АССИСТЕНТ
# =====================================================================


class ChatMessage(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post("/chat/send", response_model=ChatResponse)
def chat_send(msg: ChatMessage, db: Session = Depends(get_db)):
    user_msg = msg.message.strip()

    # Пытаемся вытащить ID тендера из текста
    tender_id = extract_tender_id_from_text(user_msg)
    tender_context = None
    if tender_id is not None:
        tender_context = build_tender_context(db, tender_id)

    if tender_context:
        prompt = f"""
Ты — AI-ассистент по тендерам и закупкам для банка.

Пользователь задал вопрос:
\"\"\"{user_msg}\"\"\".

Ниже — данные из внутренней системы по тендеру (и связанным объектам),
которые НУЖНО считать единственным источником правды:

{tender_context}

Требования к ответу:
- опирайся ТОЛЬКО на эти данные;
- если каких-то параметров нет (например, нет сроков, дат, объёма работ),
  так и скажи: "в доступных данных это не указано";
- не выдумывай цены, даты или участников, которых нет в контексте;
- отвечай структурировано, на деловом русском языке.
"""
    else:
        # Нет конкретного тендера — даём общий экспертный ответ без "фейковых" фактов
        prompt = f"""
Ты — AI-ассистент по тендерам и закупкам.
Пользователь задаёт общий вопрос (контекст по конкретному тендеру не найден):

Вопрос:
\"\"\"{user_msg}\"\"\".

Ответь:
- на деловом русском языке;
- опираясь на общие принципы закупок, тендерного анализа и управления рисками;
- если вопрос явно требует данных какого-то конкретного тендера, предложи пользователю
  указать его номер, например: "тендер 5".
"""

    res = ollama.generate(
        model="llama3",
        prompt=prompt,
    )

    return ChatResponse(reply=res["response"])
