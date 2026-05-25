from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://wcguess:wcguess@localhost:5432/wcguess"
    database_url_sync: str = "postgresql://wcguess:wcguess@localhost:5432/wcguess"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"

    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-4-20250514"
    mock_llm: bool = True

    football_data_api_key: str = ""
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"

    max_rounds: int = 30
    deliberation_timeout_seconds: int = 2700
    prompt_version: str = "v1"
    graph_version: str = "v1"

    hot_match_pregen_hours: int = 24
    hot_match_ids: str = "fifa-400021543,fifa-400021541,fifa-400021496"


@lru_cache
def get_settings() -> Settings:
    return Settings()
