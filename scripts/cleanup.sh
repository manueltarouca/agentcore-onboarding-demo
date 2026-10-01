#!/usr/bin/env bash
# Delete everything the demo created.
set -euo pipefail
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"
cd "$(dirname "$0")/../infra"
cdk destroy --force
# The agent creates its Agent Registry on first use (no CDK construct yet), so remove it here.
for id in $(aws bedrock-agentcore-control list-registries --query "registries[?name=='onboarding-tools'].registryId" --output text 2>/dev/null); do
  aws bedrock-agentcore-control delete-registry --registry-id "$id" && echo "Deleted registry $id"
done
