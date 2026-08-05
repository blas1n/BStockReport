#!/usr/bin/env bash
# BStockReport 주간 리포트 — launchd 가 매주 월 09:30 KST 에 실행한다.
#
# bstalk3r + bloasis 두 Alpaca 페이퍼 계좌를 측정해 한국어 해설과 함께
# 텔레그램으로 보낸다. 자격은 이 디렉터리의 .env 에서 온다(gitignored).
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"
mkdir -p logs

[ -f .env ] || { echo "ERROR: .env not found in $PROJECT_DIR" >&2; exit 1; }

# .env 를 프로세스 환경으로 올린다. pydantic-settings 는 .env 파일을 직접 읽지만
# 소스 어댑터는 os.environ[key_env] 로 Alpaca 키를 읽으므로, export 하지 않으면
# 키가 어댑터에 닿지 않아 두 소스가 모두 KeyError 로 실패한다(실제로 겪었다).
set -a; . ./.env; set +a

LOG="logs/weekly-$(date +%Y%m%d).log"

# 로컬 LLM 이 콜드 스타트면 첫 호출이 느리다 — 미리 깨워 둔다(실패해도 무시).
curl -s --max-time 20 "${OLLAMA_HOST:-http://localhost:11434}/api/tags" >/dev/null 2>&1 || true

# --push: 측정 → 해설(LLM, 실패 시 규칙기반) → 텔레그램 전송
if uv run bstockreport run --push >>"$LOG" 2>&1; then
  echo "$(date '+%F %T') 전송 완료" >>"$LOG"
else
  echo "$(date '+%F %T') 실패(exit $?)" >>"$LOG"
  # 리포트가 안 가는 것보다 실패를 아는 게 낫다 — 짧은 알림을 직접 보낸다.
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
      --data-urlencode "text=⚠️ BStockReport 주간 리포트 실패. $PROJECT_DIR/$LOG 확인." \
      >/dev/null || true
  fi
  exit 1
fi
