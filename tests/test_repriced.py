"""왕복을 연구 비용 가정으로 재계산 — 순수 계산. 계좌·네트워크 접근 없음."""

import pytest

from bstockreport.metrics import repriced_round_trips


def test_subtracts_two_legs_from_each_round_trip():
    r = repriced_round_trips([0.0125, -0.005], cost_per_leg=0.001)
    assert r.cost_per_leg == 0.001
    assert r.rt_count == 2
    # (0.0105 + -0.007) / 2 = 0.00175
    assert r.avg_pct == pytest.approx(0.175)
    assert r.win_pct == pytest.approx(50.0)


def test_paper_win_smaller_than_cost_is_a_loss_after_cost():
    # +0.1% 페이퍼 수익은 0.2%p 비용을 못 넘는다
    r = repriced_round_trips([0.001, 0.02], cost_per_leg=0.001)
    assert r.win_pct == pytest.approx(50.0)


def test_break_even_after_cost_is_not_a_win():
    r = repriced_round_trips([0.002], cost_per_leg=0.001)
    assert r.avg_pct == pytest.approx(0.0)
    assert r.win_pct == pytest.approx(0.0)


def test_cost_is_configurable():
    r = repriced_round_trips([0.01], cost_per_leg=0.0025)
    assert r.avg_pct == pytest.approx(0.5)


def test_zero_round_trips_is_said_not_divided():
    r = repriced_round_trips([], cost_per_leg=0.001)
    assert r.rt_count == 0
    assert r.avg_pct is None
    assert r.win_pct is None
