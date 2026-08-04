import statistics
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from alpaca.trading.enums import OrderSide, OrderStatus

from bstockreport.sources.alpaca import AlpacaPaperSource

# ─── 헬퍼 ────────────────────────────────────────────────────────────────────


def _source(**kwargs):
    return AlpacaPaperSource(
        name="paper",
        key_env="APCA_KEY",
        secret_env="APCA_SECRET",
        **kwargs,
    )


def _order(symbol, side, qty, price=None, status=OrderStatus.FILLED, t=0):
    o = MagicMock()
    o.symbol = symbol
    o.side = side
    o.filled_qty = Decimal(str(qty))
    o.filled_avg_price = Decimal(str(price)) if price is not None else None
    o.status = status
    o.submitted_at = datetime(2024, 1, 1, 0, t, 0, tzinfo=UTC)
    return o


def _position(market_value, unrealized_pl):
    p = MagicMock()
    p.market_value = str(market_value)
    p.unrealized_pl = str(unrealized_pl)
    return p


def _account(equity, cash):
    a = MagicMock()
    a.equity = str(equity)
    a.cash = str(cash)
    return a


def _history(equity_list):
    h = MagicMock()
    h.equity = equity_list
    return h


def _setup(inst, *, equity, orders, positions, acct_equity, acct_cash):
    inst.get_portfolio_history.return_value = _history(equity)
    inst.get_orders.return_value = orders
    inst.get_all_positions.return_value = positions
    inst.get_account.return_value = _account(acct_equity, acct_cash)


# ─── 픽스처 ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv("APCA_KEY", "k")
    monkeypatch.setenv("APCA_SECRET", "s")


# ─── 정상 수집 ────────────────────────────────────────────────────────────────


def test_happy_path():
    """65개 equity 포인트, 왕복 1건, 포지션 1개 → 모든 지표 채워짐."""
    eq = [100.0 + i for i in range(65)]
    buy = _order("AAPL", OrderSide.BUY, 10, 100.0, t=0)
    sell = _order("AAPL", OrderSide.SELL, 10, 120.0, t=1)
    pos = _position(5000.0, 200.0)

    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(
            inst,
            equity=eq,
            orders=[buy, sell],
            positions=[pos],
            acct_equity=50000,
            acct_cash=10000,
        )
        m = _source(baseline="SPY", baseline_trade_pct=40.0, baseline_win_pct=55.0).collect()

    assert m.ok is True
    assert m.name == "paper"
    assert m.days == 65
    assert m.equity_start == pytest.approx(100.0)
    assert m.equity_end == pytest.approx(164.0)
    assert m.ret_pct == pytest.approx(64.0)
    assert m.vol_pct is not None and m.vol_pct >= 0
    assert m.sharpe is not None
    assert m.mdd_pct == pytest.approx(0.0)
    assert m.small_sample is False

    assert m.fills == 2
    assert m.total_orders == 2
    assert m.fill_rate == pytest.approx(100.0)
    assert m.rt_count == 1
    assert m.rt_avg_pct == pytest.approx(20.0)
    assert m.rt_win_pct == pytest.approx(100.0)

    assert m.pos_count == 1
    assert m.equity == pytest.approx(50000.0)
    assert m.cash == pytest.approx(10000.0)
    assert m.long_mv == pytest.approx(5000.0)
    assert m.upl == pytest.approx(200.0)
    assert m.is_margin is False

    assert m.baseline == "SPY"
    assert m.baseline_trade_pct == pytest.approx(40.0)
    assert m.baseline_win_pct == pytest.approx(55.0)


# ─── FIFO 왕복 매칭 ──────────────────────────────────────────────────────────


def test_fifo_partial_sell():
    """부분 매도: 로트1 전량 + 로트2 일부 → 수익률 2건."""
    b1 = _order("AAPL", OrderSide.BUY, 10, 100.0, t=0)
    b2 = _order("AAPL", OrderSide.BUY, 5, 110.0, t=1)
    s = _order("AAPL", OrderSide.SELL, 12, 120.0, t=2)

    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(
            inst,
            equity=[100.0, 101.0],
            orders=[b1, b2, s],
            positions=[],
            acct_equity=10000,
            acct_cash=5000,
        )
        m = _source().collect()

    expected = [0.2, 10 / 110]
    assert m.rt_count == 2
    assert m.rt_avg_pct == pytest.approx(statistics.mean(expected) * 100)
    assert m.rt_med_pct == pytest.approx(statistics.median(expected) * 100)
    assert m.rt_win_pct == pytest.approx(100.0)


def test_fifo_loss_round_trip():
    """매도가 < 매수가이면 수익률 음수, rt_win_pct = 0."""
    b = _order("TSLA", OrderSide.BUY, 5, 200.0, t=0)
    s = _order("TSLA", OrderSide.SELL, 5, 180.0, t=1)

    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(
            inst,
            equity=[100.0, 101.0],
            orders=[b, s],
            positions=[],
            acct_equity=10000,
            acct_cash=5000,
        )
        m = _source().collect()

    assert m.rt_count == 1
    assert m.rt_avg_pct == pytest.approx((180 - 200) / 200 * 100)
    assert m.rt_win_pct == pytest.approx(0.0)


# ─── 미체결 주문 제외 ─────────────────────────────────────────────────────────


def test_unfilled_orders_excluded():
    """canceled 주문과 filled_avg_price=None 주문은 체결 집계에서 빠진다."""
    filled1 = _order("AAPL", OrderSide.BUY, 10, 100.0, t=0)
    filled2 = _order("AAPL", OrderSide.BUY, 5, 110.0, t=1)
    canceled = _order("MSFT", OrderSide.BUY, 3, status=OrderStatus.CANCELED, t=2)
    no_price = _order("GOOG", OrderSide.BUY, 2, price=None, status=OrderStatus.FILLED, t=3)

    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(
            inst,
            equity=[100.0, 101.0],
            orders=[filled1, filled2, canceled, no_price],
            positions=[],
            acct_equity=10000,
            acct_cash=5000,
        )
        m = _source().collect()

    assert m.total_orders == 4
    assert m.fills == 2
    assert m.fill_rate == pytest.approx(50.0)


# ─── is_margin ───────────────────────────────────────────────────────────────


def test_negative_cash_is_margin():
    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(
            inst,
            equity=[100.0, 101.0],
            orders=[],
            positions=[],
            acct_equity=50000,
            acct_cash=-500,
        )
        m = _source().collect()

    assert m.is_margin is True
    assert m.cash == pytest.approx(-500.0)


def test_positive_cash_not_margin():
    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(
            inst,
            equity=[100.0, 101.0],
            orders=[],
            positions=[],
            acct_equity=50000,
            acct_cash=1000,
        )
        m = _source().collect()

    assert m.is_margin is False


# ─── small_sample ─────────────────────────────────────────────────────────────


def test_small_sample_true_when_days_lt_60():
    eq = [100.0 + i for i in range(30)]

    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(inst, equity=eq, orders=[], positions=[], acct_equity=10000, acct_cash=5000)
        m = _source().collect()

    assert m.days == 30
    assert m.small_sample is True


def test_small_sample_false_when_days_gte_60():
    eq = [100.0 + i for i in range(60)]

    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(inst, equity=eq, orders=[], positions=[], acct_equity=10000, acct_cash=5000)
        m = _source().collect()

    assert m.days == 60
    assert m.small_sample is False


# ─── 포지션 0개 / 왕복 0건 ────────────────────────────────────────────────────


def test_no_positions_no_roundtrips():
    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(
            inst,
            equity=[100.0, 101.0],
            orders=[],
            positions=[],
            acct_equity=10000,
            acct_cash=5000,
        )
        m = _source().collect()

    assert m.pos_count == 0
    assert m.long_mv == pytest.approx(0.0)
    assert m.upl == pytest.approx(0.0)
    assert m.rt_count is None
    assert m.rt_avg_pct is None
    assert m.rt_med_pct is None
    assert m.rt_win_pct is None


# ─── equity 포인트 부족 ───────────────────────────────────────────────────────


def test_equity_less_than_two_points_gives_none_metrics():
    """equity 포인트 1개이면 수익률·변동성·샤프·MDD가 None."""
    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(inst, equity=[100.0], orders=[], positions=[], acct_equity=10000, acct_cash=5000)
        m = _source().collect()

    assert m.days == 1
    assert m.small_sample is True
    assert m.ret_pct is None
    assert m.vol_pct is None
    assert m.sharpe is None
    assert m.mdd_pct is None


def test_equity_none_and_zero_filtered():
    """equity 리스트의 None·0은 유효 포인트에서 제외된다."""
    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(
            inst,
            equity=[None, 0, 100.0, None, 200.0],
            orders=[],
            positions=[],
            acct_equity=10000,
            acct_cash=5000,
        )
        m = _source().collect()

    assert m.days == 2
    assert m.equity_start == pytest.approx(100.0)
    assert m.equity_end == pytest.approx(200.0)
    assert m.ret_pct == pytest.approx(100.0)


# ─── MDD ─────────────────────────────────────────────────────────────────────


def test_mdd_negative_when_drawdown_exists():
    """고점 이후 낙폭: peak=100, 최저=80 → mdd_pct = -20.0."""
    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(
            inst,
            equity=[100.0, 80.0, 90.0],
            orders=[],
            positions=[],
            acct_equity=10000,
            acct_cash=5000,
        )
        m = _source().collect()

    assert m.mdd_pct == pytest.approx(-20.0)


# ─── TradingClient 파라미터 검증 ─────────────────────────────────────────────


def test_trading_client_created_with_paper_true(monkeypatch):
    monkeypatch.setenv("MY_KEY", "abc")
    monkeypatch.setenv("MY_SEC", "xyz")

    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        _setup(
            inst,
            equity=[100.0, 101.0],
            orders=[],
            positions=[],
            acct_equity=10000,
            acct_cash=5000,
        )
        AlpacaPaperSource(name="t", key_env="MY_KEY", secret_env="MY_SEC").collect()

    MC.assert_called_once_with("abc", "xyz", paper=True)
