from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ENV: str = "development"
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_ANON_KEY: str
    REDIS_URL: str = "redis://localhost:6379"
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8081"]
    JWT_SECRET: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
