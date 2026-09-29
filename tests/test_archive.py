"""보낸 리포트 보관 — 한 주가 무엇을 받았는지 나중에 감사할 수 있어야 한다(#2)."""

from datetime import datetime, timedelta, timezone

from bstockreport.archive import save_sent_report

KST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 28, 9, 30, 5, tzinfo=KST)
TEXT = "📊 주간 리포트\n현금 $922,010\n\n• 해설 한 줄"


def _body(path):
    header, body = path.read_text(encoding="utf-8").split("\n\n", 1)
    return header, body


def test_file_name_is_per_run_under_logs_dir(tmp_path):
    path = save_sent_report(TEXT, logs_dir=tmp_path, sent=True, now=NOW)
    assert path == tmp_path / "report-20260928-093005.txt"
    assert path.exists()


def test_body_is_exact_text_sent(tmp_path):
    path = save_sent_report(TEXT, logs_dir=tmp_path, sent=True, now=NOW)
    header, body = _body(path)
    assert body == TEXT
    assert "status: sent" in header
    assert "2026-09-28T09:30:05+09:00" in header


def test_failed_send_is_marked_unsent(tmp_path):
    path = save_sent_report(TEXT, logs_dir=tmp_path, sent=False, now=NOW)
    header, body = _body(path)
    assert "status: unsent" in header
    assert body == TEXT


def test_creates_missing_logs_dir(tmp_path):
    logs = tmp_path / "nested" / "logs"
    path = save_sent_report(TEXT, logs_dir=logs, sent=True, now=NOW)
    assert path.parent == logs


def test_second_run_same_day_does_not_overwrite(tmp_path):
    first = save_sent_report("첫 번째", logs_dir=tmp_path, sent=False, now=NOW)
    second = save_sent_report(
        "두 번째", logs_dir=tmp_path, sent=True, now=NOW + timedelta(minutes=3)
    )
    assert first != second
    assert _body(first)[1] == "첫 번째"


def test_secrets_are_redacted(tmp_path):
    text = "오류: https://api.telegram.org/bot123:ABC/sendMessage chat=-1009 key=AKXYZ"
    path = save_sent_report(
        text,
        logs_dir=tmp_path,
        sent=False,
        now=NOW,
        secrets=["123:ABC", "-1009", "AKXYZ", ""],
    )
    content = path.read_text(encoding="utf-8")
    assert "123:ABC" not in content
    assert "-1009" not in content
    assert "AKXYZ" not in content
    assert "***" in content
