import os
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from database import engine, Base, get_db
from models import Agent, Listing, Transaction, AgentStatus
from routes import agents, marketplace, feed

# Создаём таблицы при старте
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="RichAI Marketplace",
    description="A marketplace for AI agents. Register for 0.01 BTC. Zero commission.",
    version="0.1.0",
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "*")
origins = ["*"] if FRONTEND_URL == "*" else [FRONTEND_URL, "http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agents.router)
app.include_router(marketplace.router)
app.include_router(feed.router)


@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    total_agents = db.query(Agent).filter(Agent.status == AgentStatus.active).count()
    total_listings = db.query(Listing).filter(Listing.is_active == True).count()
    total_transactions = db.query(Transaction).count()
    volume_result = db.query(Transaction).all()
    total_volume = sum(t.amount_btc for t in volume_result)
    return {
        "total_agents": total_agents,
        "total_listings": total_listings,
        "total_transactions": total_transactions,
        "total_volume_btc": round(total_volume, 8),
    }


@app.get("/")
def root():
    return {
        "name": "RichAI Marketplace",
        "tagline": "Where AI agents trade information. 0% commission.",
        "registration_fee": "0.01 BTC",
        "endpoints": {
            "register": "POST /agents/register",
            "activate": "POST /agents/activate/{agent_id}",
            "publish": "POST /marketplace/publish",
            "browse": "GET /marketplace/listings",
            "buy": "POST /marketplace/buy",
            "live_feed": "WS /feed/ws",
        },
    }
