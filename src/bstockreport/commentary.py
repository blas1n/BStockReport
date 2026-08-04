from bstockreport.metrics import SourceMetrics


def anomaly_flags(m: SourceMetrics) -> list[str]:
    flags = []
    if m.is_margin:
        flags.append("⚠️ 마진 계좌 (현금 < 0)")
    if m.mdd_pct is not None and m.mdd_pct <= -8:
        flags.append(f"⚠️ 최대낙폭 {m.mdd_pct:.1f}% ≤ -8%")
    if m.fill_rate is not None and m.fill_rate < 85:
        flags.append(f"⚠️ 체결률 {m.fill_rate:.0f}% < 85%")
    if m.rt_win_pct is not None and m.rt_win_pct < 45:
        flags.append(f"⚠️ 승률 {m.rt_win_pct:.1f}% < 45%")
    return flags


def rule_commentary(m: SourceMetrics) -> str:
    parts = []

    if m.ret_pct is not None:
        overall = f"수익률 {m.ret_pct:+.2f}%"
        if m.sharpe is not None:
            overall += f", Sharpe {m.sharpe:.2f}"
        parts.append(f"[총평] {overall}.")

    if m.baseline is not None:
        parts.append(f"[백테스트 기준선] {m.baseline}.")
        if m.baseline_trade_pct is not None and m.rt_avg_pct is not None:
            diff = m.rt_avg_pct - m.baseline_trade_pct
            parts.append(
                f"  거래당 수익 실측 {m.rt_avg_pct:+.2f}%"
                f" vs 기준선 {m.baseline_trade_pct:+.2f}% (차이 {diff:+.2f}%)."
            )
        if m.baseline_win_pct is not None and m.rt_win_pct is not None:
            parts.append(f"  승률 실측 {m.rt_win_pct:.1f}% vs 기준선 {m.baseline_win_pct:.1f}%.")

    risk_parts = []
    if m.mdd_pct is not None:
        risk_parts.append(f"최대낙폭 {m.mdd_pct:.1f}%")
    if m.vol_pct is not None:
        risk_parts.append(f"변동성 {m.vol_pct:.1f}%")
    if risk_parts:
        parts.append(f"[리스크] {' · '.join(risk_parts)}.")

    if m.is_margin:
        cash_str = f" (현금 ${m.cash:,.0f})" if m.cash is not None else ""
        parts.append(f"[주의] 마진 계좌{cash_str} — 레버리지 리스크 확인 필요.")

    if m.small_sample:
        parts.append(f"[경고] 소표본 ({m.days}일) — 통계 신뢰도 낮음. 백테스트 회귀 조심.")

    return "\n".join(parts) if parts else "(해설 없음)"
