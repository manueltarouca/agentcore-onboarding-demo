# What is real

Everything AgentCore in this demo is the real service, called from the agent in your account.
Two things stand in for systems a bank already has, because they are not part of AgentCore.

| Part | Real or stand-in | Notes |
|---|---|---|
| Runtime, Gateway, Policy, Memory, Browser, Code Interpreter, Evaluations, Observability | Real | Provisioned with CDK (`infra/stack.py`) or created by AWS on first use |
| Agent Registry | Real call | Created at runtime (no CDK construct yet). If the account does not allow it, the UI shows "Not permitted". Works in an account with Registry permissions |
| Cognito | Real | The identity provider. Two users: `rita.almeida` and `compliance.officer`, passwords in Secrets Manager |
| Model | Real | `global.anthropic.claude-sonnet-4-6` on Amazon Bedrock |
| Bank systems (registry lookup, screening, cases, approval) | Stand-in | One Lambda (`backend/src/onboarding_demo/tools_lambda.py`) with fixed data for the Lusitania case |
| Company registry website | Stand-in | A static page on S3 and CloudFront (`infra/registry_page/index.html`), read by the real Browser |

Replay mode plays back a recording of a real live run. It does not call AWS.
