# 표면 검증 하네스 (`tests/surface/`)

## 이 하네스가 무엇인가

표면 검증 하네스는 **"도착한 텍스트"를 직접 읽어** 리포트가 수신자에게 한 글자도 빠짐없이 전달되는지 확인한다.

유닛 테스트와 DB 조회는 리포트를 *생성*하는 로직만 검증한다. 전달 경로(`send_telegram`) 위·아래에서 무슨 일이 일어나는지는 볼 수 없다. 이 하네스는 그 구간을 닫는다.

---

## 왜 이 하네스가 필요한가 — 실제 발생한 결함 두 가지

### 결함 1: 숫자 날조 (조용한 잘림)

```
원본 리포트: "현금 $922,010"
수신 문자:   "현금 $922,0"
```

텔레그램 API 의 메시지 길이 제한(4096자)에 걸려 리포트가 중간에 잘렸다.  
오류 없이 200 OK 가 반환됐기 때문에 유닛 테스트와 전송 성공 여부 확인만으로는 잡히지 않았다.

### 결함 2: 전달 경로 사망 (아무것도 미도착)

전달 코드(`send_telegram`)가 예외를 삼키고 `False` 를 반환하면서 아무 메시지도 보내지 않았다.  
생성 로직은 완벽히 동작했으므로 DB 조회나 유닛 테스트로는 전혀 감지되지 않았다.

### 왜 "도착한 텍스트"를 봐야만 잡히는가

두 결함 모두 리포트 *생성* 이후 단계에서 발생한다.  
확인하려면 실제 HTTP 응답을 받는 쪽 — 즉 수신자 입장 — 에서 텍스트를 검사해야 한다.  
이 하네스는 로컬 스텁 서버를 통해 그 수신자 역할을 수행한다.

---

## 실제 텔레그램 API · 실제 폰으로는 절대 나가지 않는다

**이 하네스는 외부 네트워크에 연결하지 않는다.**

- `stub_telegram.py` 는 `127.0.0.1` 의 임의 포트에서 실행되는 인메모리 HTTP 서버다.  
- `redirect` 픽스처가 `urllib.request.urlopen` 을 몽키패치해 `api.telegram.org` 행 요청을 모두 스텁 포트로 가로챈다.  
- 실제 봇 토큰·채팅 ID 는 사용되지 않는다 (`bot_token="test-token"`, `chat_id="test-chat"`).  
- 테스트를 네트워크 없이 오프라인에서 실행해도 통과한다.

---

## 파일 구조

```
tests/surface/
├── README.md                       # 이 파일
├── stub_telegram.py                # 로컬 텔레그램 API 스텁 서버
└── test_report_delivery_surface.py # 표면 검증 테스트 3개
```

### `stub_telegram.py`

`TelegramStub` 클래스: 표준 라이브러리(`http.server`)만으로 구현된 인메모리 HTTP 서버.  
`POST /bot<token>/sendMessage` 를 받아 본문을 메모리에 누적하고 `{"ok": true, "result": {...}}` 로 응답한다.  
`combined_text()` 로 수신된 모든 `text` 필드를 이어붙여 원본과 비교한다.

### `test_report_delivery_surface.py`

| 테스트 | 검증 내용 |
|---|---|
| `test_normal_report_arrives_intact` | 정상 리포트 — `현금 $922,010` 이 잘리지 않고 도착 |
| `test_anomaly_report_arrives_intact` | 이상징후 경고 줄이 잘리지 않고 도착 |
| `test_large_report_all_chunks_arrive` | 3500자 초과 시 청크 분할 후에도 전체 내용 도착 |

---

## 실행 방법

```bash
# 표면 검증만 실행
uv run pytest -m surface tests/surface/ -v

# 전체 테스트와 함께 실행 (표면 검증 포함)
uv run pytest tests/ -v
```

### 출력 예시 (정상)

```
tests/surface/test_report_delivery_surface.py::test_normal_report_arrives_intact PASSED
tests/surface/test_report_delivery_surface.py::test_anomaly_report_arrives_intact PASSED
tests/surface/test_report_delivery_surface.py::test_large_report_all_chunks_arrive PASSED
```

### 실패 시 메시지 예시

```
AssertionError: 리포트가 잘렸습니다!
원본 1024자 → 수신 500자
누락 구간: '현금 $922,010\n포지션 ...'
```

---

## CI 통합

`pyproject.toml` 의 `markers` 에 `surface` 마커가 등록되어 있다.  
CI 파이프라인에서 `uv run pytest -m surface tests/surface/` 를 별도 단계로 추가하면 전달 결함을 자동으로 감지할 수 있다.
