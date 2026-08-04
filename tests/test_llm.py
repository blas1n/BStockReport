import json
import urllib.request

from bstockreport.llm import llm_commentary


class _FakeResp:
    def __init__(self, body: dict):
        self._data = json.dumps(body).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def _patch(monkeypatch, body: dict):
    monkeypatch.setattr(urllib.request, "urlopen", lambda req, timeout: _FakeResp(body))


def test_normal_response_returns_string(monkeypatch):
    content = "수익률은 긍정적이에요. 소표본 주의 필요해요. 리스크 관리 중요해요."
    body = {"message": {"content": content}}
    _patch(monkeypatch, body)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=10.0)
    assert isinstance(result, str)
    assert "수익률" in result


def test_think_block_removed(monkeypatch):
    visible = "결과는 긍정적이에요. 백테스트 회귀가 기본 시나리오예요. 마진은 리스크예요."
    content = f"<think>내부 추론 과정</think>{visible}"
    body = {"message": {"content": content}}
    _patch(monkeypatch, body)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=10.0)
    assert result is not None
    assert "<think>" not in result
    assert "내부 추론 과정" not in result
    assert "결과는 긍정적이에요" in result


def test_multiline_think_block_removed(monkeypatch):
    visible = "성과는 운일 가능성 높아요. 백테스트로의 회귀를 권장해요."
    content = f"<think>\n여러 줄\n추론\n</think>{visible}"
    body = {"message": {"content": content}}
    _patch(monkeypatch, body)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=10.0)
    assert result is not None
    assert "여러 줄" not in result
    assert "성과는 운일" in result


def test_error_key_returns_none(monkeypatch):
    body = {"error": "model not found"}
    _patch(monkeypatch, body)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=10.0)
    assert result is None


def test_short_content_returns_none(monkeypatch):
    body = {"message": {"content": "짧아"}}
    _patch(monkeypatch, body)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=10.0)
    assert result is None


def test_empty_content_returns_none(monkeypatch):
    body = {"message": {"content": ""}}
    _patch(monkeypatch, body)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=10.0)
    assert result is None


def test_missing_message_key_returns_none(monkeypatch):
    body = {}
    _patch(monkeypatch, body)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=10.0)
    assert result is None


def test_network_exception_returns_none(monkeypatch):
    def raise_err(req, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(urllib.request, "urlopen", raise_err)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=10.0)
    assert result is None


def test_timeout_exception_returns_none(monkeypatch):
    def raise_timeout(req, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", raise_timeout)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=1.0)
    assert result is None


def test_content_29_chars_is_none(monkeypatch):
    body = {"message": {"content": "a" * 29}}
    _patch(monkeypatch, body)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=10.0)
    assert result is None


def test_content_30_chars_returned(monkeypatch):
    body = {"message": {"content": "a" * 30}}
    _patch(monkeypatch, body)
    result = llm_commentary("report", model="m", host="http://h", timeout_s=10.0)
    assert result == "a" * 30
