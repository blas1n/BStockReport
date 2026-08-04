import json
import re
import urllib.request

_SYSTEM_PROMPT = (
    "극도로 솔직하고 냉정한 퀀트 애널리스트로서 해요체로 답해요. "
    "주어진 수치만 근거로 삼고 자화자찬은 금지해요. "
    "소표본의 높은 성과는 운일 가능성이 높으니 백테스트로의 회귀가 기본 시나리오임을 명시해요. "
    "체결률은 비용·슬리피지 검증 관점으로 해석하고, 마진은 리스크로 짚어요. "
    "새 수치를 지어내지 말고, 불릿 3~5개로 간결하게 작성해요."
)

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def llm_commentary(report_text: str, *, model: str, host: str, timeout_s: float) -> str | None:
    payload = json.dumps(
        {
            "model": model,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 500},
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": report_text},
            ],
        }
    ).encode()

    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = json.loads(resp.read())
    except Exception:
        return None

    if "error" in body:
        return None

    content = body.get("message", {}).get("content", "") or ""
    content = _THINK_RE.sub("", content).strip()

    if len(content) < 30:
        return None

    return content
