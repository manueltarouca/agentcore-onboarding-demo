#!/usr/bin/env bash
# Show the stack state and any resource still in progress, with how long it has been waiting.
# Usage: scripts/deploy_status.sh [stack-name]
set -euo pipefail
STACK="${1:-OnboardingAgentDemo}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"
echo "Stack: $(aws cloudformation describe-stacks --stack-name "$STACK" --query 'Stacks[0].StackStatus' --output text 2>/dev/null || echo NOT_FOUND)"
aws cloudformation describe-stack-events --stack-name "$STACK" --max-items 200 \
  --query 'StackEvents[].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]' --output json 2>/dev/null |
python3 -c '
import json, sys, datetime
events = json.load(sys.stdin)
latest = {}
for ts, rid, status, reason in reversed(events):   # oldest first, keep the last status per resource
    latest[rid] = (ts, status, reason)
now = datetime.datetime.now(datetime.timezone.utc)
waiting = [(rid, ts, s) for rid, (ts, s, _) in latest.items() if s.endswith("IN_PROGRESS")]
for rid, ts, s in sorted(waiting, key=lambda x: x[1]):
    age = (now - datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))).total_seconds() / 60
    print(f"  {age:5.1f} min  {s:22} {rid}")
failed = [(rid, r) for rid, (_, s, r) in latest.items() if s.endswith("FAILED") and r and "cancelled" not in r]
for rid, r in failed[:5]:
    print(f"  FAILED {rid}: {r[:220]}")
'
