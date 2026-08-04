from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper_api_key: str = ""
    alpaca_paper_api_secret: str = ""
    bloasis_db_path: str | None = None
    llm_model: str = "qwen3-coder:30b"
    ollama_host: str = "http://localhost:11434"
    llm_timeout_s: float = 180.0
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
