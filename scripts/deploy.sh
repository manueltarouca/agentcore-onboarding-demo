#!/usr/bin/env bash
# Deploy the stack (run on a machine with AWS credentials, Docker and the CDK CLI).
set -euo pipefail
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}" CDK_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-west-2}"
export CDK_DEFAULT_ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
cd "$(dirname "$0")/../infra"
uv sync -q
cdk deploy --require-approval never --outputs-file outputs.json
