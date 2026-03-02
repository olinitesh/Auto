from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    env: str = "dev"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: str = "postgresql+psycopg://autohaggle:autohaggle@localhost:5432/autohaggle"
    redis_url: str = "redis://localhost:6379/0"
    communication_service_url: str = "http://localhost:8010"
    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    sendgrid_api_key: str | None = None
    sendgrid_from_email: str | None = None
    max_radius_miles: int = 100


settings = Settings()
