# M4 — LLM 해설 · 텔레그램 전송 · CLI

만들 파일 (전부 신규):

- `src/bstockreport/config.py` + `tests/test_config.py`
- `src/bstockreport/llm.py` + `tests/test_llm.py`
- `src/bstockreport/delivery.py` + `tests/test_delivery.py`
- `src/bstockreport/main.py` + `tests/test_main.py`

기존 파일은 건드리지 않는다.

---

## 1. `config.py` — 설정

`pydantic-settings` 의 `BaseSettings` 로 환경변수를 읽는다. `.env` 파일도 읽는다
(`model_config = SettingsConfigDict(env_file=".env", extra="ignore")`).

| 필드 | 기본값 |
|---|---|
| `alpaca_api_key` / `alpaca_secret_key` | `""` |
| `alpaca_paper_api_key` / `alpaca_paper_api_secret` | `""` |
| `bloasis_db_path` | `None` |
| `llm_model` | `"qwen3-coder:30b"` |
| `ollama_host` | `"http://localhost:11434"` |
| `llm_timeout_s` | `180.0` |
| `telegram_bot_token` / `telegram_chat_id` | `""` |

**하드코딩 경로 금지.** 테스트는 환경변수를 monkeypatch 해서 값이 실리는지 확인한다.

---

## 2. `llm.py` — 로컬 LLM 해설 (베스트에포트)

```python
def llm_commentary(report_text: str, *, model: str, host: str, timeout_s: float) -> str | None:
```

- Ollama `POST {host}/api/chat` 에 `{"model": ..., "stream": false, "options": {"temperature": 0.3,
  "num_predict": 500}, "messages": [{"role":"system", ...}, {"role":"user", ...}]}` 를 보낸다.
  표준 라이브러리 `urllib.request` 를 쓴다(추가 의존성 금지).
- 시스템 프롬프트: 극도로 솔직하고 냉정한 퀀트 애널리스트. 해요체. 주어진 수치만 근거로.
  자화자찬 금지. **소표본의 높은 성과는 운일 가능성이 높으니 백테스트로의 회귀가 기본 시나리오**임을 명시.
  체결률은 비용·슬리피지 검증 관점으로 해석. 마진은 리스크로 짚기. **새 수치를 지어내지 말 것.**
  불릿 3~5개.
- 응답에서 `message.content` 를 꺼내고, `<think>...</think>` 블록은 정규식으로 제거한다.
- 다음 경우 **모두 `None` 반환**(예외를 밖으로 던지지 않는다):
  응답에 `error` 키가 있을 때 / 본문이 30자 미만일 때 / 네트워크·타임아웃·JSON 파싱 실패.

### 테스트
`urllib.request.urlopen` 을 monkeypatch 한다. **실제 네트워크 호출 금지.**
정상 응답 → 문자열 / `<think>` 제거됨 / `error` 키 → None / 짧은 본문 → None / 예외 → None.

---

## 3. `delivery.py` — 텔레그램 전송

```python
def send_telegram(text: str, *, bot_token: str, chat_id: str) -> bool:
```

- `https://api.telegram.org/bot{token}/sendMessage` 에 POST.
- 텔레그램 4096자 제한 때문에 **3500자 단위로 쪼개 보낸다**. 쪼갤 때는 줄바꿈 경계에서 자른다
  (한 줄이 3500자를 넘으면 그 줄은 그대로 보낸다).
- 토큰이나 chat_id 가 비어 있으면 아무것도 보내지 않고 `False`.
- 전송 실패(예외/비200)해도 예외를 던지지 않고 `False`. 모두 성공하면 `True`.
- **토큰을 로그나 예외 메시지에 절대 넣지 않는다.**

### 테스트
`urllib.request.urlopen` monkeypatch. 3500자 넘는 입력이 2회 이상 호출로 쪼개지는지 /
줄 경계에서 잘리는지 / 빈 토큰 → False, 호출 0회 / 예외 → False.

---

## 4. `main.py` — CLI

```python
def main() -> None:
```

`argparse` 로 `run` 서브커맨드 하나. 플래그 두 개(둘 다 없으면 `--emit` 과 같게 동작):

- `--emit` : 숫자 리포트만 stdout 에 출력. LLM·텔레그램 호출 없음.
  리포트를 `<<REPORT_VERBATIM>>` 마커로 감싼다(`build(..., verbatim=True)`).
- `--push` : 리포트 + 해설을 만들어 텔레그램으로 보낸다. 마커 없음(`verbatim=False`).

동작:
1. `Settings()` 로 설정을 읽는다.
2. 소스 두 개를 만든다 —
   `AlpacaPaperSource("BStalk3r", "ALPACA_API_KEY", "ALPACA_SECRET_KEY", baseline="거래당 +0.32% · 승률 63% · Sharpe ~0.72", baseline_trade_pct=0.32, baseline_win_pct=63.0)`
   와 `AlpacaPaperSource("Bloasis", "ALPACA_PAPER_API_KEY", "ALPACA_PAPER_API_SECRET", ...)`.
   Bloasis 의 baseline 은 `load_bloasis_baseline(settings.bloasis_db_path)` 결과가 있으면 그 값으로,
   없으면 `None` 으로 둔다.
3. 각 소스의 `collect()` 를 호출하되 **예외는 잡아서** `SourceMetrics(name=..., ok=False, error=...)`
   로 바꾼다. 한 소스가 실패해도 다른 소스는 계속 간다.
4. `build(metrics, verbatim=...)` 로 본문을 만든다.
5. `--push` 일 때만: `llm_commentary(본문)` 을 시도하고, `None` 이면 각 소스의
   `rule_commentary(m)` 를 이어붙여 대체한다(**해설이 비는 일은 없어야 한다**).
   본문 아래에 해설을 덧붙인다.
6. `--push` 면 `send_telegram(...)`, 아니면 `print(...)`.

`pyproject.toml` 의 `[project.scripts]` 에 이미 `bstockreport = "bstockreport.main:main"` 이 있다.

### 테스트
`AlpacaPaperSource.collect` / `llm_commentary` / `send_telegram` 을 전부 monkeypatch 한다.
**실제 계좌·네트워크 호출 금지.**

- `--emit` → stdout 에 마커 있음, 텔레그램 호출 0회
- `--push` → 텔레그램 1회 이상 호출, 마커 없음
- 한 소스가 예외를 던져도 다른 소스 블록이 출력에 남음
- `llm_commentary` 가 `None` 이면 규칙기반 해설이 대신 들어감 (해설이 비지 않음)

---

## 검증

```
uv sync --extra dev
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest --cov=src/bstockreport --cov-fail-under=80
```
