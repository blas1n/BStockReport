from datetime import date

from bstockreport.metrics import SourceMetrics
from bstockreport.report import build


def _ok(**kwargs) -> SourceMetrics:
    return SourceMetrics(name="TestSrc", ok=True, **kwargs)


def _fail(error: str = "연결 오류") -> SourceMetrics:
    return SourceMetrics(name="FailSrc", ok=False, error=error)


# ── 단일 소스 · 기본 구조 ────────────────────────────────────────────────────


class TestSingleSourceStructure:
    def test_source_name_appears(self):
        result = build([_ok()], verbatim=False)
        assert "[TestSrc]" in result

    def test_no_verbatim_markers_when_false(self):
        result = build([_ok()], verbatim=False)
        assert "<<REPORT_VERBATIM>>" not in result
        assert "<<END>>" not in result

    def test_verbatim_wraps_output(self):
        result = build([_ok()], verbatim=True)
        assert result.startswith("<<REPORT_VERBATIM>>")
        assert result.endswith("<<END>>")

    def test_verbatim_body_is_between_markers(self):
        result = build([_ok(ret_pct=1.0)], verbatim=True)
        inner = result.removeprefix("<<REPORT_VERBATIM>>\n").removesuffix("\n<<END>>")
        assert "[TestSrc]" in inner
        assert "수익률" in inner


# ── None 필드 생략 ───────────────────────────────────────────────────────────


class TestNoneFieldsOmitted:
    def test_no_asset_line_when_all_none(self):
        result = build([_ok()], verbatim=False)
        assert "자산:" not in result

    def test_no_fill_line_when_all_none(self):
        result = build([_ok()], verbatim=False)
        assert "체결:" not in result

    def test_no_rt_line_when_all_none(self):
        result = build([_ok()], verbatim=False)
        assert "왕복거래:" not in result

    def test_no_pos_line_when_all_none(self):
        result = build([_ok()], verbatim=False)
        assert "포지션:" not in result

    def test_partial_asset_only_shows_present_fields(self):
        result = build([_ok(ret_pct=3.5)], verbatim=False)
        assert "수익률 +3.50%" in result
        assert "Sharpe" not in result
        assert "MDD" not in result


# ── ok=False 소스 ────────────────────────────────────────────────────────────


class TestFailedSource:
    def test_failure_line_format(self):
        result = build([_fail("API 타임아웃")], verbatim=False)
        assert "⚠️ FailSrc 수집 실패: API 타임아웃" in result

    def test_failure_no_asset_line(self):
        result = build([_fail()], verbatim=False)
        assert "자산:" not in result

    def test_failure_no_position_line(self):
        result = build([_fail()], verbatim=False)
        assert "포지션:" not in result

    def test_ok_source_still_renders_after_failure(self):
        src_ok = _ok(ret_pct=2.0)
        result = build([_fail(), src_ok], verbatim=False)
        assert "⚠️ FailSrc" in result
        assert "[TestSrc]" in result
        assert "수익률 +2.00%" in result


# ── 복수 소스 · 구분선 ────────────────────────────────────────────────────────


class TestMultipleSources:
    def test_separator_between_sources(self):
        a = SourceMetrics(name="A", ok=True, ret_pct=1.0)
        b = SourceMetrics(name="B", ok=True, ret_pct=2.0)
        result = build([a, b], verbatim=False)
        assert "─" in result
        assert "[A]" in result
        assert "[B]" in result

    def test_one_source_no_separator(self):
        result = build([_ok()], verbatim=False)
        assert "─" not in result

    def test_three_sources_two_separators(self):
        sources = [
            SourceMetrics(name="X", ok=True),
            SourceMetrics(name="Y", ok=True),
            SourceMetrics(name="Z", ok=True),
        ]
        result = build(sources, verbatim=False)
        assert result.count("─" * 10) >= 2


# ── 자산 섹션 ────────────────────────────────────────────────────────────────


class TestAssetSection:
    def test_equity_start_formatted(self):
        result = build([_ok(equity_start=100_000.0)], verbatim=False)
        assert "시작 $100,000" in result

    def test_equity_end_formatted(self):
        result = build([_ok(equity_end=105_000.0)], verbatim=False)
        assert "종료 $105,000" in result

    def test_ret_pct_positive_sign(self):
        result = build([_ok(ret_pct=5.25)], verbatim=False)
        assert "수익률 +5.25%" in result

    def test_ret_pct_negative(self):
        result = build([_ok(ret_pct=-3.1)], verbatim=False)
        assert "수익률 -3.10%" in result

    def test_sharpe_two_decimals(self):
        result = build([_ok(sharpe=1.234)], verbatim=False)
        assert "Sharpe 1.23" in result

    def test_mdd_one_decimal(self):
        result = build([_ok(mdd_pct=-12.5)], verbatim=False)
        assert "MDD -12.5%" in result

    def test_vol_one_decimal(self):
        result = build([_ok(vol_pct=8.7)], verbatim=False)
        assert "변동성 8.7%" in result


# ── 체결 섹션 ────────────────────────────────────────────────────────────────


class TestFillSection:
    def test_fills_shown(self):
        result = build([_ok(fills=42)], verbatim=False)
        assert "체결 42건" in result

    def test_total_orders_shown(self):
        result = build([_ok(total_orders=50)], verbatim=False)
        assert "주문 50건" in result

    def test_fill_rate_rounded(self):
        result = build([_ok(fill_rate=84.6)], verbatim=False)
        assert "체결률 85%" in result


# ── 왕복거래 섹션 ────────────────────────────────────────────────────────────


class TestRoundTripSection:
    def test_rt_count_shown(self):
        result = build([_ok(rt_count=10)], verbatim=False)
        assert "10회" in result

    def test_rt_avg_pct_signed(self):
        result = build([_ok(rt_avg_pct=0.55)], verbatim=False)
        assert "평균 +0.55%" in result

    def test_rt_med_pct_negative(self):
        result = build([_ok(rt_med_pct=-0.10)], verbatim=False)
        assert "중앙값 -0.10%" in result

    def test_rt_win_pct_one_decimal(self):
        result = build([_ok(rt_win_pct=62.3)], verbatim=False)
        assert "승률 62.3%" in result


# ── 포지션 섹션 ────────────────────────────────────────────────────────────────


class TestPositionSection:
    def test_pos_count_shown(self):
        result = build([_ok(pos_count=3)], verbatim=False)
        assert "포지션 3개" in result

    def test_equity_formatted(self):
        result = build([_ok(equity=50_000.0)], verbatim=False)
        assert "평가액 $50,000" in result

    def test_cash_formatted(self):
        result = build([_ok(cash=20_000.0)], verbatim=False)
        assert "현금 $20,000" in result

    def test_long_mv_formatted(self):
        result = build([_ok(long_mv=30_000.0)], verbatim=False)
        assert "롱 MV $30,000" in result

    def test_upl_signed(self):
        result = build([_ok(upl=-500.0)], verbatim=False)
        assert "미실현손익 $-500" in result


# ── 이상징후 ─────────────────────────────────────────────────────────────────


class TestAnomalyFlagsInReport:
    def test_no_anomaly_line_when_clean(self):
        result = build([_ok()], verbatim=False)
        assert "이상징후:" not in result

    def test_anomaly_line_appears_for_margin(self):
        result = build([_ok(is_margin=True)], verbatim=False)
        assert "이상징후:" in result
        assert "마진" in result

    def test_anomaly_line_appears_for_low_mdd(self):
        result = build([_ok(mdd_pct=-9.0)], verbatim=False)
        assert "이상징후:" in result
        assert "최대낙폭" in result

    def test_no_commentary_text_in_report(self):
        result = build([_ok(ret_pct=2.0, mdd_pct=-5.0)], verbatim=False)
        assert "[총평]" not in result
        assert "[리스크]" not in result
        assert "[백테스트 기준선]" not in result


# ── 빈 리스트 ────────────────────────────────────────────────────────────────


class TestEmptyList:
    def test_empty_list_returns_empty_string(self):
        result = build([], verbatim=False)
        assert result == ""

    def test_empty_list_verbatim(self):
        result = build([], verbatim=True)
        assert result == "<<REPORT_VERBATIM>>\n\n<<END>>"


# ── 집계 기간 푸터 ────────────────────────────────────────────────────────────


class TestPeriodFooter:
    def test_period_footer_shown_when_dates_present(self):
        m = _ok(period_start=date(2026, 5, 1), period_end=date(2026, 8, 1))
        result = build([m], verbatim=False)
        assert "집계 기간: 2026-05-01 ~ 2026-08-01" in result

    def test_period_footer_at_bottom(self):
        m = _ok(period_start=date(2026, 5, 1), period_end=date(2026, 8, 1), ret_pct=1.0)
        result = build([m], verbatim=False)
        assert result.endswith("집계 기간: 2026-05-01 ~ 2026-08-01")

    def test_period_footer_omitted_when_no_dates(self):
        result = build([_ok()], verbatim=False)
        assert "집계 기간:" not in result

    def test_period_footer_inside_verbatim_markers(self):
        m = _ok(period_start=date(2026, 5, 1), period_end=date(2026, 8, 1))
        result = build([m], verbatim=True)
        assert result.startswith("<<REPORT_VERBATIM>>")
        assert result.endswith("<<END>>")
        assert "집계 기간: 2026-05-01 ~ 2026-08-01" in result

    def test_period_footer_uses_widest_range_across_sources(self):
        a = SourceMetrics(
            name="A", ok=True, period_start=date(2026, 5, 1), period_end=date(2026, 8, 1)
        )
        b = SourceMetrics(
            name="B", ok=True, period_start=date(2026, 4, 15), period_end=date(2026, 8, 5)
        )
        result = build([a, b], verbatim=False)
        assert "집계 기간: 2026-04-15 ~ 2026-08-05" in result
