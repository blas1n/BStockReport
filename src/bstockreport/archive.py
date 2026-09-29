"""보낸 리포트 보관 — 매주 실제로 무엇이 나갔는지 감사할 수 있게 한다.

파일: ``<logs_dir>/report-YYYYMMDD-HHMMSS.txt`` (실행 시각 기준, 로컬 시간).
머리말(``# status: sent|unsent``, ``# saved_at: ...``) 뒤 빈 줄 하나, 그 뒤는
텔레그램에 보낸(또는 보내려던) 본문 그대로다. 자격 값은 ``***`` 로 가린다.
"""

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

_MASK = "***"


def _redact(text: str, secrets: Iterable[str]) -> str:
    # 긴 값부터 가려야 짧은 값이 긴 값의 일부만 가려 나머지를 남기지 않는다.
    for secret in sorted({s for s in secrets if s}, key=len, reverse=True):
        text = text.replace(secret, _MASK)
    return text


def save_sent_report(
    text: str,
    *,
    logs_dir: Path,
    sent: bool,
    now: datetime,
    secrets: Iterable[str] = (),
) -> Path:
    """보낸 본문을 실행 단위 파일로 남기고 그 경로를 돌려준다."""
    logs_dir.mkdir(parents=True, exist_ok=True)
    path = logs_dir / f"report-{now:%Y%m%d-%H%M%S}.txt"
    status = "sent" if sent else "unsent"
    header = f"# status: {status}\n# saved_at: {now.isoformat()}\n"
    path.write_text(header + "\n" + _redact(text, secrets), encoding="utf-8")
    return path
