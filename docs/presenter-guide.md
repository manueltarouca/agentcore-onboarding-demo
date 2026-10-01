# Demo guide

Open the app and, in a second tab, the AWS console.

## Live demo (about 15 minutes)

| # | Click | Say |
|---|---|---|
| 1 | Engineering view, **Live**, **Run case** | One case, ten steps, each an AgentCore primitive |
| 2 | Watch steps 1 to 5; click **Ownership** | The model writes the maths, the sandbox runs it, we check it |
| 3 | Step 6 turns red: **DENIED** | Cedar at the Gateway. No prompt gets past it |
| 4 | **Client** tab | What the company sees: under review, two documents to send. Nothing about screening |
| 5 | **Relationship manager** tab | What Rita sees: missing documents, owners, PEP, risk medium |
| 6 | **Compliance officer** tab, **Approve** | Same session, new person. The same tool is now allowed |
| 7 | Back to Engineering, click **Evaluation** | An LLM judge scored the run from its traces |
| 8 | **Trace** tab, then the CloudWatch link | Every call, with tokens and cost |
| 9 | One or two **Open in AWS console** links (Policy, Memory) | This is where it lives in your account |

If a live run fails, switch to **Replay**: it plays the last completed live run.

## Short replay (2 minutes)

**Replay**, **2x**, **Run case** in the Engineering view. Point at the DENY, open the Compliance
officer tab, press **Approve**, open the Client tab (Approved), finish on the evaluation scores.

## Before you present

```bash
scripts/serve.sh                                               # start the web app
cd backend && uv run python -m onboarding_demo.web.cli --details   # one warm-up run
```

Approve within a few minutes: Runtime sessions end after a period of inactivity.
