import sqlite3

import pytest

from bstockreport.baseline import load_bloasis_baseline


def _db(tmp_path, cols, rows, *, name="bloasis.db"):
    db = tmp_path / name
    conn = sqlite3.connect(str(db))
    col_defs = ", ".join(f"{c} REAL" for c in cols if c != "created_at")
    if "created_at" in cols:
        col_defs += (", " if col_defs else "") + "created_at TEXT"
    conn.execute(f"CREATE TABLE backtest_runs ({col_defs})")
    for row in rows:
        conn.execute(f"INSERT INTO backtest_runs VALUES ({', '.join('?' * len(row))})", row)
    conn.commit()
    conn.close()
    return str(db)


# ─── 정상 케이스 ──────────────────────────────────────────────────────────────


def test_normal_all_columns(tmp_path):
    db = _db(
        tmp_path,
        cols=["win_rate", "sharpe", "max_drawdown", "trade_pct", "created_at"],
        rows=[(0.58, 1.33, -15.0, 40.0, "2024-01-01")],
    )
    result = load_bloasis_baseline(db)
    assert result is not None
    assert result.win_pct == pytest.approx(58.0)
    assert result.trade_pct == pytest.approx(40.0)
    assert "승률" in result.text
    assert "Sharpe" in result.text


def test_win_rate_fraction_converted(tmp_path):
    """win_rate=0.58 → win_pct=58.0."""
    db = _db(tmp_path, cols=["win_rate"], rows=[(0.58,)])
    result = load_bloasis_baseline(db)
    assert result is not None
    assert result.win_pct == pytest.approx(58.0)


def test_win_rate_already_percent(tmp_path):
    """win_rate=58 → win_pct=58.0 (1 초과이므로 그대로)."""
    db = _db(tmp_path, cols=["win_rate"], rows=[(58.0,)])
    result = load_bloasis_baseline(db)
    assert result is not None
    assert result.win_pct == pytest.approx(58.0)


# ─── None 반환 케이스 ─────────────────────────────────────────────────────────


def test_no_table_returns_none(tmp_path):
    """테이블 없음 → None."""
    db = tmp_path / "empty.db"
    conn = sqlite3.connect(str(db))
    conn.close()
    assert load_bloasis_baseline(str(db)) is None


def test_empty_table_returns_none(tmp_path):
    """행 0개 → None."""
    db = _db(tmp_path, cols=["win_rate", "sharpe"], rows=[])
    assert load_bloasis_baseline(db) is None


def test_missing_file_returns_none(tmp_path):
    """파일 경로가 존재하지 않음 → None."""
    assert load_bloasis_baseline(str(tmp_path / "nonexistent.db")) is None


def test_no_path_returns_none(monkeypatch):
    """db_path/BLOASIS_DB_PATH 둘 다 없음 → None."""
    monkeypatch.delenv("BLOASIS_DB_PATH", raising=False)
    assert load_bloasis_baseline() is None


def test_env_var_used(tmp_path, monkeypatch):
    """BLOASIS_DB_PATH 환경변수로 경로 지정 → 정상 읽힘."""
    db = _db(tmp_path, cols=["win_rate"], rows=[(0.58,)])
    monkeypatch.setenv("BLOASIS_DB_PATH", db)
    result = load_bloasis_baseline()
    assert result is not None
    assert result.win_pct == pytest.approx(58.0)


# ─── 일부 컬럼만 존재 ─────────────────────────────────────────────────────────


def test_partial_columns_text_only_available(tmp_path):
    """win_rate 컬럼만 있음 → sharpe/MDD 없이 text 구성."""
    db = _db(tmp_path, cols=["win_rate"], rows=[(0.58,)])
    result = load_bloasis_baseline(db)
    assert result is not None
    assert result.win_pct == pytest.approx(58.0)
    assert result.trade_pct is None
    assert "Sharpe" not in result.text
    assert "MDD" not in result.text
    assert "승률" in result.text


def test_all_metric_values_null_returns_none(tmp_path):
    """win_rate/sharpe/max_drawdown 모두 NULL → None."""
    db = _db(tmp_path, cols=["win_rate", "sharpe", "max_drawdown"], rows=[(None, None, None)])
    assert load_bloasis_baseline(db) is None


# ─── 예외 격리 ────────────────────────────────────────────────────────────────


def test_corrupted_db_returns_none(tmp_path):
    """손상된 파일 → 예외가 밖으로 새지 않고 None 반환."""
    bad_db = tmp_path / "bad.db"
    bad_db.write_bytes(b"this is not a sqlite database!!")
    assert load_bloasis_baseline(str(bad_db)) is None
