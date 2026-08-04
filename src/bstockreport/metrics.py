from dataclasses import dataclass


@dataclass
class SourceMetrics:
    name: str
    ok: bool
    error: str | None = None

    # 자산곡선
    days: int = 0
    equity_start: float | None = None
    equity_end: float | None = None
    ret_pct: float | None = None
    vol_pct: float | None = None
    sharpe: float | None = None
    mdd_pct: float | None = None
    small_sample: bool = False

    # 체결·수익
    fills: int | None = None
    total_orders: int | None = None
    fill_rate: float | None = None
    rt_count: int | None = None
    rt_avg_pct: float | None = None
    rt_med_pct: float | None = None
    rt_win_pct: float | None = None

    # 포지션·현금
    pos_count: int | None = None
    equity: float | None = None
    cash: float | None = None
    long_mv: float | None = None
    upl: float | None = None
    is_margin: bool = False

    # 소스별 기준선(백테스트 등) — 비교 앵커. None이면 비교줄 생략
    baseline: str | None = None
    baseline_trade_pct: float | None = None
    baseline_win_pct: float | None = None
