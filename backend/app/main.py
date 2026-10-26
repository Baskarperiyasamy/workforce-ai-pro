import asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func
from . import models, routes_ai, routes_auth, routes_hr, seed
from .core import Base, Session, decode_token, engine
from .models import MonitorLog, Notification

app = FastAPI(title="WorkForce AI Pro API", version="1.0.0", description="HR attrition prediction and workforce intelligence platform")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_methods=["*"], allow_headers=["*"], allow_credentials=True)
for r in (routes_auth.router, routes_hr.router, routes_ai.router):
    app.include_router(r)


@app.on_event("startup")
def startup():
    Base.metadata.create_all(engine)
    seed.run()


@app.get("/api/health", tags=["system"])
def health():
    return {"status": "ok"}


def newest(uid):
    db = Session()
    try:
        n = db.query(func.coalesce(func.max(Notification.id), 0)).filter(Notification.user_id == uid).scalar()
        m = db.query(func.coalesce(func.max(MonitorLog.id), 0)).scalar()
        return n, m
    finally:
        db.close()


def fresh(uid, last_n):
    db = Session()
    try:
        return [{"id": n.id, "message": n.message, "priority": n.priority, "kind": n.kind} for n in db.query(Notification).filter(Notification.user_id == uid, Notification.id > last_n).order_by(Notification.id)]
    finally:
        db.close()


@app.websocket("/ws")
async def live(sock: WebSocket, token: str):
    try:
        uid = int(decode_token(token)["sub"])
    except HTTPException:
        await sock.close(code=4401)
        return
    await sock.accept()
    last_n, last_m = await run_in_threadpool(newest, uid)
    try:
        while True:
            await asyncio.sleep(2)
            n, m = await run_in_threadpool(newest, uid)
            if n > last_n or m > last_m:
                items = await run_in_threadpool(fresh, uid, last_n)
                await sock.send_json({"type": "update", "notifications": items})
                last_n, last_m = n, m
    except (WebSocketDisconnect, RuntimeError):
        return
