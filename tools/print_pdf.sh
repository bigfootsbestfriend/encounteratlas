#!/bin/sh
# Print a built page (from _site, via a throwaway local server) to a PDF with headless Chrome, as the browser would print it.
# usage: tools/print_pdf.sh /printables/judge-a-ufo-report/ site/static/printables/judge-a-ufo-report.pdf
set -e
cd "$(dirname "$0")/.."
PORT=8799
python3 -m http.server $PORT -d _site >/dev/null 2>&1 &
SRV=$!
trap 'kill $SRV' EXIT
sleep 1
timeout 90 google-chrome-stable --headless=new --disable-gpu --no-sandbox --no-pdf-header-footer \
  --print-to-pdf="$(realpath -m "$2")" "http://localhost:$PORT$1" 2>/dev/null
