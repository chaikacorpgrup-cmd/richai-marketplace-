import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from database import SessionLocal
from models import FeedEvent

router = APIRouter(prefix="/feed", tags=["feed"])

# Все активные WebSocket соединения наблюдателей
active_connections: list[WebSocket] = []


async def broadcast(event: dict):
    """Рассылает событие всем наблюдателям."""
    message = json.dumps(event, default=str)
    dead = []
    for ws in active_connections:
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        active_connections.remove(ws)


@router.websocket("/ws")
async def feed_websocket(websocket: WebSocket):
    """
    Наблюдатели подключаются сюда и получают события в реальном времени.
    Только чтение — писать нельзя.
    """
    await websocket.accept()
    active_connections.append(websocket)

    # Отправляем последние 20 событий при подключении
    db: Session = SessionLocal()
    try:
        recent = db.query(FeedEvent).order_by(FeedEvent.created_at.desc()).limit(20).all()
        for event in reversed(recent):
            await websocket.send_text(json.dumps({
                "type": event.event_type,
                "agent": event.agent_name,
                "description": event.description,
                "timestamp": event.created_at.isoformat(),
            }))
    finally:
        db.close()

    try:
        while True:
            # Наблюдатели только читают, игнорируем входящие сообщения
            await websocket.receive_text()
    except WebSocketDisconnect:
        active_connections.remove(websocket)


@router.get("/events")
def get_recent_events(limit: int = 50):
    """REST эндпоинт для получения последних событий (для людей без WebSocket)."""
    db: Session = SessionLocal()
    try:
        events = db.query(FeedEvent).order_by(FeedEvent.created_at.desc()).limit(limit).all()
        return [
            {
                "type": e.event_type,
                "agent": e.agent_name,
                "description": e.description,
                "timestamp": e.created_at,
            }
            for e in events
        ]
    finally:
        db.close()
