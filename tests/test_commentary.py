import pytest

from bstockreport.commentary import anomaly_flags, rule_commentary
from bstockreport.metrics import SourceMetrics


def m(**kwargs) -> SourceMetrics:
    return SourceMetrics(name="Test", ok=True, **kwargs)


# ── anomaly_flags ─────────────────────────────────────────────────────────────


class TestAnomalyFlags:
    def test_clean_no_flags(self):
        assert anomaly_flags(m()) == []

    def test_margin(self):
        flags = anomaly_flags(m(is_margin=True))
        assert any("마진" in f for f in flags)

    def test_mdd_at_threshold(self):
        flags = anomaly_flags(m(mdd_pct=-8.0))
        assert any("최대낙폭" in f for f in flags)

    def test_mdd_below_threshold(self):
        flags = anomaly_flags(m(mdd_pct=-9.5))
        assert any("최대낙폭" in f for f in flags)

    def test_mdd_above_threshold_no_flag(self):
        assert anomaly_flags(m(mdd_pct=-7.9)) == []

    def test_mdd_none_no_flag(self):
        assert anomaly_flags(m()) == []

    def test_fill_rate_low(self):
        flags = anomaly_flags(m(fill_rate=84.9))
        assert any("체결률" in f for f in flags)

    def test_fill_rate_at_boundary_no_flag(self):
        assert anomaly_flags(m(fill_rate=85.0)) == []

    def test_fill_rate_none_no_flag(self):
        assert anomaly_flags(m()) == []

    def test_win_rate_low(self):
        flags = anomaly_flags(m(rt_win_pct=44.9))
        assert any("승률" in f for f in flags)

    def test_win_rate_at_boundary_no_flag(self):
        assert anomaly_flags(m(rt_win_pct=45.0)) == []

    def test_win_rate_none_no_flag(self):
        assert anomaly_flags(m()) == []

    def test_multiple_flags(self):
        flags = anomaly_flags(m(is_margin=True, mdd_pct=-10.0, fill_rate=70.0, rt_win_pct=30.0))
        assert len(flags) == 4


# ── rule_commentary ───────────────────────────────────────────────────────────


class TestRuleCommentary:
    def test_all_none_returns_placeholder(self):
        assert rule_commentary(m()) == "(해설 없음)"

    def test_ret_pct_only(self):
        result = rule_commentary(m(ret_pct=5.3))
        assert "[총평]" in result
        assert "+5.30%" in result
        assert "Sharpe" not in result

    def test_ret_pct_with_sharpe(self):
        result = rule_commentary(m(ret_pct=5.3, sharpe=1.2))
        assert "Sharpe 1.20" in result

    def test_negative_ret_pct(self):
        result = rule_commentary(m(ret_pct=-2.1))
        assert "-2.10%" in result

    def test_baseline_only(self):
        result = rule_commentary(m(baseline="기준 설명"))
        assert "[백테스트 기준선]" in result
        assert "기준 설명" in result
        assert "거래당 수익" not in result
        assert "승률 실측" not in result

    def test_baseline_with_trade_comparison(self):
        result = rule_commentary(m(baseline="B", baseline_trade_pct=0.32, rt_avg_pct=0.50))
        assert "거래당 수익" in result
        assert "+0.50%" in result
        assert "+0.32%" in result
        assert "차이 +0.18%" in result

    def test_baseline_trade_pct_missing_skips_comparison(self):
        result = rule_commentary(m(baseline="B", rt_avg_pct=0.50))
        assert "거래당 수익" not in result

    def test_baseline_rt_avg_missing_skips_comparison(self):
        result = rule_commentary(m(baseline="B", baseline_trade_pct=0.32))
        assert "거래당 수익" not in result

    def test_baseline_with_win_comparison(self):
        result = rule_commentary(m(baseline="B", baseline_win_pct=63.0, rt_win_pct=60.0))
        assert "승률 실측 60.0%" in result
        assert "기준선 63.0%" in result

    def test_baseline_win_pct_missing_skips_win_line(self):
        result = rule_commentary(m(baseline="B", rt_win_pct=60.0))
        assert "승률 실측" not in result

    def test_risk_mdd(self):
        result = rule_commentary(m(mdd_pct=-5.2))
        assert "[리스크]" in result
        assert "최대낙폭 -5.2%" in result

    def test_risk_vol(self):
        result = rule_commentary(m(vol_pct=12.3))
        assert "[리스크]" in result
        assert "변동성 12.3%" in result

    def test_risk_mdd_and_vol_joined(self):
        result = rule_commentary(m(mdd_pct=-3.0, vol_pct=8.0))
        assert "최대낙폭" in result
        assert "변동성" in result
        assert " · " in result

    def test_margin_with_cash(self):
        result = rule_commentary(m(is_margin=True, cash=-1000.0))
        assert "[주의]" in result
        assert "마진" in result
        assert "-1,000" in result

    def test_margin_without_cash(self):
        result = rule_commentary(m(is_margin=True))
        assert "[주의]" in result
        assert "마진" in result
        assert "현금" not in result

    def test_small_sample(self):
        result = rule_commentary(m(small_sample=True, days=30))
        assert "[경고]" in result
        assert "30일" in result

    def test_combined_all_sections(self):
        result = rule_commentary(
            m(
                ret_pct=2.0,
                sharpe=0.8,
                baseline="B",
                mdd_pct=-6.0,
                vol_pct=10.0,
                is_margin=True,
                cash=-500.0,
                small_sample=True,
                days=45,
            )
        )
        assert "[총평]" in result
        assert "[백테스트 기준선]" in result
        assert "[리스크]" in result
        assert "[주의]" in result
        assert "[경고]" in result


# ── Source ABC smoke test ─────────────────────────────────────────────────────


def test_source_abc_cannot_be_instantiated():
    from bstockreport.sources.base import Source

    with pytest.raises(TypeError):
        Source()  # type: ignore[abstract]


def test_source_abc_concrete_subclass():
    from bstockreport.sources.base import Source

    class Stub(Source):
        @property
        def name(self) -> str:
            return "stub"

        def collect(self) -> SourceMetrics:
            return SourceMetrics(name="stub", ok=True)

    s = Stub()
    assert s.name == "stub"
    assert s.collect().ok is True
