from bstockreport.config import Settings


def test_defaults(monkeypatch):
    for var in [
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
        "ALPACA_PAPER_API_KEY",
        "ALPACA_PAPER_API_SECRET",
        "BLOASIS_DB_PATH",
        "LLM_MODEL",
        "OLLAMA_HOST",
        "LLM_TIMEOUT_S",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "COST_PER_LEG",
    ]:
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.alpaca_api_key == ""
    assert s.alpaca_secret_key == ""
    assert s.alpaca_paper_api_key == ""
    assert s.alpaca_paper_api_secret == ""
    assert s.bloasis_db_path is None
    assert s.llm_model == "qwen3-coder:30b"
    assert s.ollama_host == "http://localhost:11434"
    assert s.llm_timeout_s == 180.0
    assert s.telegram_bot_token == ""
    assert s.telegram_chat_id == ""
    assert s.cost_per_leg == 0.001


def test_env_override(monkeypatch):
    monkeypatch.setenv("ALPACA_API_KEY", "key123")
    monkeypatch.setenv("ALPACA_SECRET_KEY", "sec456")
    monkeypatch.setenv("LLM_MODEL", "llama3:8b")
    monkeypatch.setenv("OLLAMA_HOST", "http://remote:11434")
    monkeypatch.setenv("LLM_TIMEOUT_S", "60.0")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "cid")
    monkeypatch.setenv("BLOASIS_DB_PATH", "/tmp/db.sqlite")

    s = Settings()
    assert s.alpaca_api_key == "key123"
    assert s.alpaca_secret_key == "sec456"
    assert s.llm_model == "llama3:8b"
    assert s.ollama_host == "http://remote:11434"
    assert s.llm_timeout_s == 60.0
    assert s.telegram_bot_token == "tok"
    assert s.telegram_chat_id == "cid"
    assert s.bloasis_db_path == "/tmp/db.sqlite"


def test_extra_env_ignored(monkeypatch):
    monkeypatch.setenv("UNKNOWN_VAR_XYZ", "anything")
    s = Settings()
    assert not hasattr(s, "unknown_var_xyz")


def test_logs_dir_default_and_override(monkeypatch):
    from pathlib import Path

    monkeypatch.delenv("LOGS_DIR", raising=False)
    assert Settings(_env_file=None).logs_dir == Path("logs")
    monkeypatch.setenv("LOGS_DIR", "/var/tmp/bsr-logs")
    assert Settings(_env_file=None).logs_dir == Path("/var/tmp/bsr-logs")


def test_cost_per_leg_override(monkeypatch):
    monkeypatch.setenv("COST_PER_LEG", "0.0015")
    assert Settings(_env_file=None).cost_per_leg == 0.0015


def test_cost_per_leg_rejects_negative(monkeypatch):
    import pydantic
    import pytest

    monkeypatch.setenv("COST_PER_LEG", "-0.001")
    with pytest.raises(pydantic.ValidationError):
        Settings(_env_file=None)
