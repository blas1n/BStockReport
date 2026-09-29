"""이번 주(최근 7일) 지표 — 순수 계산. 계좌·네트워크 접근 없음."""

from datetime import date

import pytest

from bstockreport.metrics import WeeklyMetrics, weekly_metrics

# 2026-09-26(토) 까지의 일일 equity. 기준 종가는 cutoff(09-19) 이하의 마지막 포인트.
_EQUITY = [
    (date(2026, 9, 15), 1_130_000.0),
    (date(2026, 9, 18), 1_140_000.0),
    (date(2026, 9, 19), 1_142_429.0),  # cutoff 당일 → 기준
    (date(2026, 9, 22), 1_150_000.0),
    (date(2026, 9, 26), 1_134_670.0),  # as_of
]


def test_window_is_seven_calendar_days_ending_at_last_equity_date():
    w = weekly_metrics(_EQUITY, [])
    assert isinstance(w, WeeklyMetrics)
    assert w.start == date(2026, 9, 20)
    assert w.end == date(2026, 9, 26)


def test_equity_start_is_last_close_on_or_before_cutoff():
    w = weekly_metrics(_EQUITY, [])
    assert w.equity_start == pytest.approx(1_142_429.0)
    assert w.equity_end == pytest.approx(1_134_670.0)
    assert w.ret_pct == pytest.approx((1_134_670.0 / 1_142_429.0 - 1) * 100)


def test_round_trips_are_counted_by_close_date_inside_window():
    trips = [
        (date(2026, 9, 19), 0.50),  # cutoff 당일 → 지난주
        (date(2026, 9, 20), 0.02),
        (date(2026, 9, 24), -0.01),
        (date(2026, 9, 26), 0.005),
        (date(2026, 9, 27), 0.30),  # as_of 이후 → 제외
    ]
    w = weekly_metrics(_EQUITY, trips)
    assert w.rt_count == 3
    assert w.rt_avg_pct == pytest.approx((0.02 - 0.01 + 0.005) / 3 * 100)
    assert w.rt_win_pct == pytest.approx(2 / 3 * 100)


def test_no_round_trips_gives_zero_count_and_no_ratios():
    w = weekly_metrics(_EQUITY, [(date(2026, 9, 1), 0.1)])
    assert w.rt_count == 0
    assert w.rt_avg_pct is None
    assert w.rt_win_pct is None


def test_history_shorter_than_a_week_starts_from_first_point():
    eq = [(date(2026, 9, 23), 100.0), (date(2026, 9, 26), 110.0)]
    w = weekly_metrics(eq, [])
    assert w.equity_start == pytest.approx(100.0)
    assert w.ret_pct == pytest.approx(10.0)


def test_single_point_has_no_equity_change():
    w = weekly_metrics([(date(2026, 9, 26), 100.0)], [])
    assert w.end == date(2026, 9, 26)
    assert w.equity_start is None
    assert w.equity_end is None
    assert w.ret_pct is None


def test_empty_equity_returns_none():
    assert weekly_metrics([], [(date(2026, 9, 26), 0.1)]) is None


def test_unsorted_equity_input_is_ordered_by_date():
    w = weekly_metrics(list(reversed(_EQUITY)), [])
    assert w.equity_start == pytest.approx(1_142_429.0)
    assert w.equity_end == pytest.approx(1_134_670.0)
