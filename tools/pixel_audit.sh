#!/usr/bin/env bash
# 슬라이드별 텍스트 가림률 측정. 사용: tools/pixel_audit.sh <page> <slideCount>
set -uo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
P="$1"; N="$2"; OUT="$ROOT/.shots/px"; mkdir -p "$OUT"
PORT=8823
render(){ google-chrome --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 \
  --window-size=1920,1080 --virtual-time-budget=3500 \
  --screenshot="$2" "http://127.0.0.1:$PORT/tools/audit-pixel.html?p=$P&s=$3&m=$4" >/dev/null 2>&1; }
for i in $(seq 1 "$N"); do
  ( render x "$OUT/$P-$i-full.png" "$i" mark
    render x "$OUT/$P-$i-only.png" "$i" only ) &
  while [ "$(jobs -r | wc -l)" -ge 4 ]; do wait -n; done
done
wait
