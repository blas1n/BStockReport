"""표면 검증 테스트: 리포트가 텔레그램에 도착했을 때 한 글자도 빠짐없는지 확인.

실제 폰·실제 텔레그램 API 로는 절대 나가지 않는다.
``redirect`` 픽스처가 ``urllib.request.urlopen`` 을 몽키패치해 모든
outbound HTTP 요청을 로컬 ``TelegramStub`` 서버(127.0.0.1:임의포트)로 가로챈다.

잡는 결함의 성질
-----------------
유닛 테스트와 DB 조회는 리포트 *생성* 로직만 검증한다.
다음 두 결함은 수신자 쪽 텍스트를 직접 읽어야만 탐지된다:

1. **숫자 날조 (조용한 잘림)** — 텔레그램 4096자 제한에 걸려 리포트가
   중간에 잘린다. 200 OK 가 반환되므로 전송 성공 여부 확인만으로는 안 잡힌다.
   예: '현금 $922,010' → '현금 $922,0'

2. **전달 경로 사망 (전체 미도착)** — send_telegram() 이 예외를 삼키고
   False 를 반환해 아무것도 보내지 않는다.
   생성 로직이 정상이므로 생성 단계 테스트로는 감지 불가.

실행:
    uv run pytest -m surface tests/surface/ -v
"""

import urllib.request

import pytest
from stub_telegram import TelegramStub

from bstockreport.delivery import send_telegram
from bstockreport.metrics import SourceMetrics
from bstockreport.report import build

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def stub() -> TelegramStub:
    with TelegramStub() as s:
        yield s  # type: ignore[misc]


@pytest.fixture()
def redirect(stub: TelegramStub, monkeypatch: pytest.MonkeyPatch) -> None:
    """send_telegram 이 api.telegram.org 대신 스텁으로 향하게 한다.

    프로덕션 코드를 수정하지 않고, urllib.request.urlopen 을 래핑해
    URL 만 교체한다.
    """
    _orig = urllib.request.urlopen

    def _urlopen(req: urllib.request.Request, *args: object, **kwargs: object) -> object:
        if isinstance(req, urllib.request.Request) and "api.telegram.org" in req.full_url:
            req.full_url = req.full_url.replace(
                "https://api.telegram.org",
                f"http://127.0.0.1:{stub.port}",
            )
        return _orig(req, *args, **kwargs)

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen)


@pytest.fixture()
def normal_metrics() -> SourceMetrics:
    """정상 거래 메트릭스 — 결함 재현용: 현금 $922,010 이 잘리면 안 된다."""
    return SourceMetrics(
        name="BStalk3r",
        ok=True,
        days=90,
        equity_start=900_000.0,
        equity_end=922_010.0,
        ret_pct=2.45,
        vol_pct=12.3,
        sharpe=1.82,
        mdd_pct=-3.5,
        fills=47,
        total_orders=50,
        fill_rate=94.0,
        rt_count=23,
        rt_avg_pct=1.12,
        rt_med_pct=0.85,
        rt_win_pct=60.9,
        pos_count=8,
        equity=922_010.0,
        cash=922_010.0,
        long_mv=700_000.0,
        upl=5_000.0,
    )


@pytest.fixture()
def anomaly_metrics() -> SourceMetrics:
    """이상징후 경고가 포함된 메트릭스 — 경고 줄이 잘리면 안 된다."""
    return SourceMetrics(
        name="BStalk3r-Anomaly",
        ok=True,
        days=90,
        equity_start=1_000_000.0,
        equity_end=900_000.0,
        ret_pct=-10.0,
        vol_pct=25.0,
        sharpe=-0.5,
        mdd_pct=-12.0,  # ≤ -8% → ⚠️ 최대낙폭
        fills=30,
        total_orders=50,
        fill_rate=60.0,  # < 85% → ⚠️ 체결률
        rt_count=15,
        rt_avg_pct=-1.5,
        rt_med_pct=-1.2,
        rt_win_pct=33.0,  # < 45% → ⚠️ 승률
        pos_count=3,
        equity=900_000.0,
        cash=-50_000.0,
        long_mv=950_000.0,
        upl=-20_000.0,
        is_margin=True,  # → ⚠️ 마진 계좌
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.surface
def test_normal_report_arrives_intact(
    normal_metrics: SourceMetrics,
    stub: TelegramStub,
    redirect: None,
) -> None:
    """정상 리포트가 한 글자도 잘리지 않고 스텁에 도착하는지 확인."""
    report = build([normal_metrics], verbatim=False)

    assert "현금 $922,010" in report, "픽스처 확인 실패: 보고서에 현금 액수가 없습니다"

    ok = send_telegram(report, bot_token="test-token", chat_id="test-chat")

    assert ok, "send_telegram 이 False 반환 — 전달 경로 사망"

    received = stub.combined_text()
    assert received == report, (
        f"리포트가 잘렸습니다!\n"
        f"원본 {len(report)}자 → 수신 {len(received)}자\n"
        f"누락 구간: {report[len(received) :]!r}"
    )


@pytest.mark.surface
def test_anomaly_report_arrives_intact(
    anomaly_metrics: SourceMetrics,
    stub: TelegramStub,
    redirect: None,
) -> None:
    """이상징후 경고 줄이 포함된 리포트가 한 글자도 잘리지 않고 도착하는지 확인."""
    report = build([anomaly_metrics], verbatim=False)

    assert "이상징후" in report, "픽스처 확인 실패: 이상징후 줄이 없습니다"

    ok = send_telegram(report, bot_token="test-token", chat_id="test-chat")

    assert ok, "send_telegram 이 False 반환 — 전달 경로 사망"

    received = stub.combined_text()
    assert received == report, (
        f"이상징후 리포트가 잘렸습니다!\n"
        f"원본 {len(report)}자 → 수신 {len(received)}자\n"
        f"누락 구간: {report[len(received) :]!r}"
    )


@pytest.mark.surface
def test_large_report_all_chunks_arrive(
    stub: TelegramStub,
    redirect: None,
) -> None:
    """3500자 초과 리포트가 청크로 분할돼도 전체 내용이 스텁에 도착하는지 확인."""
    metrics_list = [
        SourceMetrics(
            name=f"Source{i:02d}",
            ok=True,
            days=90,
            equity_start=1_000_000.0,
            equity_end=1_100_000.0,
            ret_pct=10.0,
            vol_pct=15.0,
            sharpe=1.5,
            mdd_pct=-5.0,
            fills=50,
            total_orders=55,
            fill_rate=90.9,
            rt_count=25,
            rt_avg_pct=0.8,
            rt_med_pct=0.6,
            rt_win_pct=56.0,
            pos_count=10,
            equity=1_100_000.0,
            cash=100_000.0,
            long_mv=1_000_000.0,
            upl=50_000.0,
        )
        for i in range(20)
    ]

    report = build(metrics_list, verbatim=False)
    assert len(report) > 3500, f"전제 실패: 리포트({len(report)}자)가 청크 크기(3500자) 이하입니다"

    ok = send_telegram(report, bot_token="test-token", chat_id="test-chat")

    assert ok, "send_telegram 이 False 반환 — 청크 전송 실패"
    assert len(stub.received) > 1, (
        f"청크 분할 안 됨: 스텁이 메시지를 {len(stub.received)}개만 수신했습니다"
    )

    received = stub.combined_text()
    assert received == report, (
        f"청크 분할 후 리포트가 잘렸습니다!\n"
        f"원본 {len(report)}자 → 수신 {len(received)}자\n"
        f"청크 수: {len(stub.received)}\n"
        f"누락 구간: {report[len(received) :]!r}"
    )
