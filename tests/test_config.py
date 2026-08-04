from bstockreport.config import Settings


def test_defaults():
    s = Settings()
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
