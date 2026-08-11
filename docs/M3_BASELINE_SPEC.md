# M3 — bloasis 백테스트 기준선 + 소표본 판정 교정

만들/고칠 파일:

- **신규** `src/bstockreport/baseline.py`
- **신규** `tests/test_baseline.py`
- **수정** `src/bstockreport/sources/alpaca.py` (소표본 판정 한 줄)
- **수정** `tests/test_alpaca_source.py` (소표본 케이스 보강)

다른 파일은 건드리지 않는다.

---

## 1. `baseline.py` — bloasis.db 에서 백테스트 기준선 읽기

bloasis 프로젝트는 백테스트 결과를 SQLite `backtest_runs` 테이블에 남긴다.
그 최신 행을 **읽기 전용으로** 읽어 리포트의 기준선 문자열/수치로 쓴다.

```python
@dataclass(frozen=True)
class Baseline:
    text: str  # 사람이 읽는 한 줄 (SourceMetrics.baseline 에 넣는다)
    trade_pct: float | None  # 거래당 평균 수익률 %
    win_pct: float | None  # 승률 %


def load_bloasis_baseline(db_path: str | None = None) -> Baseline | None: ...
```

동작:
- `db_path` 가 없으면 환경변수 `BLOASIS_DB_PATH` 를 쓴다. 그것도 없으면 `None` 반환.
- 파일이 없으면 `None` 반환 (예외 금지).
- **읽기 전용으로 연다**: `sqlite3.connect(f"file:{path}?mode=ro", uri=True)`.
- `backtest_runs` 테이블이 없거나 행이 0개면 `None` 반환.
- 가장 최근 행 하나를 고른다(`created_at` 컬럼이 있으면 그 내림차순, 없으면 `rowid` 내림차순).
- 그 행에서 쓸 수 있는 값만 뽑는다: 승률(`win_rate`), 샤프(`sharpe`), 최대낙폭(`max_drawdown`).
  컬럼이 없으면 그 값은 `None` 로 두고 나머지로 진행한다.
- `win_rate` 가 0~1 사이 소수면 ×100 해서 %로 만든다. 이미 1보다 크면 그대로 %로 본다.
- `text` 는 있는 값만 ` · ` 로 이어 만든다. 예: `"백테스트: 승률 58% · Sharpe 1.33"`.
  쓸 값이 하나도 없으면 `None` 반환.
- **어떤 예외도 밖으로 던지지 않는다** — 실패하면 `None`. 기준선은 있으면 좋은 정보이지 필수가 아니다.

`trade_pct` 는 `backtest_runs` 에 대응 컬럼이 있으면 쓰고, 없으면 `None`.

### 테스트 (`tests/test_baseline.py`)
`tmp_path` 에 임시 SQLite 를 만들어 검증한다. **실제 bloasis.db 를 읽지 않는다.**

- 정상: 컬럼이 다 있는 행 → `text`/`win_pct`/`trade_pct` 가 채워짐
- `win_rate` 가 0.58 이면 58.0 으로 변환됨
- `win_rate` 가 58 이면 그대로 58.0
- 테이블 없음 → `None`
- 행 0개 → `None`
- 파일 경로가 존재하지 않음 → `None`
- `db_path`/`BLOASIS_DB_PATH` 둘 다 없음 → `None`
- 일부 컬럼만 존재 → 있는 값으로만 `text` 구성
- DB 가 손상되어 예외가 나도 `None` (예외가 밖으로 새지 않음)

---

## 2. 소표본 판정 교정 (`sources/alpaca.py`)

**현재 결함**: `small_sample` 을 *거래일 수*(`days < 60`)로만 판정한다.
그래서 이제 막 시작한 계좌(왕복거래 **2건**)인데도 equity 이력이 60일을 넘으면
소표본 경고가 뜨지 않는다. 표본이 작은 것은 날짜가 아니라 **거래 수**다.

고칠 것 — 둘 중 **하나라도** 해당하면 `small_sample=True`:

```
days < 60  또는  (rt_count 가 있고 rt_count < 30)
```

왕복거래가 하나도 없으면(`rt_count is None`) 날짜 기준만 본다.

### 테스트 보강 (`tests/test_alpaca_source.py`)
기존 케이스는 그대로 두고 추가한다:

- `days >= 60` 이지만 왕복 2건 → `small_sample=True` (이번에 고치는 실제 상황)
- `days >= 60` 이고 왕복 30건 이상 → `small_sample=False`
- 왕복 0건이고 `days >= 60` → `small_sample=False`

---

## 검증

```
uv sync --extra dev
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest --cov=src/bstockreport --cov-fail-under=80
```
