import math
import statistics
from collections import defaultdict, deque
from datetime import UTC, datetime

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, OrderStatus, QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest, GetPortfolioHistoryRequest

from bstockreport.metrics import SourceMetrics
from bstockreport.sources.base import Source


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
        self._name = name
        self._api_key = api_key
        self._secret_key = secret_key
        self._baseline = baseline
        self._baseline_trade_pct = baseline_trade_pct
        self._baseline_win_pct = baseline_win_pct

    @property
    def name(self) -> str:
        return self._name

    def collect(self) -> SourceMetrics:
        if not self._api_key:
            raise ValueError(f"{self._name}: API 키가 비어 있어요")
        client = TradingClient(self._api_key, self._secret_key, paper=True)

        # 1. 자산곡선
        hist = client.get_portfolio_history(GetPortfolioHistoryRequest(period="3M", timeframe="1D"))
        raw_timestamps = hist.timestamp if isinstance(hist.timestamp, list) else []
        equity_raw = hist.equity or []
        equity_pts = [e for e in equity_raw if e]

        if len(equity_pts) >= 2:
            days = len(equity_pts)
            equity_start = float(equity_pts[0])
            equity_end = float(equity_pts[-1])
            ret_pct = (equity_end / equity_start - 1) * 100

            daily_returns = [
                (equity_pts[i] - equity_pts[i - 1]) / equity_pts[i - 1]
                for i in range(1, len(equity_pts))
            ]
            mean_ret = statistics.mean(daily_returns)
            stdev_ret = statistics.stdev(daily_returns) if len(daily_returns) >= 2 else 0.0

            vol_pct = stdev_ret * math.sqrt(252) * 100
            sharpe = (mean_ret / stdev_ret) * math.sqrt(252) if stdev_ret != 0 else 0.0

            peak = equity_pts[0]
            mdd = 0.0
            for e in equity_pts:
                if e > peak:
                    peak = e
                dd = (e - peak) / peak
                if dd < mdd:
                    mdd = dd
            mdd_pct = mdd * 100
        else:
            days = len(equity_pts)
            equity_start = None
            equity_end = None
            ret_pct = None
            vol_pct = None
            sharpe = None
            mdd_pct = None

        # 2. 체결·왕복거래
        orders = client.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=500))
        total_orders = len(orders)
        filled = [
            o for o in orders if o.status == OrderStatus.FILLED and o.filled_avg_price is not None
        ]
        fills = len(filled)
        fill_rate = (fills / total_orders * 100) if total_orders > 0 else 0.0

        # FIFO 왕복 매칭
        filled_sorted = sorted(filled, key=lambda o: o.submitted_at)
        buy_queues: dict[str, deque] = defaultdict(deque)
        round_trip_returns: list[float] = []

        for order in filled_sorted:
            symbol = order.symbol
            qty = float(order.filled_qty)
            price = float(order.filled_avg_price)

            if order.side == OrderSide.BUY:
                buy_queues[symbol].append([qty, price])
            elif order.side == OrderSide.SELL:
                remaining = qty
                while remaining > 0 and buy_queues[symbol]:
                    lot = buy_queues[symbol][0]
                    round_trip_returns.append((price - lot[1]) / lot[1])
                    if lot[0] <= remaining:
                        remaining -= lot[0]
                        buy_queues[symbol].popleft()
                    else:
                        lot[0] -= remaining
                        remaining = 0

        if round_trip_returns:
            rt_count = len(round_trip_returns)
            rt_avg_pct = statistics.mean(round_trip_returns) * 100
            rt_med_pct = statistics.median(round_trip_returns) * 100
            rt_win_pct = sum(1 for r in round_trip_returns if r > 0) / rt_count * 100
        else:
            rt_count = None
            rt_avg_pct = None
            rt_med_pct = None
            rt_win_pct = None

        small_sample = days < 60 or (rt_count is not None and rt_count < 30)

        # 집계 기간
        valid_ts = [t for t, e in zip(raw_timestamps, equity_raw, strict=False) if e]
        if valid_ts:
            period_start = datetime.fromtimestamp(valid_ts[0], tz=UTC).date()
            period_end = datetime.fromtimestamp(valid_ts[-1], tz=UTC).date()
        else:
            period_start = None
            period_end = None

        # 3. 포지션·현금
        account = client.get_account()
        positions = client.get_all_positions()

        pos_count = len(positions)
        equity_acc = float(account.equity)
        cash = float(account.cash)
        long_mv = sum(float(p.market_value) for p in positions)
        upl = sum(float(p.unrealized_pl) for p in positions)
        is_margin = cash < 0

        return SourceMetrics(
            name=self._name,
            ok=True,
            days=days,
            equity_start=equity_start,
            equity_end=equity_end,
            ret_pct=ret_pct,
            vol_pct=vol_pct,
            sharpe=sharpe,
            mdd_pct=mdd_pct,
            small_sample=small_sample,
            fills=fills,
            total_orders=total_orders,
            fill_rate=fill_rate,
            rt_count=rt_count,
            rt_avg_pct=rt_avg_pct,
            rt_med_pct=rt_med_pct,
            rt_win_pct=rt_win_pct,
            pos_count=pos_count,
            equity=equity_acc,
            cash=cash,
            long_mv=long_mv,
            upl=upl,
            is_margin=is_margin,
            baseline=self._baseline,
            baseline_trade_pct=self._baseline_trade_pct,
            baseline_win_pct=self._baseline_win_pct,
            period_start=period_start,
            period_end=period_end,
        )
