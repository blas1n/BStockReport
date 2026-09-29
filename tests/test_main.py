import sys

import pytest

import bstockreport.main as main_mod
from bstockreport.metrics import SourceMetrics


@pytest.fixture(autouse=True)
def _logs_dir(tmp_path, monkeypatch):
    """--push 가 저장하는 리포트 사본이 레포 logs/ 를 더럽히지 않게 한다."""
    logs = tmp_path / "logs"
    monkeypatch.setenv("LOGS_DIR", str(logs))
    return logs


def _good_collect(self):
    return SourceMetrics(name=self._name, ok=True, ret_pct=2.0, rt_avg_pct=0.3, rt_win_pct=60.0)


def _fake_send(calls: list):
    def _send(text, **kw):
        calls.append(text)
        return True

    return _send


# ── --emit ────────────────────────────────────────────────────────────────────


def test_emit_has_verbatim_marker(monkeypatch, capsys):
    telegram_calls: list = []
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--emit"])

    main_mod.main()

    out = capsys.readouterr().out
    assert "<<REPORT_VERBATIM>>" in out
    assert "<<END>>" in out


def test_emit_no_telegram_call(monkeypatch, capsys):
    telegram_calls: list = []
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--emit"])

    main_mod.main()

    assert len(telegram_calls) == 0


def test_no_flag_behaves_like_emit(monkeypatch, capsys):
    telegram_calls: list = []
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run"])

    main_mod.main()

    out = capsys.readouterr().out
    assert "<<REPORT_VERBATIM>>" in out
    assert len(telegram_calls) == 0


# ── --push ────────────────────────────────────────────────────────────────────


def test_push_calls_telegram(monkeypatch):
    telegram_calls: list = []
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(main_mod, "llm_commentary", lambda *a, **kw: "LLM 해설이에요.")
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--push"])

    main_mod.main()

    assert len(telegram_calls) >= 1


def test_push_no_verbatim_marker_in_telegram(monkeypatch):
    telegram_calls: list = []
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(main_mod, "llm_commentary", lambda *a, **kw: "LLM 해설이에요.")
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--push"])

    main_mod.main()

    for text in telegram_calls:
        assert "<<REPORT_VERBATIM>>" not in text


def test_push_no_stdout(monkeypatch, capsys):
    telegram_calls: list = []
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(main_mod, "llm_commentary", lambda *a, **kw: "LLM 해설이에요.")
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--push"])

    main_mod.main()

    out = capsys.readouterr().out
    assert out.strip() == ""


# ── 소스 예외 처리 ────────────────────────────────────────────────────────────


def test_one_source_fails_other_in_output(monkeypatch, capsys):
    call_count = [0]

    def flaky_collect(self):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("api error")
        return SourceMetrics(name=self._name, ok=True, ret_pct=2.0)

    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", flaky_collect)
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--emit"])

    main_mod.main()

    out = capsys.readouterr().out
    assert "수집 실패" in out
    assert "수익률" in out


def test_both_sources_fail_exits_1(monkeypatch, capsys):
    """전 소스 실패 시 출력은 하되 종료 코드 1."""

    def always_fail(self):
        raise RuntimeError("always fails")

    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", always_fail)
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--emit"])

    with pytest.raises(SystemExit) as exc_info:
        main_mod.main()

    assert exc_info.value.code == 1
    out = capsys.readouterr().out
    assert "수집 실패" in out


# ── LLM None → 규칙기반 해설 ─────────────────────────────────────────────────


def test_llm_none_uses_rule_commentary_nonempty(monkeypatch):
    telegram_calls: list = []
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(main_mod, "llm_commentary", lambda *a, **kw: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--push"])

    main_mod.main()

    assert len(telegram_calls) >= 1
    full_text = " ".join(telegram_calls)
    assert "•" in full_text


def test_llm_none_commentary_not_empty(monkeypatch):
    telegram_calls: list = []
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(main_mod, "llm_commentary", lambda *a, **kw: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--push"])

    main_mod.main()

    full_text = " ".join(telegram_calls)
    assert len(full_text.strip()) > 0


# ── 종료 코드 ──────────────────────────────────────────────────────────────────


def test_all_sources_fail_exits_1_and_telegram_called(monkeypatch):
    """모든 소스 실패 → SystemExit(1), 전송은 여전히 호출됨."""
    telegram_calls: list = []

    def always_fail(self):
        raise RuntimeError("always fails")

    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", always_fail)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(main_mod, "llm_commentary", lambda *a, **kw: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--push"])

    with pytest.raises(SystemExit) as exc_info:
        main_mod.main()

    assert exc_info.value.code == 1
    assert len(telegram_calls) >= 1


def test_partial_failure_exits_0(monkeypatch):
    """일부만 실패 → 정상 종료(코드 0)."""
    call_count = [0]

    def flaky_collect(self):
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("api error")
        return SourceMetrics(name=self._name, ok=True, ret_pct=2.0)

    telegram_calls: list = []
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", flaky_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(main_mod, "llm_commentary", lambda *a, **kw: "LLM 해설이에요.")
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--push"])

    main_mod.main()  # SystemExit 발생 없이 정상 종료


def test_all_sources_success_exits_0(monkeypatch):
    """전부 성공 → 정상 종료(코드 0)."""
    telegram_calls: list = []
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _fake_send(telegram_calls))
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(main_mod, "llm_commentary", lambda *a, **kw: "LLM 해설이에요.")
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--push"])

    main_mod.main()  # SystemExit 발생 없이 정상 종료


# ── 보낸 리포트 보관 (#2) ─────────────────────────────────────────────────────


def _push_setup(monkeypatch, telegram_calls, *, ok=True):
    def _send(text, **kw):
        telegram_calls.append(text)
        return ok

    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "send_telegram", _send)
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(main_mod, "llm_commentary", lambda *a, **kw: "LLM 해설이에요.")
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--push"])


def _saved(logs):
    files = sorted(logs.glob("report-*.txt"))
    assert len(files) == 1, files
    header, body = files[0].read_text(encoding="utf-8").split("\n\n", 1)
    return header, body


def test_push_saves_exact_text_sent(monkeypatch, _logs_dir):
    telegram_calls: list = []
    _push_setup(monkeypatch, telegram_calls)

    main_mod.main()

    header, body = _saved(_logs_dir)
    assert body == telegram_calls[0]
    assert "LLM 해설이에요." in body  # 해설
    assert "수익률" in body  # 숫자 블록
    assert "status: sent" in header


def test_push_failed_send_still_saved_as_unsent(monkeypatch, _logs_dir):
    telegram_calls: list = []
    _push_setup(monkeypatch, telegram_calls, ok=False)

    with pytest.raises(SystemExit):
        main_mod.main()

    header, body = _saved(_logs_dir)
    assert body == telegram_calls[0]
    assert "status: unsent" in header


def test_push_failed_send_exits_nonzero_after_saving(monkeypatch, _logs_dir):
    """전송 실패 → 보관본(unsent)을 남긴 뒤 종료 코드 2. 래퍼가 '전송 완료'로 적지 않게."""
    telegram_calls: list = []
    _push_setup(monkeypatch, telegram_calls, ok=False)

    with pytest.raises(SystemExit) as exc_info:
        main_mod.main()

    assert exc_info.value.code == 2
    header, _ = _saved(_logs_dir)
    assert "status: unsent" in header


def test_push_failed_send_wins_over_all_sources_failed(monkeypatch, _logs_dir):
    """아무것도 배달되지 않은 쪽이 더 무겁다 — 전 소스 실패여도 전송 실패면 2."""

    def always_fail(self):
        raise RuntimeError("always fails")

    telegram_calls: list = []
    _push_setup(monkeypatch, telegram_calls, ok=False)
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", always_fail)

    with pytest.raises(SystemExit) as exc_info:
        main_mod.main()

    assert exc_info.value.code == 2


def test_push_saved_file_has_no_telegram_secrets(monkeypatch, _logs_dir):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "999:SECRET-TOKEN")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "-100777")
    telegram_calls: list = []
    _push_setup(monkeypatch, telegram_calls)

    main_mod.main()

    content = next(_logs_dir.glob("report-*.txt")).read_text(encoding="utf-8")
    assert "SECRET-TOKEN" not in content
    assert "-100777" not in content


def test_push_redacts_secret_leaked_into_report(monkeypatch, _logs_dir):
    """수집 오류 문자열에 키가 섞여 들어와도 보관본에는 남지 않는다."""
    monkeypatch.setenv("ALPACA_API_KEY", "AKLEAKED")

    def leaky(self):
        raise RuntimeError("auth failed for AKLEAKED")

    telegram_calls: list = []
    _push_setup(monkeypatch, telegram_calls)
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", leaky)

    with pytest.raises(SystemExit):
        main_mod.main()

    content = next(_logs_dir.glob("report-*.txt")).read_text(encoding="utf-8")
    assert "AKLEAKED" not in content
    assert "수집 실패" in content


def test_emit_saves_nothing(monkeypatch, capsys, _logs_dir):
    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", _good_collect)
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--emit"])

    main_mod.main()

    assert not _logs_dir.exists() or not list(_logs_dir.glob("report-*.txt"))


# ── 비용 반영 줄: 두 소스 모두 설정 비용으로 ──────────────────────────────────


def test_emit_reprices_both_sources_at_configured_cost(monkeypatch, capsys):
    """실제 collect() 를 돌리고 TradingClient 만 가짜로. 두 호출 지점 모두 비용을 받아야 한다."""
    from datetime import UTC, datetime
    from decimal import Decimal
    from unittest.mock import MagicMock, patch

    from alpaca.trading.enums import OrderSide, OrderStatus

    def _order(side, price, minute):
        o = MagicMock()
        o.symbol = "AAPL"
        o.side = side
        o.filled_qty = Decimal("10")
        o.filled_avg_price = Decimal(str(price))
        o.status = OrderStatus.FILLED
        o.submitted_at = datetime(2026, 9, 1, 19, minute, tzinfo=UTC)
        o.filled_at = None
        return o

    for var, val in {
        "ALPACA_API_KEY": "k1",
        "ALPACA_SECRET_KEY": "s1",
        "ALPACA_PAPER_API_KEY": "k2",
        "ALPACA_PAPER_API_SECRET": "s2",
        "COST_PER_LEG": "0.002",
    }.items():
        monkeypatch.setenv(var, val)
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--emit"])

    with patch("bstockreport.sources.alpaca.TradingClient") as MC:
        inst = MC.return_value
        hist = MagicMock()
        hist.equity = [100.0, 101.0]
        hist.timestamp = None
        inst.get_portfolio_history.return_value = hist
        inst.get_orders.return_value = [
            _order(OrderSide.BUY, 100.0, 0),
            _order(OrderSide.SELL, 101.0, 1),
        ]
        inst.get_all_positions.return_value = []
        acct = MagicMock()
        acct.equity = "10000"
        acct.cash = "5000"
        inst.get_account.return_value = acct
        main_mod.main()

    out = capsys.readouterr().out
    # +1.00% 페이퍼 왕복 − 2 × 20bp = +0.60%
    line = "비용 반영(20bp/leg): 평균 +0.60% · 승률 100.0% · 페이퍼 체결은 실제보다 저렴"
    assert out.splitlines().count(line) == 2
