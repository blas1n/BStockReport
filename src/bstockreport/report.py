from bstockreport.commentary import anomaly_flags
from bstockreport.metrics import RepricedRoundTrips, SourceMetrics, WeeklyMetrics

_SEP = "─" * 56


def _week_line(w: WeeklyMetrics) -> str:
    parts: list[str] = []
    if w.equity_start is not None and w.equity_end is not None and w.ret_pct is not None:
        parts.append(f"자산 ${w.equity_start:,.0f} → ${w.equity_end:,.0f} ({w.ret_pct:+.2f}%)")
    if w.rt_count == 0:
        parts.append("왕복거래 없음")
    else:
        parts.append(f"왕복거래 {w.rt_count}회")
        if w.rt_avg_pct is not None:
            parts.append(f"평균 {w.rt_avg_pct:+.2f}%")
        if w.rt_win_pct is not None:
            parts.append(f"승률 {w.rt_win_pct:.1f}%")
    return f"이번 주({w.start} ~ {w.end}): " + " · ".join(parts)


def _repriced_line(r: RepricedRoundTrips) -> str:
    parts: list[str] = []
    if r.rt_count == 0:
        parts.append("왕복거래 없음")
    else:
        if r.avg_pct is not None:
            parts.append(f"평균 {r.avg_pct:+.2f}%")
        if r.win_pct is not None:
            parts.append(f"승률 {r.win_pct:.1f}%")
    parts.append("페이퍼 체결은 실제보다 저렴")
    return f"비용 반영({round(r.cost_per_leg * 1e4, 2):g}bp/leg): " + " · ".join(parts)


def build(metrics: list[SourceMetrics], *, verbatim: bool) -> str:
    blocks: list[str] = []

    for m in metrics:
        if not m.ok:
            blocks.append(f"⚠️ {m.name} 수집 실패: {m.error}")
            continue

        lines: list[str] = [f"[{m.name}]"]

        # 이번 주 — 주간 독자가 먼저 보는 줄. 3개월 줄은 아래에 그대로.
        if m.week is not None:
            lines.append(_week_line(m.week))

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

        # 연구 비용 가정으로 다시 매긴 왕복 — 페이퍼 체결은 실제보다 싸다
        if m.repriced is not None:
            lines.append(_repriced_line(m.repriced))

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

    starts = [m.period_start for m in metrics if m.period_start is not None]
    ends = [m.period_end for m in metrics if m.period_end is not None]
    if starts and ends:
        body = body + f"\n집계 기간: {min(starts)} ~ {max(ends)}"

    if verbatim:
        return f"<<REPORT_VERBATIM>>\n{body}\n<<END>>"
    return body
