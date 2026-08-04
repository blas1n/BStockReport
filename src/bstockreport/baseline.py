import os
import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Baseline:
    text: str
    trade_pct: float | None
    win_pct: float | None


def load_bloasis_baseline(db_path: str | None = None) -> Baseline | None:
    try:
        path = db_path or os.environ.get("BLOASIS_DB_PATH")
        if not path:
            return None

        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            col_cur = conn.execute("PRAGMA table_info(backtest_runs)")
            cols = {row[1] for row in col_cur.fetchall()}
            if not cols:
                return None

            order_by = "created_at DESC" if "created_at" in cols else "rowid DESC"
            row_cur = conn.execute(f"SELECT * FROM backtest_runs ORDER BY {order_by} LIMIT 1")
            col_names = [d[0] for d in row_cur.description]
            row = row_cur.fetchone()
            if row is None:
                return None

            d = dict(zip(col_names, row, strict=True))

            win_pct: float | None = None
            if d.get("win_rate") is not None:
                wr = float(d["win_rate"])
                win_pct = wr * 100 if wr <= 1 else wr

            sharpe: float | None = None
            if d.get("sharpe") is not None:
                sharpe = float(d["sharpe"])

            mdd: float | None = None
            if d.get("max_drawdown") is not None:
                mdd = float(d["max_drawdown"])

            trade_pct: float | None = None
            if d.get("trade_pct") is not None:
                trade_pct = float(d["trade_pct"])

            parts: list[str] = []
            if win_pct is not None:
                parts.append(f"승률 {win_pct:g}%")
            if sharpe is not None:
                parts.append(f"Sharpe {sharpe:.2f}")
            if mdd is not None:
                parts.append(f"MDD {mdd:.1f}%")

            if not parts:
                return None

            return Baseline(
                text="백테스트: " + " · ".join(parts),
                trade_pct=trade_pct,
                win_pct=win_pct,
            )
        finally:
            conn.close()
    except Exception:
        return None
