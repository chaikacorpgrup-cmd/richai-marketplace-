import secrets
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import Agent, AgentStatus, FeedEvent
from bitcoin import get_registration_address, create_payment_invoice, check_registration_payment

router = APIRouter(prefix="/agents", tags=["agents"])


class RegisterRequest(BaseModel):
    name: str


class AgentResponse(BaseModel):
    id: str
    name: str
    api_key: str
    btc_address: str
    status: str
    balance_btc: float
    registered_at: datetime | None

    class Config:
        from_attributes = True


def get_current_agent(api_key: str, db: Session = Depends(get_db)) -> Agent:
    agent = db.query(Agent).filter(Agent.api_key == api_key).first()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if agent.status != AgentStatus.active:
        raise HTTPException(status_code=403, detail="Agent not active. Complete payment first.")
    return agent


@router.post("/register")
async def register_agent(req: RegisterRequest, db: Session = Depends(get_db)):
    """
    Шаг 1: Агент регистрируется, получает BTC адрес для оплаты.
    После оплаты 0.01 BTC вызывает /agents/activate.
    """
    api_key = secrets.token_hex(32)
    pay_to = get_registration_address()

    agent = Agent(
        name=req.name,
        api_key=api_key,
        btc_address=pay_to,  # адрес куда платить = адрес владельца
        status=AgentStatus.pending_payment,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)

    invoice = await create_payment_invoice(str(agent.id), pay_to)

    return {
        "agent_id": str(agent.id),
        "api_key": api_key,
        "payment": invoice,
        "message": f"Send exactly 0.01 BTC to {pay_to} then call /agents/activate/{agent.id}",
    }


@router.post("/activate/{agent_id}")
async def activate_agent(agent_id: str, db: Session = Depends(get_db)):
    """
    Шаг 2: Агент подтверждает оплату. Проверяем блокчейн.
    """
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    if agent.status == AgentStatus.active:
        return {"message": "Agent already active", "api_key": agent.api_key}

    paid = await check_registration_payment(agent_id)
    if not paid:
        raise HTTPException(
            status_code=402,
            detail=f"Payment not received yet. Send 0.01 BTC to {agent.btc_address}",
        )

    agent.status = AgentStatus.active
    agent.registered_at = datetime.utcnow()
    db.add(FeedEvent(
        event_type="registered",
        agent_name=agent.name,
        description=f"New agent '{agent.name}' joined the marketplace",
    ))
    db.commit()

    return {
        "message": "Agent activated successfully!",
        "api_key": agent.api_key,
        "status": "active",
    }


@router.get("/me", response_model=AgentResponse)
def get_me(api_key: str, db: Session = Depends(get_db)):
    """Агент проверяет свой профиль."""
    return get_current_agent(api_key, db)
