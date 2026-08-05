import argparse
import sys

from bstockreport.baseline import load_bloasis_baseline
from bstockreport.commentary import rule_commentary
from bstockreport.config import Settings
from bstockreport.delivery import send_telegram
from bstockreport.llm import llm_commentary
from bstockreport.metrics import SourceMetrics
from bstockreport.report import build
from bstockreport.sources.alpaca import AlpacaPaperSource


def main() -> None:
    parser = argparse.ArgumentParser(prog="bstockreport")
    sub = parser.add_subparsers(dest="cmd")
    run_cmd = sub.add_parser("run")
    group = run_cmd.add_mutually_exclusive_group()
    group.add_argument("--emit", action="store_true")
    group.add_argument("--push", action="store_true")
    args = parser.parse_args()

    push = getattr(args, "push", False)
    verbatim = not push

    settings = Settings()

    bloasis_bl = load_bloasis_baseline(settings.bloasis_db_path)

    sources = [
        AlpacaPaperSource(
            "BStalk3r",
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            baseline="거래당 +0.32% · 승률 63% · Sharpe ~0.72",
            baseline_trade_pct=0.32,
            baseline_win_pct=63.0,
        ),
        AlpacaPaperSource(
            "Bloasis",
            api_key=settings.alpaca_paper_api_key,
            secret_key=settings.alpaca_paper_api_secret,
            baseline=bloasis_bl.text if bloasis_bl else None,
            baseline_trade_pct=bloasis_bl.trade_pct if bloasis_bl else None,
            baseline_win_pct=bloasis_bl.win_pct if bloasis_bl else None,
        ),
    ]

    metrics: list[SourceMetrics] = []
    for src in sources:
        try:
            metrics.append(src.collect())
        except Exception as exc:
            metrics.append(SourceMetrics(name=src.name, ok=False, error=str(exc)))

    all_failed = all(not m.ok for m in metrics)

    report = build(metrics, verbatim=verbatim)

    if not push:
        print(report)
        if all_failed:
            sys.exit(1)
        return

    commentary = llm_commentary(
        report,
        model=settings.llm_model,
        host=settings.ollama_host,
        timeout_s=settings.llm_timeout_s,
    )
    if commentary is None:
        parts = [rule_commentary(m) for m in metrics if m.ok]
        commentary = "\n\n".join(parts) if parts else ""

    full = report
    if commentary:
        full = report + "\n\n" + commentary

    send_telegram(full, bot_token=settings.telegram_bot_token, chat_id=settings.telegram_chat_id)

    if all_failed:
        sys.exit(1)
