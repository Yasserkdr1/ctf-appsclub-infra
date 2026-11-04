#!/usr/bin/env bash
# Verify public TLS/HTTP2 plus local CTFd and Caddy service status.
set -euo pipefail
DOMAIN="${1:-ctf.158.158.123.197.sslip.io}"
URL="https://${DOMAIN}/vpn"
echo "===== DNS ====="
getent ahostsv4 "$DOMAIN" | head -1 || true
echo "===== CURL TLS / HTTP VERSION ====="
if ! curl --version | grep -qi 'HTTP2'; then
  echo 'WARNING: this local curl has no HTTP/2 support; verify h2 in Chrome DevTools'
fi
curl --http2 --noproxy '*' --connect-timeout 8 --max-time 30 \
  -sS -o /dev/null \
  -w 'HTTP %{http_code} | protocol %{http_version} | TLS verify %{ssl_verify_result} | total %{time_total}s\n' \
  "$URL"
echo '===== AZURE GATEWAY ====='
ssh ctf-gateway '
  systemctl is-active caddy
  sudo ss -lntp | grep -E ":(80|443|8000) " || true
  sudo journalctl -u caddy -n 12 --no-pager
'
cat <<'STEPS'
===== CHROME PERFORMANCE CHECK =====
1. Disable Network request blocking for /events in Chrome DevTools.
2. Open HTTPS domain in a fresh tab, log in, and inspect Network > Protocol.
3. Verify page documents use h2 (or h3); /events may remain Pending.
4. Rapidly navigate Panel, Mana, Instances, Challenges, Notifications.
5. If a page stalls, record Network > Timing and /events connection count.
STEPS
