import json
import urllib.request

from bstockreport.delivery import _split, send_telegram


class _FakeResp:
    def __init__(self, status: int = 200):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


# ── _split 단위 테스트 ────────────────────────────────────────────────────────


def test_split_short_text_single_chunk():
    assert _split("hello") == ["hello"]


def test_split_empty_returns_original():
    result = _split("")
    assert result == [""]


def test_split_long_text_multiple_chunks():
    line = "x" * 100 + "\n"
    text = line * 40  # 4040 chars
    chunks = _split(text)
    assert len(chunks) >= 2


def test_split_on_line_boundary():
    line = "a" * 100 + "\n"
    text = line * 40
    chunks = _split(text)
    for chunk in chunks:
        for sub_line in chunk.splitlines():
            assert len(sub_line) <= 100


def test_split_single_long_line_kept_intact():
    long_line = "z" * 4000
    chunks = _split(long_line)
    assert long_line in "".join(chunks)


# ── send_telegram ────────────────────────────────────────────────────────────


def test_empty_token_returns_false_no_call(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: calls.append(req) or _FakeResp())
    assert send_telegram("hello", bot_token="", chat_id="123") is False
    assert len(calls) == 0


def test_empty_chat_id_returns_false_no_call(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: calls.append(req) or _FakeResp())
    assert send_telegram("hello", bot_token="tok", chat_id="") is False
    assert len(calls) == 0


def test_short_text_single_call_returns_true(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: calls.append(req) or _FakeResp())
    assert send_telegram("hi", bot_token="tok", chat_id="123") is True
    assert len(calls) == 1


def test_long_text_splits_into_multiple_calls(monkeypatch):
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: calls.append(req) or _FakeResp())
    line = "x" * 100 + "\n"
    text = line * 40  # 4040 chars
    result = send_telegram(text, bot_token="tok", chat_id="123")
    assert result is True
    assert len(calls) >= 2


def test_chunks_sent_respect_line_boundaries(monkeypatch):
    chunks_sent = []

    def fake_urlopen(req):
        payload = json.loads(req.data.decode())
        chunks_sent.append(payload["text"])
        return _FakeResp()

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    line = "b" * 100 + "\n"
    text = line * 40
    send_telegram(text, bot_token="tok", chat_id="123")
    for chunk in chunks_sent:
        for sub_line in chunk.splitlines():
            assert len(sub_line) <= 100


def test_non_200_response_returns_false(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: _FakeResp(status=400))
    assert send_telegram("hello", bot_token="tok", chat_id="123") is False


def test_exception_returns_false(monkeypatch):
    def raise_err(req):
        raise OSError("timeout")

    monkeypatch.setattr(urllib.request, "urlopen", raise_err)
    assert send_telegram("hello", bot_token="tok", chat_id="123") is False


def test_correct_url_used(monkeypatch):
    reqs = []
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: reqs.append(req) or _FakeResp())
    send_telegram("hi", bot_token="MYTOKEN", chat_id="42")
    assert len(reqs) == 1
    assert "MYTOKEN" in reqs[0].full_url
    assert "/sendMessage" in reqs[0].full_url


def test_all_chunks_success_returns_true(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req: _FakeResp(200))
    line = "c" * 100 + "\n"
    result = send_telegram(line * 40, bot_token="tok", chat_id="99")
    assert result is True
