import statistics
from dataclasses import dataclass
from datetime import date, timedelta

WEEK_DAYS = 7


@dataclass
class WeeklyMetrics:
    """최근 7일(달력일) 창. start~end 는 창에 포함되는 날짜."""

    start: date
    end: date
    equity_start: float | None
    equity_end: float | None
    ret_pct: float | None
    rt_count: int
    rt_avg_pct: float | None
    rt_win_pct: float | None


def weekly_metrics(
    equity: list[tuple[date, float]], round_trips: list[tuple[date, float]]
) -> WeeklyMetrics | None:
    """마지막 equity 날짜로 끝나는 7달력일 창의 지표.

    - 자산 기준값: cutoff(= 끝 - 7일) 이하의 마지막 종가. 없으면 창 안 첫 포인트.
    - 왕복: 청산일(매도 체결일)이 cutoff < d <= 끝 인 것. 수익률은 소수(0.01 = 1%).
    """
    if not equity:
        return None
    pts = sorted(equity, key=lambda p: p[0])
    end = pts[-1][0]
    cutoff = end - timedelta(days=WEEK_DAYS)

    before = [p for p in pts if p[0] <= cutoff]
    base = before[-1] if before else pts[0]
    if base is pts[-1]:
        equity_start = equity_end = ret_pct = None
    else:
        equity_start = base[1]
        equity_end = pts[-1][1]
        ret_pct = (equity_end / equity_start - 1) * 100

    rets = [r for d, r in round_trips if cutoff < d <= end]
    rt_count = len(rets)
    rt_avg_pct = statistics.mean(rets) * 100 if rets else None
    rt_win_pct = sum(1 for r in rets if r > 0) / rt_count * 100 if rets else None

    return WeeklyMetrics(
        start=cutoff + timedelta(days=1),
        end=end,
        equity_start=equity_start,
        equity_end=equity_end,
        ret_pct=ret_pct,
        rt_count=rt_count,
        rt_avg_pct=rt_avg_pct,
        rt_win_pct=rt_win_pct,
    )


@dataclass
class RepricedRoundTrips:
    """페이퍼 왕복을 연구 비용 가정으로 다시 매긴 것. 수익률은 %(1.0 = 1%)."""

    cost_per_leg: float
    rt_count: int
    avg_pct: float | None
    win_pct: float | None


def repriced_round_trips(returns: list[float], cost_per_leg: float) -> RepricedRoundTrips:
    """페이퍼 체결은 그대로 두고 왕복마다 2 × cost_per_leg 를 뺀다(returns 는 소수).

    페이퍼 체결 비용(~3bp 왕복)이 실제보다 싸서, 연구 가정(편도 10bp)으로 다시 매긴 숫자를
    옆에 둔다. 비용 이후 0 은 승리로 세지 않는다. 왕복이 없으면 나누지 않고 None.
    """
    net = [r - 2 * cost_per_leg for r in returns]
    if not net:
        return RepricedRoundTrips(cost_per_leg=cost_per_leg, rt_count=0, avg_pct=None, win_pct=None)
    return RepricedRoundTrips(
        cost_per_leg=cost_per_leg,
        rt_count=len(net),
        avg_pct=statistics.mean(net) * 100,
        win_pct=sum(1 for r in net if r > 0) / len(net) * 100,
    )


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

    # 집계 기간
    period_start: date | None = None
    period_end: date | None = None

    # 이번 주(최근 7일) — 3개월 지표와 별도
    week: WeeklyMetrics | None = None

    # 연구 비용 가정으로 다시 매긴 왕복 — None 이면 줄 생략
    repriced: RepricedRoundTrips | None = None
