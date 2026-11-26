import subprocess

import pytest

import bstockreport.llm as llm_mod
from bstockreport.llm import claude_commentary

GOOD = "수익률은 소표본이라 운일 가능성이 커요. 백테스트로의 회귀가 기본 시나리오예요."


class _Proc:
    def __init__(self, returncode: int, stdout: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = ""


def _patch_run(monkeypatch, result=None, exc=None):
    calls: list = []

    def _run(argv, **kw):
        calls.append((argv, kw))
        if exc is not None:
            raise exc
        return result

    monkeypatch.setattr(subprocess, "run", _run)
    return calls


def test_returns_stripped_stdout(monkeypatch):
    _patch_run(monkeypatch, _Proc(0, f"\n{GOOD}\n"))
    assert claude_commentary("report", timeout_s=10.0) == GOOD


def test_report_goes_on_stdin_with_the_analyst_prompt(monkeypatch):
    calls = _patch_run(monkeypatch, _Proc(0, GOOD))
    claude_commentary("REPORT BODY", timeout_s=10.0)
    argv, kw = calls[0]
    assert kw["input"] == "REPORT BODY"
    assert kw["timeout"] == 10.0
    assert argv[0] == "claude" and "-p" in argv
    assert argv[argv.index("--system-prompt") + 1] == llm_mod._SYSTEM_PROMPT


def test_runs_as_a_plain_completion_with_no_tools(monkeypatch):
    """A tool-enabled session spends turns looking around instead of answering."""
    calls = _patch_run(monkeypatch, _Proc(0, GOOD))
    claude_commentary("r", timeout_s=10.0)
    argv, _ = calls[0]
    assert argv[argv.index("--disallowedTools") + 1] == "*"
    assert argv[argv.index("--setting-sources") + 1] == ""
    assert "--strict-mcp-config" in argv


def test_model_is_passed_only_when_set(monkeypatch):
    calls = _patch_run(monkeypatch, _Proc(0, GOOD))
    claude_commentary("r", timeout_s=10.0)
    assert "--model" not in calls[0][0]
    claude_commentary("r", timeout_s=10.0, model="sonnet")
    argv = calls[1][0]
    assert argv[argv.index("--model") + 1] == "sonnet"


@pytest.mark.parametrize(
    "result,exc",
    [
        (_Proc(1, GOOD), None),
        (_Proc(0, "짧음"), None),
        (None, subprocess.TimeoutExpired(cmd="claude", timeout=1)),
        (None, FileNotFoundError("claude")),
    ],
)
def test_failure_returns_none(monkeypatch, result, exc):
    _patch_run(monkeypatch, result, exc)
    assert claude_commentary("r", timeout_s=1.0) is None
