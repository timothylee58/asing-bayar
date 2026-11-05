from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENV: str = "development"
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_ANON_KEY: str
    REDIS_URL: str = "redis://localhost:6379"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8081"]
    JWT_SECRET: str = ""  # unused: tokens are verified by Supabase Auth; kept so old .env files load
    SUPABASE_STORAGE_BUCKET: str = "receipts"

    # Public URLs. WEB_BASE_URL is the share-page origin (links sent over WhatsApp);
    # BACKEND_PUBLIC_URL is this API's own origin (payment-gateway webhooks call it).
    WEB_BASE_URL: str = "http://localhost:3000"
    BACKEND_PUBLIC_URL: str = "http://localhost:8000"

    # Payment gateway (Level 2) — optional, app works without these
    PAYMENT_GATEWAY_ENABLED: bool = False
    PAYMENT_GATEWAY_PROVIDER: str = "hitpay"  # "hitpay" | "stripe" | "airwallex"
    HITPAY_API_KEY: str = ""
    HITPAY_WEBHOOK_SALT: str = ""
    HITPAY_SANDBOX: bool = True

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @model_validator(mode="after")
    def _validate_gateway_config(self) -> "Settings":
        """Refuse to boot with a half-configured payment gateway.

        A gateway that is "enabled" without its secrets would silently fall back
        to the stub gateway, which accepts unsigned webhooks.
        """
        if not self.PAYMENT_GATEWAY_ENABLED:
            return self
        missing = [
            name
            for name in ("HITPAY_API_KEY", "HITPAY_WEBHOOK_SALT")
            if not getattr(self, name)
        ]
        if missing:
            raise ValueError(
                "PAYMENT_GATEWAY_ENABLED=true requires: " + ", ".join(missing)
            )
        if self.is_production:
            if self.HITPAY_SANDBOX:
                raise ValueError("HITPAY_SANDBOX must be false when ENV=production")
            if "localhost" in self.BACKEND_PUBLIC_URL:
                raise ValueError(
                    "BACKEND_PUBLIC_URL must be the public API origin when "
                    "the payment gateway is enabled in production"
                )
        return self


settings = Settings()
