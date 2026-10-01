"""Who is calling the agent, read from the Cognito access token.

AgentCore Runtime has already validated the token (inbound JWT authorizer) before our
code runs, so here we only read its claims. The token itself is passed on to the Gateway.
"""
import base64
import json

from onboarding_demo.case import CASES
from onboarding_demo.workflow.ports import Caller

DISPLAY_NAMES = {"rita.almeida": "Rita Almeida", "compliance.officer": "Compliance officer",
                 **{case.client_username: case.company for case in CASES.values()}}
COMPLIANCE_GROUP = "compliance"
CLIENT_GROUP = "clients"


def caller_from_headers(headers: dict[str, str]) -> Caller:
    authorization = next(v for k, v in headers.items() if k.lower() == "authorization")
    token = authorization.removeprefix("Bearer ").strip()
    claims = _claims(token)
    username = claims.get("username", claims.get("sub", "unknown"))
    groups = claims.get("cognito:groups", [])
    role = ("Client" if CLIENT_GROUP in groups
            else "Compliance" if COMPLIANCE_GROUP in groups else "Relationship manager")
    return Caller(name=DISPLAY_NAMES.get(username, username), role=role, token=token, username=username)


def _claims(token: str) -> dict:
    payload = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
