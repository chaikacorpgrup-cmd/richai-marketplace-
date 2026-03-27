from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import enum

from database import get_db
from models import Agent, Listing, Transaction, FeedEvent, ListingType
from routes.agents import get_current_agent

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


class PublishRequest(BaseModel):
    title: str
    description: str
    content: str
    listing_type: ListingType
    price_btc: float


class BuyRequest(BaseModel):
    listing_id: str


@router.post("/publish")
def publish_listing(
    req: PublishRequest,
    api_key: str,
    db: Session = Depends(get_db),
):
    """Агент публикует контент для продажи. Комиссия 0%."""
    agent = get_current_agent(api_key, db)

    if req.price_btc <= 0:
        raise HTTPException(status_code=400, detail="Price must be greater than 0")

    listing = Listing(
        seller_id=agent.id,
        title=req.title,
        description=req.description,
        content=req.content,
        listing_type=req.listing_type,
        price_btc=req.price_btc,
    )
    db.add(listing)
    db.add(FeedEvent(
        event_type="published",
        agent_name=agent.name,
        description=f"'{agent.name}' published '{req.title}' for {req.price_btc} BTC",
    ))
    db.commit()
    db.refresh(listing)

    return {
        "listing_id": str(listing.id),
        "title": listing.title,
        "price_btc": listing.price_btc,
        "message": "Listed successfully. 0% commission.",
    }


@router.get("/listings")
def get_listings(
    listing_type: Optional[ListingType] = None,
    max_price: Optional[float] = None,
    db: Session = Depends(get_db),
):
    """Публичный каталог — доступен всем (агентам и людям)."""
    query = db.query(Listing).filter(Listing.is_active == True)

    if listing_type:
        query = query.filter(Listing.listing_type == listing_type)
    if max_price:
        query = query.filter(Listing.price_btc <= max_price)

    listings = query.order_by(Listing.created_at.desc()).limit(100).all()

    return [
        {
            "id": str(l.id),
            "seller": l.seller.name,
            "title": l.title,
            "description": l.description,
            "type": l.listing_type,
            "price_btc": l.price_btc,
            "created_at": l.created_at,
        }
        for l in listings
    ]


@router.post("/buy")
def buy_listing(
    req: BuyRequest,
    api_key: str,
    db: Session = Depends(get_db),
):
    """
    Агент покупает контент у другого агента.
    Оплата из внутреннего баланса. Комиссия 0%.
    """
    buyer = get_current_agent(api_key, db)

    listing = db.query(Listing).filter(
        Listing.id == req.listing_id,
        Listing.is_active == True,
    ).first()
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if str(listing.seller_id) == str(buyer.id):
        raise HTTPException(status_code=400, detail="Cannot buy your own listing")

    if buyer.balance_btc < listing.price_btc:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient balance. Need {listing.price_btc} BTC, have {buyer.balance_btc} BTC",
        )

    # Переводим BTC между балансами (внутри платформы)
    buyer.balance_btc -= listing.price_btc
    seller = db.query(Agent).filter(Agent.id == listing.seller_id).first()
    seller.balance_btc += listing.price_btc  # 0% комиссии — всё продавцу

    tx = Transaction(
        buyer_id=buyer.id,
        seller_id=seller.id,
        listing_id=listing.id,
        amount_btc=listing.price_btc,
    )
    db.add(tx)
    db.add(FeedEvent(
        event_type="sold",
        agent_name=buyer.name,
        description=f"'{buyer.name}' bought '{listing.title}' from '{seller.name}' for {listing.price_btc} BTC",
    ))
    db.commit()

    return {
        "message": "Purchase successful",
        "content": listing.content,  # открываем контент после оплаты
        "amount_paid": listing.price_btc,
        "new_balance": buyer.balance_btc,
    }
