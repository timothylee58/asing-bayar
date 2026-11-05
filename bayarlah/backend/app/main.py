from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import bills, game, notifications, payments, public, ws
from app.core.config import settings
from app.core.dependencies import close_redis


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_redis()


app = FastAPI(
    title="Bayar.lah API",
    version="1.0.0",
    docs_url=None if settings.is_production else "/docs",
    openapi_url=None if settings.is_production else "/openapi.json",
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(bills.router, prefix="/api/bills", tags=["bills"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(public.router, prefix="/api/public", tags=["public"])
app.include_router(game.router, prefix="/api/game", tags=["game"])
app.include_router(ws.router, tags=["websocket"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])


@app.get("/health")
async def health():
    return {"status": "ok"}
