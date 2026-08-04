import json
import urllib.request

_CHUNK = 3500


def _split(text: str) -> list[str]:
    chunks: list[str] = []
    lines = text.splitlines(keepends=True)
    current = ""
    for line in lines:
        if len(current) + len(line) <= _CHUNK:
            current += line
        else:
            if current:
                chunks.append(current)
            current = line
    if current:
        chunks.append(current)
    return chunks or [text]


def send_telegram(text: str, *, bot_token: str, chat_id: str) -> bool:
    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    chunks = _split(text)
    for chunk in chunks:
        payload = json.dumps({"chat_id": chat_id, "text": chunk}).encode()
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                if resp.status != 200:
                    return False
        except Exception:
            return False
    return True
