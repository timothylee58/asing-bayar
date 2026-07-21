from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str = "development"
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_ANON_KEY: str
    REDIS_URL: str = "redis://localhost:6379"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8081"]
    JWT_SECRET: str = ""
    SUPABASE_STORAGE_BUCKET: str = "receipts"

    # Payment gateway (Level 2) — optional, app works without these
    PAYMENT_GATEWAY_ENABLED: bool = False
    PAYMENT_GATEWAY_PROVIDER: str = "hitpay"  # "hitpay" | "stripe" | "airwallex"
    HITPAY_API_KEY: str = ""
    HITPAY_WEBHOOK_SALT: str = ""
    HITPAY_SANDBOX: bool = True
    WEB_BASE_URL: str = "http://localhost:3000"

    class Config:
        env_file = ".env"


settings = Settings()
