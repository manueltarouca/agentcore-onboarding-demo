"""Run the whole case from a terminal, without the UI.

    uv run python -m onboarding_demo.web.cli            # start as Rita, approve as compliance
    uv run python -m onboarding_demo.web.cli --start-only
    uv run python -m onboarding_demo.web.cli --details      # also print what each step returned
"""
import asyncio
import json
import sys
import time
import uuid

from onboarding_demo.web import main


def describe(e: dict) -> str:
    if "type" not in e:
        return str(e)[:150]
    if e["type"] in ("tool_call", "policy_decision"):
        return f"{e['tool']} {e.get('decision', '')} as {e['caller']}"
    if e["type"] == "usage":
        return f"{e['step']} {e['input_tokens'] + e['output_tokens']} tokens {e['latency_ms']} ms"
    return str(e.get("step") or e.get("message") or e.get("totals") or "")


async def run(start_only: bool) -> None:
    session = f"onboarding-{uuid.uuid4().hex}"
    events = []
    started = time.time()
    for username, action in [("rita.almeida", "start"), ("compliance.officer", "approve")]:
        if action == "approve" and start_only:
            break
        token = await main.auth.sign_in(username)
        print(f"--- {action} as {username}")
        async for e in main.runtime.invoke(token, session, {"action": action}):
            events.append(e)
            print(f"{time.time() - started:6.1f}s  {e.get('type', 'raw'):18} {describe(e)[:150]}", flush=True)
    print("session", session)
    if "--details" in sys.argv:
        for e in events:
            if e.get("type") == "step_completed":
                detail = {k: (v if k != "screenshot" else f"<{len(v)} base64 chars>") for k, v in e["detail"].items()}
                print(f"\n## {e['step']}\n{json.dumps(detail, indent=1, default=str)[:900]}")


if __name__ == "__main__":
    asyncio.run(run("--start-only" in sys.argv))
