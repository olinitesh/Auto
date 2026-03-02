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
    marketcheck_api_key: str | None = None
    marketcheck_base_url: str = "https://api.marketcheck.com/v2/search/car/active"
    dealer_direct_scrape_enabled: bool = False
    toyota_graphql_endpoint: str = "https://api.search-inventory.toyota.com/graphql"
    toyota_graphql_origin: str = "https://www.toyota.com"
    toyota_graphql_referer: str = "https://www.toyota.com/"
    toyota_graphql_user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
    toyota_x_api_key: str | None = None
    toyota_x_aws_waf_token: str | None = None
    toyota_graphql_cookie: str | None = None
    toyota_graphql_extra_headers_json: str | None = None
    toyota_graphql_debug: bool = False
    max_radius_miles: int = 100


settings = Settings()
