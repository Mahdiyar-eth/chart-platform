#!/bin/bash
# Runtime withdrawal race (round 2): User B creates 600k withdrawal, 3 admins resolve concurrently
set -u
COOKIE_B="8eea43d6-6c76-4946-8403-0e8c408ac2cd.b04f0ba2f7b4e061cf1f0f8043617f5df68c716a85587690779ade9297640749"
ADMIN_CK="chart_admin=8b12ecfd10326d01044deddb5e213c91304ff1873fd1e6068da4c2ca4de91f5b"

curl -s -b "chart_user=$COOKIE_B" -X POST https://chart.negar.io/api/wallet/withdraw -d 'amount_rial=600000'
echo ""
sleep 1
WID=$(sudo -u postgres psql -d chart_platform -tAc "SELECT id FROM withdrawal_requests WHERE user_id='8eea43d6-6c76-4946-8403-0e8c408ac2cd' AND status='pending' ORDER BY created_at DESC LIMIT 1")
echo "WID=$WID"
pids=""
for i in 1 2 3; do
  ( curl -s -o /tmp/wr_$i.txt -w "call$i:%{http_code}\n" -X POST -b "$ADMIN_CK" \
      "https://chart.negar.io/api/admin/withdrawals/$WID/resolve" -d "status=paid" ) &
  pids="$pids $!"
done
for p in $pids; do wait "$p"; done
for i in 1 2 3; do echo "call$i: $(head -c 60 /tmp/wr_$i.txt)"; done
sudo -u postgres psql -d chart_platform -tAc "SELECT 'status='||status FROM withdrawal_requests WHERE id='$WID'"
sudo -u postgres psql -d chart_platform -tAc "SELECT 'balance='||balance_rial FROM users WHERE phone='09120000008'"
