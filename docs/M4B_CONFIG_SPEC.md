# M4b — 설정 경로 일원화 + 수집 실패 신호

## 배경 (실제 사고)

`config.py`(pydantic-settings)는 `.env` **파일**을 읽는데,
`sources/alpaca.py` 는 `os.environ[key_env]` 로 **프로세스 환경**을 읽는다.
경로가 둘이라, 셸에서 `.env` 를 export 하지 않으면 키가 어댑터에 닿지 않는다.

launchd 최소 환경에서 실제로 이 일이 났다 — 리포트는 전송됐지만 내용이
`⚠️ BStalk3r 수집 실패: 'ALPACA_API_KEY'` 였다. 게다가 **종료 코드가 0**이라
운영 스크립트는 "전송 완료"로 기록했다. 실패를 알 방법이 없었다.

고칠 것 두 가지.

---

## 1. 어댑터가 키 "값"을 받게 한다

`src/bstockreport/sources/alpaca.py` 의 생성자를 바꾼다:

```python
class AlpacaPaperSource(Source):
    def __init__(
        self,
        name: str,
        api_key: str,
        secret_key: str,
        baseline: str | None = None,
        baseline_trade_pct: float | None = None,
        baseline_win_pct: float | None = None,
    ) -> None:
```

- `key_env` / `secret_env` (환경변수 **이름**)를 받던 것을 **값**으로 바꾼다.
- `collect()` 안에서 `os.environ` 을 읽지 않는다. `os` import 도 필요 없어진다.
- 키가 빈 문자열이면 `collect()` 에서 `ValueError(f"{name}: API 키가 비어 있어요")` 를 던진다
  (호출측이 `ok=False` 로 흡수하는 계약은 그대로).

`src/bstockreport/main.py` 는 `Settings()` 에서 값을 꺼내 넘긴다:
- BStalk3r ← `settings.alpaca_api_key`, `settings.alpaca_secret_key`
- Bloasis ← `settings.alpaca_paper_api_key`, `settings.alpaca_paper_api_secret`

이러면 `.env` 만으로 동작하고 셸 export 가 필요 없어진다.

`tests/test_alpaca_source.py` 의 생성 부분을 새 시그니처에 맞게 고친다.
**기존 테스트 케이스와 커버리지는 줄이지 않는다.** 키가 비었을 때 `ValueError` 를 던지는 케이스를 추가한다.

---

## 2. 전 소스 수집 실패는 종료 코드로 알린다

`main()` 에서:
- 소스가 **하나라도** 성공하면 종료 코드 `0` (부분 실패여도 리포트는 쓸모가 있다).
- **모든** 소스가 실패하면 리포트/알림은 그대로 보내되 **종료 코드 `1`**.
  운영 스크립트가 실패를 감지할 수 있어야 한다.

`tests/test_main.py` 에 추가:
- 전 소스 실패 → `SystemExit` 코드 1, 그래도 전송은 호출됨
- 일부만 실패 → 코드 0
- 전부 성공 → 코드 0

---

## 검증

```
uv sync --extra dev
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest --cov=src/bstockreport --cov-fail-under=80
```
