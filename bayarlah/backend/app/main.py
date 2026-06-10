from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.api import bills, payments, game, ws, notifications


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Bayar.lah API",
    version="1.0.0",
    docs_url="/docs" if settings.ENV != "production" else None,
    redoc_url=None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(bills.router, prefix="/api/bills", tags=["bills"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(game.router, prefix="/api/game", tags=["game"])
app.include_router(ws.router, tags=["websocket"])
app.include_router(notifications.router, prefix="/api/notifications", tags=["notifications"])


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.ENV}
