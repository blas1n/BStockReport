# M2 — Alpaca 페이퍼 계좌 어댑터 사양

만들 파일 **두 개만**. 다른 파일은 건드리지 않는다.

- `src/bstockreport/sources/alpaca.py`
- `tests/test_alpaca_source.py`

## 클래스

```python
class AlpacaPaperSource(Source):
    def __init__(
        self,
        name: str,
        key_env: str,
        secret_env: str,
        baseline: str | None = None,
        baseline_trade_pct: float | None = None,
        baseline_win_pct: float | None = None,
    ) -> None: ...
```

API 키는 `os.environ[key_env]` / `os.environ[secret_env]` 로 읽는다. **하드코딩 금지.**
클라이언트는 `TradingClient(key, secret, paper=True)` (alpaca-py).

## `collect() -> SourceMetrics`

성공하면 `ok=True`. **예외가 나면 그대로 던진다** — 호출측이 `ok=False, error=...` 로 흡수하는 계약이다.

### 1. 자산곡선

`get_portfolio_history(GetPortfolioHistoryRequest(period="3M", timeframe="1D"))` 의 `equity` 리스트
(None/0 값은 제외)에서:

| 필드 | 계산 |
|---|---|
| `days` | equity 포인트 개수 |
| `equity_start` / `equity_end` | 첫 값 / 마지막 값 |
| `ret_pct` | `(end/start - 1) * 100` |
| `vol_pct` | 일간수익률 모표준편차 × √252 × 100 |
| `sharpe` | (일간수익률 평균 / 모표준편차) × √252 |
| `mdd_pct` | 고점 대비 최대 낙폭 (%, 음수) |
| `small_sample` | `days < 60` |

표준편차가 0이면 `sharpe`는 0.0. 포인트가 2개 미만이면 이 지표들은 `None`으로 둔다.

### 2. 체결 · 왕복거래

`get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500))` 로 전부 가져온 뒤,
**`status`가 filled 이고 `filled_avg_price` 가 있는 것만** 체결로 센다.

- `fills` = 체결 건수, `total_orders` = 전체 건수, `fill_rate` = 체결/전체 × 100

**FIFO 왕복 매칭** — 체결을 `submitted_at` 오름차순으로 훑으며 심볼별로:
- 매수: `(수량, 체결가)` 로트를 큐 뒤에 넣는다
- 매도: 큐 앞에서부터 차감하며, 차감한 각 로트마다 수익률 `(매도가 - 로트가) / 로트가` 를 기록한다
  (부분 매도면 로트에 남은 수량을 남겨둔다)

기록된 수익률 리스트에서 `rt_count`, `rt_avg_pct`, `rt_med_pct`, `rt_win_pct`(>0 비율 × 100)를 낸다.
왕복이 하나도 없으면 이 네 필드는 `None`.

### 3. 포지션 · 현금

`get_account()` + `get_all_positions()` 에서 `pos_count`, `equity`, `cash`, `long_mv`,
`upl`(각 포지션 `unrealized_pl` 합). `cash < 0` 이면 `is_margin=True`.

### 4. baseline

생성자로 받은 `baseline` / `baseline_trade_pct` / `baseline_win_pct` 를 그대로 `SourceMetrics` 에 담는다.

## 테스트 (`tests/test_alpaca_source.py`)

**네트워크 호출 금지** — `TradingClient` 를 `unittest.mock` 으로 전부 모킹한다.

- 정상 수집: 각 지표가 기대값으로 채워짐
- FIFO 왕복: 부분 매도가 섞인 케이스에서 수익률 리스트가 맞음
- 미체결 주문은 체결 집계에서 제외됨
- `cash < 0` → `is_margin=True`
- `days < 60` → `small_sample=True`
- 포지션 0개 / 왕복 0건 → 해당 필드 `None` 또는 0

## 검증

```
uv sync --extra dev
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run pytest --cov=src/bstockreport --cov-fail-under=80
```
