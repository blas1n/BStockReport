"""로컬 텔레그램 API 스텁 서버 (표준 라이브러리만 사용).

실제 api.telegram.org 에 연결하지 않는다. 모든 요청은 127.0.0.1 의
임의 포트에서 실행되는 인메모리 HTTP 서버가 받는다. 실제 폰으로 메시지가
나가는 일은 구조적으로 불가능하다.

표면 검증 테스트(test_report_delivery_surface.py)의 ``redirect`` 픽스처가
``urllib.request.urlopen`` 을 몽키패치해 send_telegram() 의 outbound 요청을
이 스텁으로 돌린다. 테스트는 ``combined_text()`` 로 수신된 텍스트를 원본
리포트와 비교해 잘림·미도착 결함을 탐지한다.
"""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any


class _StubServer(HTTPServer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.received: list[dict[str, Any]] = []


class _Handler(BaseHTTPRequestHandler):
    server: _StubServer  # type: ignore[assignment]

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        data: dict[str, Any] = json.loads(body)
        self.server.received.append(data)

        response = json.dumps(
            {
                "ok": True,
                "result": {
                    "message_id": len(self.server.received),
                    "chat": {"id": data.get("chat_id"), "type": "private"},
                    "date": 1_700_000_000,
                    "text": data.get("text", ""),
                },
            }
        ).encode()

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, *args: object) -> None:
        pass  # 테스트 출력 억제


class TelegramStub:
    """표면 검증용 로컬 텔레그램 API 스텁.

    127.0.0.1 의 임의 포트에서 실행되며, POST /bot<token>/sendMessage 를
    받아 본문을 메모리에 누적하고 {"ok": true, "result": {...}} 로 응답한다.
    외부 네트워크 연결 없음 — api.telegram.org 에 단 한 바이트도 나가지 않는다.

    사용 예::

        with TelegramStub() as stub:
            # 테스트 코드에서 stub.port 를 이용해 요청을 스텁으로 돌림
            ...
            assert stub.combined_text() == original_report
    """

    def __init__(self) -> None:
        self._server = _StubServer(("127.0.0.1", 0), _Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self._server.server_address[1]

    @property
    def received(self) -> list[dict[str, Any]]:
        """스텁이 수신한 요청 본문 목록."""
        return self._server.received

    def combined_text(self) -> str:
        """수신한 모든 'text' 필드를 도착 순서대로 이어붙인다."""
        return "".join(msg.get("text", "") for msg in self.received)

    def start(self) -> "TelegramStub":
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()

    def __enter__(self) -> "TelegramStub":
        return self.start()

    def __exit__(self, *args: object) -> None:
        self.stop()
