# BStockReport

bstalk3r · bloasis 두 Alpaca 페이퍼 계좌를 **같은 시점에 측정**하고, 한국어 애널리스트 **해설**을 붙여
**하나의 리포트**로 텔레그램에 보내는 도구.

두 트레이딩 프로젝트의 코드에 의존하지 않는다 — 계좌(Alpaca API)와 DB만 **읽기 전용**으로 본다.

## 두 가지 실행 모드

| 모드 | 명령 | 해설 | 전송 | 용도 |
|---|---|---|---|---|
| **A (자립)** | `bstockreport run --push` | 로컬 Ollama (실패 시 규칙기반 폴백) | 직접 텔레그램 | launchd 주간 실행 |
| **B (BSVibe)** | `bstockreport run --emit` | 없음 (BSVibe 에이전트가 작성) | 없음 (BSVibe가 딜리버) | BSVibe 스케줄 run |

Mode B에서는 숫자 블록을 `<<REPORT_VERBATIM>> … <<END>>` 마커로 감싸 출력한다.
BSVibe 에이전트는 그 블록을 **그대로 복사**하고 해설만 아래에 덧붙인다(숫자 드리프트 방지).

## 측정 대상

| 소스 | 계좌 | 자격 env |
|---|---|---|
| BStalk3r | Alpaca 페이퍼 | `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` |
| Bloasis | Alpaca 페이퍼 (별개 계좌) | `ALPACA_PAPER_API_KEY` / `ALPACA_PAPER_API_SECRET` |

지표: 자산곡선(수익·변동성·Sharpe·최대낙폭), 체결률, 완료 왕복거래(FIFO 매칭 → 평균·중앙·승률),
보유 포지션·현금(마진 여부). 각 소스의 백테스트 기준선과 비교한다.

## 원칙

1. **측정 전용** — 주문을 내지 않는다. 계좌를 읽기만 한다.
2. **절대 실패하지 않는다** — 한 소스가 죽어도 나머지는 보고한다. LLM이 죽으면 규칙기반 해설로 폴백한다.
3. **냉정한 해설** — 소표본의 높은 성과는 운일 가능성을 명시하고, 백테스트로의 회귀를 기본 시나리오로 둔다.

## 개발

설계 문서: `docs/DESIGN.md` (구현은 이 문서를 따른다)

```bash
uv sync --extra dev
uv run pytest --cov=src/bstockreport --cov-fail-under=80
uv run ruff check src/ tests/
```
