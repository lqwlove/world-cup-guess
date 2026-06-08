from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://wcguess:wcguess@localhost:5432/wcguess"
    database_url_sync: str = "postgresql://wcguess:wcguess@localhost:5432/wcguess"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:3000"

    anthropic_api_key: str = ""
    # OpenAI 兼容接口：OpenAI / DeepSeek / 火山引擎方舟 等共用
    openai_api_key: str = ""
    openai_api_base: str = ""
    # openai | deepseek | volcengine | anthropic
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-chat"
    mock_llm: bool = True

    football_data_api_key: str = ""
    football_data_base_url: str = "https://api.football-data.org/v4"
    football_data_competition: str = "WC"
    polymarket_gamma_url: str = "https://gamma-api.polymarket.com"

    # Web search（Tavily 优先；未配置时回退 DuckDuckGo）
    tavily_api_key: str = ""
    web_search_enabled: bool = True
    web_search_max_results: int = 5

    max_rounds: int = 30
    deliberation_timeout_seconds: int = 2700
    prompt_version: str = "v1"
    graph_version: str = "v2"
    graph_checkpoint_enabled: bool = True

    hot_match_pregen_hours: int = 24
    hot_match_ids: str = "fifa-400021543,fifa-400021541,fifa-400021496"


@lru_cache
def get_settings() -> Settings:
    return Settings()
