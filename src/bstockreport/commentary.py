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
        parts.append(f"• {overall}예요.")

    if m.baseline is not None:
        parts.append(f"• 백테스트 기준선은 {m.baseline}이에요.")
        if m.baseline_trade_pct is not None and m.rt_avg_pct is not None:
            diff = m.rt_avg_pct - m.baseline_trade_pct
            parts.append(
                f"• 거래당 수익 실측 {m.rt_avg_pct:+.2f}%"
                f" vs 기준선 {m.baseline_trade_pct:+.2f}% (차이 {diff:+.2f}%)예요."
            )
        if m.baseline_win_pct is not None and m.rt_win_pct is not None:
            parts.append(
                f"• 승률 실측 {m.rt_win_pct:.1f}% vs 기준선 {m.baseline_win_pct:.1f}%예요."
            )

    risk_parts = []
    if m.mdd_pct is not None:
        risk_parts.append(f"최대낙폭 {m.mdd_pct:.1f}%")
    if m.vol_pct is not None:
        risk_parts.append(f"변동성 {m.vol_pct:.1f}%")
    if risk_parts:
        risk_line = f"• 위험 지표는 {' · '.join(risk_parts)}예요."
        if m.small_sample:
            risk_line += " 소표본이라 Sharpe는 과대평가되기 쉬워요."
        parts.append(risk_line)

    if m.is_margin:
        cash_str = f" (현금 ${m.cash:,.0f})" if m.cash is not None else ""
        parts.append(f"• 마진 계좌{cash_str}예요. 레버리지 리스크를 확인해야 해요.")

    if m.small_sample:
        parts.append(
            f"• {m.days}거래일 소표본이에요."
            " 지금은 결론을 내는 단계가 아니라,"
            " 좋은 성과가 운이었을 가능성을 열어두고 지켜보는 단계예요."
        )

    return "\n".join(parts) if parts else "(해설 없음)"
