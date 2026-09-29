from pathlib import Path

from pydantic import Field
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
    # --push 가 보낸 본문을 남기는 곳. launchd 래퍼의 weekly-*.log 와 같은 디렉터리.
    logs_dir: Path = Path("logs")
    # 왕복 재계산에 쓰는 편도 비용(소수, 0.001 = 10bp). 연구·백테스트 가정과 같게 둔다.
    cost_per_leg: float = Field(default=0.001, ge=0)
