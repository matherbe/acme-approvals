#!/usr/bin/env bash
# One-shot install inside the lab VM (Linux).
#   git clone https://github.com/matherbe/acme-approvals ~/acme-approvals
#   bash ~/acme-approvals/install.sh
set -e
SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="$HOME/acme-approvals"
if [ "$SRC" != "$DEST" ]; then
  mkdir -p "$DEST"
  cp "$SRC"/app.py "$SRC"/mcp_server.py "$SRC"/.mcp.json "$SRC"/CLAUDE.md "$SRC"/requirements.txt "$SRC"/run.sh "$SRC"/README.md "$DEST"/
fi
chmod +x "$DEST/run.sh"
python3 -m pip install -q -r "$DEST/requirements.txt" 2>/dev/null || python3 -m pip install -q --break-system-packages -r "$DEST/requirements.txt"
pkill -f "acme-approvals/app.py" 2>/dev/null || true
cd "$DEST" && nohup python3 app.py > acme.log 2>&1 &
sleep 2
if curl -sf http://127.0.0.1:8080/health >/dev/null; then
  echo "Acme Approvals is running at http://localhost:8080"
else
  echo "App did not start; see $DEST/acme.log"; exit 1
fi
# start at boot for this user (skipped quietly if crontab is unavailable)
( crontab -l 2>/dev/null | grep -v "acme-approvals/run.sh"; echo "@reboot bash $DEST/run.sh" ) | crontab - 2>/dev/null || true
echo "Next: cd ~/acme-approvals && code -r . && claude"
