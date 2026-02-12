"""Load settings from env."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model_enhance: str = "gpt-4o-mini"
    openai_model_agent: str = "gpt-4o-mini"

    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    webhook_verify_token: str = ""
    whatsapp_app_id: str | int | None = None  # optional; for pywa callback registration & update validation
    whatsapp_app_secret: str | None = None

    base_url: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
