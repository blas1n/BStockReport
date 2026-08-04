from bstockreport.commentary import anomaly_flags
from bstockreport.metrics import SourceMetrics

_SEP = "─" * 40


def build(metrics: list[SourceMetrics], *, verbatim: bool) -> str:
    blocks: list[str] = []

    for m in metrics:
        if not m.ok:
            blocks.append(f"⚠️ {m.name} 수집 실패: {m.error}")
            continue

        lines: list[str] = [f"[{m.name}]"]

        # 자산곡선
        asset_parts: list[str] = []
        if m.equity_start is not None:
            asset_parts.append(f"시작 ${m.equity_start:,.0f}")
        if m.equity_end is not None:
            asset_parts.append(f"종료 ${m.equity_end:,.0f}")
        if m.ret_pct is not None:
            asset_parts.append(f"수익률 {m.ret_pct:+.2f}%")
        if m.sharpe is not None:
            asset_parts.append(f"Sharpe {m.sharpe:.2f}")
        if m.mdd_pct is not None:
            asset_parts.append(f"MDD {m.mdd_pct:.1f}%")
        if m.vol_pct is not None:
            asset_parts.append(f"변동성 {m.vol_pct:.1f}%")
        if asset_parts:
            lines.append("자산: " + " · ".join(asset_parts))

        # 체결·수익
        fill_parts: list[str] = []
        if m.fills is not None:
            fill_parts.append(f"체결 {m.fills}건")
        if m.total_orders is not None:
            fill_parts.append(f"주문 {m.total_orders}건")
        if m.fill_rate is not None:
            fill_parts.append(f"체결률 {m.fill_rate:.0f}%")
        if fill_parts:
            lines.append("체결: " + " · ".join(fill_parts))

        # 왕복거래
        rt_parts: list[str] = []
        if m.rt_count is not None:
            rt_parts.append(f"{m.rt_count}회")
        if m.rt_avg_pct is not None:
            rt_parts.append(f"평균 {m.rt_avg_pct:+.2f}%")
        if m.rt_med_pct is not None:
            rt_parts.append(f"중앙값 {m.rt_med_pct:+.2f}%")
        if m.rt_win_pct is not None:
            rt_parts.append(f"승률 {m.rt_win_pct:.1f}%")
        if rt_parts:
            lines.append("왕복거래: " + " · ".join(rt_parts))

        # 포지션·현금
        pos_parts: list[str] = []
        if m.pos_count is not None:
            pos_parts.append(f"포지션 {m.pos_count}개")
        if m.equity is not None:
            pos_parts.append(f"평가액 ${m.equity:,.0f}")
        if m.cash is not None:
            pos_parts.append(f"현금 ${m.cash:,.0f}")
        if m.long_mv is not None:
            pos_parts.append(f"롱 MV ${m.long_mv:,.0f}")
        if m.upl is not None:
            pos_parts.append(f"미실현손익 ${m.upl:+,.0f}")
        if pos_parts:
            lines.append("포지션: " + " · ".join(pos_parts))

        # 이상징후
        flags = anomaly_flags(m)
        if flags:
            lines.append("이상징후: " + " / ".join(flags))

        blocks.append("\n".join(lines))

    body = f"\n{_SEP}\n".join(blocks)

    if verbatim:
        return f"<<REPORT_VERBATIM>>\n{body}\n<<END>>"
    return body
