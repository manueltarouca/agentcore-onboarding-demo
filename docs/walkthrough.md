# Walkthrough: one case, start to finish

## The app in four views

| View | Who | What they see |
|---|---|---|
| Client | Lusitania Holdings SGPS | Application status and the documents still needed. Never the screening results |
| Relationship manager | Rita Almeida | Her case: status, documents still missing, company verified, beneficial owners, screening, decision |
| Compliance officer | Compliance officer | Cases the agent may not approve, why, and the Approve button |
| Engineering | You | Every step as an AgentCore primitive, the policy decisions, the trace, links to the AWS console |

All four read the same stream of events from the agent. Each shows only what that person should see:
telling a client they are under suspicion ("tipping off") is forbidden by anti-money-laundering rules.

A low-risk case (Douro Ceramics Lda) takes a shorter path: at step 6 Policy allows the agent's
approval, step 7 is skipped, and steps 8 to 10 run in the same first invocation.

## Sequence of events

```
Browser UI        Web app (FastAPI)       Cognito      AgentCore Runtime (agent)        Gateway + Policy     Lambda (bank)
    |  Run case          |                    |                 |                              |                   |
    |------------------->| sign in Rita ----->|                 |                              |                   |
    |                    |<---- access token -|                 |                              |                   |
    |                    | invoke "start" with Rita's token --->| JWT checked by Runtime       |                   |
    |<== events (SSE) ===|<========== events streamed ==========|                              |                   |
    |                    |                    |                 | 1 Memory: read conversation  |                   |
    |                    |                    |                 | 2 tool call as Rita -------->| Policy: ALLOW --->| registry_lookup
    |                    |                    |                 | 3 Browser: read registry page                    |
    |                    |                    |                 | 4 Code Interpreter: run the model's script       |
    |                    |                    |                 | 5 tool calls as Rita ------->| Policy: ALLOW --->| screen_person x2
    |                    |                    |                 | 6 approve as Rita ---------->| Policy: DENY      |
    |                    |                    |                 |   compliance case as Rita -->| Policy: ALLOW --->| create_compliance_case
    |<== awaiting approval ===================================|  (workflow paused in the session's microVM)        |
    |                                                                                                              |
    |  Approve (compliance view)                                                                                   |
    |------------------->| sign in compliance.officer ------->|                                                    |
    |                    | invoke "approve", same session id ->| resumes the paused workflow                       |
    |                    |                    |                 | 7 approve as officer ------->| Policy: ALLOW --->| approve_customer
    |                    |                    |                 | 8 Memory: long-term records for Rita              |
    |                    |                    |                 | 9 Evaluations: score the session from its spans   |
    |                    |                    |                 | 10 Agent Registry: publish the lookup tool        |
    |<== run completed =======================================|                                                    |
```

## What each step proves

| # | Step | Primitive | The point to make |
|---|---|---|---|
| 1 | Intake | Memory | The agent remembers what Rita already said and asks only for what is missing |
| 2 | Company lookup | Gateway | An existing system becomes an MCP tool; the call carries Rita's identity |
| 3 | Registry page | Browser | A website with no API, read by a managed browser (screenshot in the UI) |
| 4 | Ownership | Code Interpreter | The model writes the maths, a sandbox runs it, we check it against a tested reference |
| 5 | Screening | Gateway | Only people are screened; Miguel Santos is a politically exposed person, risk medium |
| 6 | Approval attempt | Policy | The agent tries to approve; Cedar says no for medium risk. The agent prepares, a person decides |
| 7 | Human approval | Identity | Same tool, different person: Policy allows it for compliance.officer |
| 8 | Long-term memory | Memory | Facts, preferences and lessons extracted for the next case |
| 9 | Evaluation | Evaluations | An LLM judge scores the run from CloudWatch traces (it once caught a vague prompt) |
| 10 | Publish tool | Agent Registry | Share the tool with other teams (shows "Not permitted" where the account does not allow it) |

## Two things to point at

- **Two invocations, one session.** The first call stops at the human decision. The second call,
  with a different person's token, lands in the same session where the workflow is waiting.
- **Policy sits outside the model.** No prompt can talk the agent past the Cedar rule, because the
  Gateway checks every tool call before it reaches the bank's systems.
