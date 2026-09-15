#!/usr/bin/env bash
# Start Acme Approvals in the background on http://localhost:8090 (override with ACME_PORT)
cd "$(dirname "$0")"
python3 -m pip install -q -r requirements.txt 2>/dev/null || python3 -m pip install -q --break-system-packages -r requirements.txt
nohup python3 app.py > acme.log 2>&1 &
echo "Acme Approvals running at http://localhost:${ACME_PORT:-8090}/ (log: acme.log)"
