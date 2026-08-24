#!/usr/bin/env bash
# 크래쉬랩 덱 슬라이드 스크린샷.
#   tools/shot.sh <page> [slide번호|all] [width] [height]
#   예: tools/shot.sh lecture-1 3          슬라이드 3장만
#       tools/shot.sh lecture-1 all        전체 슬라이드
#       tools/shot.sh index 1 1920 1080
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PAGE="${1:?page 필요 (index|lecture-1..4)}"
SLIDE="${2:-all}"
W="${3:-1920}"; H="${4:-1080}"
OUT="$ROOT/.shots"; mkdir -p "$OUT"
PORT=8823

if ! curl -s -o /dev/null --max-time 2 "http://127.0.0.1:$PORT/"; then
  (cd "$ROOT" && nohup python3 -m http.server "$PORT" --bind 127.0.0.1 >/dev/null 2>&1 &)
  for _ in $(seq 1 25); do curl -s -o /dev/null --max-time 1 "http://127.0.0.1:$PORT/" && break; sleep 0.2; done
fi

shoot() {
  local n="$1" url="http://127.0.0.1:$PORT/$PAGE.html"
  [ "$n" != "-" ] && url="$url#slide-$n"
  local f="$OUT/$PAGE-$([ "$n" = "-" ] && echo full || printf '%02d' "$n")-${W}x${H}.png"
  google-chrome --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
    --window-size="$W,$H" --screenshot="$f" --virtual-time-budget=2500 "$url" >/dev/null 2>&1
  echo "$f"
}

if [ "$SLIDE" = "all" ]; then
  total=$(grep -oE 'class="slide( |")' "$ROOT/$PAGE.html" | wc -l)
  for i in $(seq 1 "$total"); do shoot "$i"; done
elif [ "$SLIDE" = "full" ]; then
  shoot -
else
  shoot "$SLIDE"
fi
