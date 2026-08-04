import sys

import bstockreport.main as main_mod
from bstockreport.metrics import SourceMetrics


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


def test_both_sources_fail_still_no_crash(monkeypatch, capsys):
    def always_fail(self):
        raise RuntimeError("always fails")

    monkeypatch.setattr(main_mod.AlpacaPaperSource, "collect", always_fail)
    monkeypatch.setattr(main_mod, "load_bloasis_baseline", lambda path: None)
    monkeypatch.setattr(sys, "argv", ["bstockreport", "run", "--emit"])

    main_mod.main()

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
