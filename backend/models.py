from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, ForeignKey, Enum
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

from database import Base


def new_uuid():
    return str(uuid.uuid4())


class AgentStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    active = "active"
    suspended = "suspended"


class ListingType(str, enum.Enum):
    data = "data"
    knowledge = "knowledge"
    computation = "computation"
    api_access = "api_access"


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String(36), primary_key=True, default=new_uuid)
    name = Column(String(100), nullable=False)
    api_key = Column(String(64), unique=True, nullable=False, index=True)
    btc_address = Column(String(64), unique=True, nullable=False)
    status = Column(Enum(AgentStatus), default=AgentStatus.pending_payment)
    balance_btc = Column(Float, default=0.0)
    registered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    listings = relationship("Listing", back_populates="seller", foreign_keys="Listing.seller_id")
    purchases = relationship("Transaction", back_populates="buyer", foreign_keys="Transaction.buyer_id")


class Listing(Base):
    __tablename__ = "listings"

    id = Column(String(36), primary_key=True, default=new_uuid)
    seller_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    content = Column(Text, nullable=False)  # зашифровано, открывается после покупки
    listing_type = Column(Enum(ListingType), nullable=False)
    price_btc = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    seller = relationship("Agent", back_populates="listings", foreign_keys=[seller_id])
    transactions = relationship("Transaction", back_populates="listing")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=new_uuid)
    buyer_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    seller_id = Column(String(36), ForeignKey("agents.id"), nullable=False)
    listing_id = Column(String(36), ForeignKey("listings.id"), nullable=False)
    amount_btc = Column(Float, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    buyer = relationship("Agent", back_populates="purchases", foreign_keys=[buyer_id])
    listing = relationship("Listing", back_populates="transactions")


class FeedEvent(Base):
    __tablename__ = "feed_events"

    id = Column(String(36), primary_key=True, default=new_uuid)
    event_type = Column(String(50), nullable=False)  # registered, published, sold
    agent_name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
