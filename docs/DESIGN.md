# BStockReport — 설계 문서

> 상태: **설계 단계 (구현 보류)**. BSVibe 수정 완료 후 형님 노티로 개발 착수.
> 개발 주체: **BSVibe dogfooding** (product-builder를 greenfield repo에 물리는 실전 테스트).
> 최종 수정: 2026-08-03

## 1. 목표

bstalk3r(RSI-2 페이퍼)와 bloasis(트레이딩 플랫폼) **두 계좌를 같은 시점에 측정**하고,
각각 한국어 애널리스트 **해설**을 붙여 **하나의 리포트**로 텔레그램에 푸시한다.

- 독립 repo `blas1n/BStockReport` — 두 프로젝트 코드에 **의존하지 않고** 계좌/DB만 읽는다(측정 전용).
- 이유: 두 트레이딩 repo는 각자 독립 유지, 리포팅은 횡단 관심사이므로 분리.
- 기존 bstalk3r의 `scripts/measure_paper.py`(한국어+qwen3-coder:30b 해설) 설계를 일반화·이식.

## 2. 핵심 원칙 (bstalk3r measure_paper에서 검증된 것 계승)

1. **3단 견고성**: LLM 해설 → 실패 시 규칙기반 한국어 해설 → 이상징후 플래그(항상 규칙기반).
   리포트는 **절대 실패하지 않는다**(소스 하나가 죽어도 나머지는 보고).
2. **냉정한 톤**: 소표본의 높은 성과 = 운일 가능성 명시, 백테스트로의 회귀가 기본 시나리오.
   자화자찬 금지. (시스템 프롬프트로 강제)
3. **측정 전용·읽기만**: 주문/거래를 내지 않는다. 계좌 상태와 이력을 읽어 요약만.
4. **소스 격리**: 한 소스의 API 실패가 다른 소스 보고를 막지 않는다(어댑터별 try/except).

## 3. 아키텍처 — 소스 어댑터 패턴

```
BStockReport/
  src/bstockreport/
    __init__.py
    config.py            # pydantic-settings: 소스별 자격/경로, LLM, 텔레그램
    metrics.py           # @dataclass SourceMetrics — 공통 지표 계약(아래 3.1)
    commentary.py        # 규칙기반 한국어 해설 + 이상징후 플래그(소스 무관)
    llm.py               # Ollama(litellm) 호출 + 폴백. BSVibe 모델 라우팅도 지원
    report.py            # 여러 SourceMetrics → 한국어 결합 리포트 텍스트
    delivery.py          # 텔레그램 푸시(청크). BSVibe telegram 커넥터 경로도 지원
    sources/
      base.py            # Source ABC: name, collect() -> SourceMetrics
      bstalk3r.py        # Alpaca 페이퍼 어댑터(아래 4)
      bloasis.py         # bloasis 어댑터(아래 5 — 조사 반영 예정)
    main.py              # CLI: `bstockreport run`
                         #   --emit   : 결정적 지표+규칙기반 팩트만 출력(Mode B, BSVibe가 해설·전송)
                         #   --push   : Mode A(자립) — 로컬 Ollama 해설 + 텔레그램 push까지
  scripts/
    weekly-report.sh     # launchd 래퍼(.env 로드→run→푸시). BSVibe 이관 전 잠정
  tests/
    test_commentary.py   # 이상징후 분기·규칙해설(측정 무관, 순수)
    test_llm.py          # LLM 모킹/스트립/폴백
    test_report.py       # 결합 리포트 포맷·소스 실패 격리
    test_bstalk3r_source.py  # Alpaca 클라이언트 모킹
    test_bloasis_source.py   # bloasis 소스 모킹
  pyproject.toml         # uv, py3.11, ruff, pytest, alpaca-py
  .env.example
  README.md
```

### 3.1 공통 지표 계약 — `SourceMetrics`

두 소스가 **같은 dataclass**를 채운다(측정 방식은 어댑터가 흡수). 리포트/해설은 이 계약만 안다.

```python
@dataclass
class SourceMetrics:
    name: str  # "BStalk3r" / "Bloasis"
    ok: bool  # 수집 성공 여부(False면 리포트에 에러줄만)
    error: str | None = None

    # 자산곡선
    days: int = 0
    equity_start: float | None = None
    equity_end: float | None = None
    ret_pct: float | None = None
    vol_pct: float | None = None
    sharpe: float | None = None
    mdd_pct: float | None = None
    small_sample: bool = False  # days < 60

    # 체결·왕복
    fills: int | None = None
    total_orders: int | None = None
    fill_rate: float | None = None
    rt_count: int | None = None
    rt_avg_pct: float | None = None
    rt_med_pct: float | None = None
    rt_win_pct: float | None = None

    # 포지션·현금
    pos_count: int | None = None
    equity: float | None = None
    cash: float | None = None
    long_mv: float | None = None
    upl: float | None = None
    is_margin: bool = False

    # 소스별 기준선(백테스트 등) — 비교 앵커. None이면 비교줄 생략
    baseline: str | None = None  # 예: "거래당 +0.32% · 승률 63% · Sharpe ~0.72"
    baseline_trade_pct: float | None = None
    baseline_win_pct: float | None = None
```

> 소스마다 없는 필드는 None → 리포트/해설이 자동으로 해당 줄을 생략(measure_paper의 `if key in m` 패턴).

## 4. Alpaca 페이퍼 소스 (공용) — 확정

**핵심 단순화**: bstalk3r도 bloasis도 **Alpaca 페이퍼 계좌**를 쓴다(조사 확인). 그래서 어댑터는
**키쌍으로 파라미터화된 하나의 `AlpacaPaperSource`**로 두 소스를 모두 커버한다.
기존 `measure_paper.py`의 `_collect()` 로직 그대로 이식. 읽기 전용.

```python
class AlpacaPaperSource(Source):
    def __init__(self, name, key_env, secret_env, baseline=None): ...

    # get_portfolio_history(period="3M", timeframe="1D") → vol/Sharpe/maxDD
    # get_orders(ALL, limit=500) filled → FIFO 매칭 → 왕복 P&L·승률
    # get_account()+get_all_positions() → 마진 여부(cash<0)
```

- **bstalk3r 인스턴스**: `key_env="ALPACA_API_KEY"`, `secret_env="ALPACA_SECRET_KEY"`,
  baseline=`거래당 +0.32% · 승률 63% · Sharpe ~0.72 (비용 10bps/leg, 2년)`
  (`baseline_trade_pct=0.32`, `baseline_win_pct=63`).
- **bloasis 인스턴스**: `key_env="ALPACA_PAPER_API_KEY"`, `secret_env="ALPACA_PAPER_API_SECRET"`,
  baseline=bloasis.db에서 로드(§5).

> FIFO 왕복/승률을 우리가 Alpaca `get_orders`에서 직접 계산하므로, bloasis에 페이퍼 승률 명령이
> 없다는 갭은 자동 해소된다(Alpaca가 체결 truth이라 pre-open reconcile 이슈도 우회).

## 5. bloasis 소스 — 확정 (조사 반영)

bloasis는 **Alpaca 페이퍼 계좌**(`AlpacaBrokerAdapter(mode="paper")`, `bloasis/broker/alpaca.py`)로
실거래하고, 모든 주문/에쿼티 스냅샷을 **로컬 SQLite `bloasis.db`**에 미러링한다.
(별도 in-memory 시뮬 `paper_simulator.py`는 dry-run 전용 — 무시.)

**측정 = §4 `AlpacaPaperSource` 인스턴스** (`ALPACA_PAPER_API_KEY`/`ALPACA_PAPER_API_SECRET`).
자산곡선·왕복·포지션 모두 Alpaca에서 직접. bloasis 코드 import 불필요(느슨 결합 유지).

**baseline 보강** (선택, 읽기전용): `bloasis.db`의 `backtest_runs` 테이블에 `win_rate`/`sharpe`/
`max_drawdown` 등 백테스트 지표가 있음. 최근/대표 백테스트 행을 읽어 bloasis baseline 문자열 구성.
- 경로: `BLOASIS_DB_PATH`(기본 `~/Works/bloasis/main/bloasis.db`), SQLite 읽기전용 열기.
- DB 없거나 백테스트 행 없으면 baseline=None → 리포트가 비교줄 생략(견고).

**참고(구현 시)**:
- bloasis의 페이퍼 스키마: `paper_sessions`/`paper_orders`/`paper_equity_snapshots`
  (`bloasis/storage/schema.py:340-418`). 우리는 Alpaca 직접이라 이 테이블 불필요하나,
  세션명/스냅샷을 리포트에 부가하고 싶으면 참조 가능.
- ⚠️ 페이퍼 승률/왕복 P&L 계산 명령은 bloasis에 **없음** → §4 FIFO로 우리가 계산(해결됨).
- bloasis Alpaca 페이퍼는 pre-open 주문을 `filled_qty=0/accepted`로 내고 나중 reconcile →
  우리가 Alpaca `get_orders(filled만)`을 읽으므로 미체결은 자연 제외(문제 없음).
- ⚠️ 스냅샷은 로테이션 run당 1행이라 불규칙 → Sharpe/vol은 bloasis.db 스냅샷이 아니라
  **Alpaca portfolio_history**(일일)로 계산하는 게 정확(그래서 §4 경로 채택).

## 6. 리포트 프레임워크

- `report.build(metrics_list)` → 한국어 결합 리포트.
  - 헤더(날짜) + 소스별 블록(자산/체결/왕복/포지션/이상징후/🧠 해설) + 소스 간 구분선.
  - 소스 `ok=False`면 그 블록은 `⚠️ {name} 수집 실패: {error}` 한 줄로.
- `commentary`:
  - `anomaly_flags(m)` — 마진/낙폭≤-8%/체결률<85%/승률<45% (항상 규칙기반).
  - `rule_commentary(m)` — 총평+회귀·실행검증·리스크·마진·소표본 경고(measure_paper 이식).
- `llm.commentary(m)` — 소스 지표를 프롬프트화 → Ollama(litellm) → 실패 시 None.
  - 시스템 프롬프트: 극도로 냉정·회귀 강제·자화자찬 금지·make-or-break(체결) 관점(검증된 버전 재사용).

## 7. LLM 해설 경로 (이중, 둘 다 코드 검증됨)

1. **로컬 Ollama 직접**(Mode A / launchd): `http://localhost:11434/api/chat`,
   `LLM_MODEL=qwen3-coder:30b`(Ollama 0.15.5가 로드 가능한 유일한 고품질 한국어 모델),
   `LLM_TIMEOUT_S=180`.(curl `--max-time`, 아키 미지원).
2. **BSVibe 모델 라우팅**(Mode B / dogfooding): BSVibe `litellm` ModelAccount 등록 →
   런타임에 `litellm.acompletion(model="ollama_chat/qwen3-coder:30b", api_base=...)` 실호출
   (BSVibe 어댑터 코드로 검증). 항상 `ollama_chat/`.
   ⚠️ 호출이 **워커 컨테이너**서 originate → `api_base=http://host.docker.internal:11434`
   (BSVibe 임베딩 설정이 이미 같은 패턴을 쓴다).
   compose에 `extra_hosts` 미선언이라 mac Docker Desktop은 자동 해결, Linux prod은 추가 필요.

## 8. 전송

- 텔레그램: `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`, 4096자 청크(measure_paper의 awk 청킹 이식).
- BSVibe dogfooding 시: BSVibe **telegram 커넥터**의 딜리버리로 대체(아래 9-B).

## 9. BSVibe Dogfooding 계획 (코드 검증 반영)

### 9-0. 역량 검증 결과 (bsvibe-app 코드 감사)
| # | 역량 | 판정 | 근거 |
|---|---|---|---|
| 1 | 텔레그램 아웃바운드 | **IMPLEMENTED** | BSVibe 내부 모듈 실 sendMessage, BSVibe 내부 모듈 `@p.outbound`, 카탈로그 등록 |
| 2 | 제품 스케줄/틱 | **IMPLEMENTED** | `workspace_schedules`(BSVibe 내부 모듈)+cron advancer+프로덕션 `ScheduleWorker`(BSVibe 내부 모듈), REST `POST /api/v1/schedules`·MCP `bsvibe_schedules_create` |
| 3 | run→텍스트 딜리버(PR불요) | **PARTIAL** | 딜리버러블→텔레그램 텍스트 경로 완전배선·repo없는 run 가능, 그러나 출력은 **에이전트가 `emit_deliverable`로 authoring**(스크립트 stdout 캡처 아님) |
| 4 | litellm 로컬모델 | **IMPLEMENTED** | `provider!="executor"`→`LiteLLMAdapter`(BSVibe 내부 모듈)→`litellm.acompletion(model,api_base)`(BSVibe 내부 모듈). ⚠️ 워커 컨테이너→호스트 Ollama `host.docker.internal:11434` |

**③ 함의 (설계 결정)**: BSVibe run은 "스크립트 stdout을 파이프"가 아니라 **LLM 에이전트가
판단·수행·authoring**하는 모델. 그래서 **숫자는 결정적 도구(BStockReport)가, 해설·전송은 BSVibe가**
맡는 분담이 정답. 에이전트가 숫자를 지어내지 않게 도구 출력에 묶어야 함.

### 9-A. 개발 이관 (product-builder dogfooding)
1. `blas1n/BStockReport` 빈 repo 생성(README+pyproject 스캐폴드만).
2. BSVibe **제품 등록**(`bsvibe_products_create`, repo_url) → **PWA에서 bootstrap 시작**
   (⚠️ MCP `products_create`는 bootstrap 자동시작 안 함 — PWA로 clone+ingest 트리거).
3. 이 설계 문서를 지식/인텐트로 투입 → 마일스톤별 **run**:
   - M1: 공통 계약(SourceMetrics)+commentary(규칙기반)+report+tests
   - M2: `AlpacaPaperSource`(§4, Alpaca 모킹 테스트) — bstalk3r+bloasis 인스턴스
   - M3: bloasis.db baseline 로더(§5) + 두 계좌 distinct 검증
   - M4: Mode A(자립: 로컬 Ollama 해설 + 텔레그램 push) + CLI + launchd 래퍼
   - M5: Mode B(BSVibe 실행 이관, 9-B)
4. executor가 PR로 구현 → 리뷰. **BSVibe가 실제 greenfield 코드를 쓰는지** 검증(진짜 dogfooding).

### 9-B. 실행 이관 (runtime dogfooding) — 역할 분담
**BStockReport**(도구, 결정적): `bstockreport run --emit` → 두 계좌 **정확한 지표 + 규칙기반 팩트**를
출력(해설·전송 없음). **BSVibe**(에이전트+인프라): 스케줄→도구 실행→라우팅된 로컬모델로 한국어 해설
authoring→텔레그램 딜리버.

**③ PARTIAL 대응 — 숫자 충실성 2중 안전판** (에이전트가 숫자를 각색/날조하는 위험 차단):
1. **verbatim 마커 블록**: `run --emit`이 전송 직전 포맷까지 끝낸 숫자 블록을 마커로 감싸 출력
   (`<<REPORT_VERBATIM>> … <<END>>`). 스케줄 프롬프트에 **"마커 안은 한 글자도 수정 금지, 그대로 복붙.
   해설은 마커 아래에만. 도구가 에러면 숫자 지어내지 말고 실패를 보고"** 규율.
2. **safe→direct 게이트**: 초기 몇 주 `output_mode="safe"`(승인큐)로 폰에서 검수하며 드리프트 0 실증 →
   확인 후 `direct`(자동전송) 전환.

> 이 소프트-보장(에이전트 복붙)은 stdout 파이프의 하드-보장과 달라 **구조적 갭**이며,
> **BSVibe 쪽 이슈로 등록됨**(결정적 "도구 출력
> verbatim 딜리버러블" 프리미티브 요청 — 다른 세션이 처리). 위 2중 안전판은 그 프리미티브 생기기 전 우회.

구체 배선(검증된 MCP/REST):
1. **로컬 모델**: `bsvibe_model_accounts_create(provider="litellm", label="local qwen3-coder",
   litellm_model="ollama_chat/qwen3-coder:30b", api_base="http://host.docker.internal:11434", api_key="ollama")`.
   ⚠️ **default로 만들면 모든 run이 로컬모델로 감** → 대신 **run-routing 규칙**(`bsvibe_run_routing_rules_create`,
   source_text="주간 트레이딩 리포트 해설" 또는 caller_id)으로 **이 리포트 run만** 로컬모델 라우팅.
2. **텔레그램 커넥터**: `bsvibe_connectors_create(connector="telegram", signing_secret=…,
   delivery_config={chat_id, bot_token})` → `bsvibe_bindings_create(product_id, connector_account_id,
   resource_id, output_mode=…)`. output_mode: **`safe`(승인큐)로 시작→검증되면 `direct`(자동전송)**.
   (bot_token≠webhook_secret 분리.)
3. **스케줄**: `bsvibe_schedules_create(kind="instruction", cron_expr="30 9 * * 1",
   text="bstockreport run --emit 실행→그 지표로 한국어 해설 작성→텔레그램 딜리버", product_id=…)`.
   (kind=`product_tick`도 가능하나 `instruction`이 작업을 명시적으로 지정해 더 안전.)
4. 성공·안정 확인 후 launchd(Mode A) 은퇴. 그 전까진 **Mode A가 신뢰 폴백**.

### 9-C. 예상 마찰 (dogfooding의 실제 소득)
- **샌드박스 실행 환경**(per-product DinD, deps·PG 없음):
  `uv`/alpaca-py 프로비저닝, **Alpaca 페이퍼 키 2쌍 주입**, bloasis.db 접근(또는 baseline 생략).
- **모델 라우팅 네트워킹**: 워커 컨테이너→호스트 Ollama `host.docker.internal`, compose `extra_hosts` 미선언
  (mac Docker Desktop 자동, Linux prod 추가 필요).
- **에이전트 숫자 충실성**: 해설이 도구 출력 숫자에 묶이도록 프롬프트/스킬 규율(지어내기 방지).
- 이 마찰들이 곧 BSVibe 제품 개선 백로그(형님이 지금 고치는 것과 합류).

## 10. 열린 결정 (개발 착수 시 확정)
- ✅ bloasis 측정 대상 확정(§5) — Alpaca 페이퍼(공용 어댑터) + bloasis.db baseline.
- ✅ **두 계좌 distinct 확인됨** (2026-08-04 라이브 검증):
  - bstalk3r `PA-REDACTED-A` — equity $1,068,541 / 현금 -$28,374(마진) / 21포지션 / 주문 196
  - bloasis `PA-REDACTED-B` — equity $1,005,310 / 현금 $922,010 / 4포지션 / 주문 14(체결 8)
  → 이중집계 없음. bloasis는 초기 단계(소표본) — 리포트가 정직하게 그대로 표시.
- 리포트 주기: bstalk3r와 동일 월 09:30 KST **단일 결합 리포트**(권장) vs 소스별 분리.
- BSVibe 실행 이관 시 Alpaca 키 관리 위치(워크스페이스 secret vs 호스트 워커 env).

