"""The two AWS calls the web app makes: sign in with Cognito, invoke the agent on Runtime."""
import asyncio
import json
from collections.abc import AsyncIterator
from urllib.parse import quote

import boto3
import httpx


class CognitoAuth:
    """Signs in the demo users. Their passwords live in Secrets Manager (created by CDK)."""

    def __init__(self, region: str, client_id: str, password_secrets: dict[str, str]):
        self.cognito = boto3.client("cognito-idp", region_name=region)
        self.secrets = boto3.client("secretsmanager", region_name=region)
        self.client_id = client_id
        self.password_secrets = password_secrets

    async def sign_in(self, username: str) -> str:
        return await asyncio.to_thread(self._sign_in, username)

    def _sign_in(self, username: str) -> str:
        password = self.secrets.get_secret_value(SecretId=self.password_secrets[username])["SecretString"]
        result = self.cognito.initiate_auth(
            ClientId=self.client_id, AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": username, "PASSWORD": password},
        )
        return result["AuthenticationResult"]["AccessToken"]


class RuntimeClient:
    """Invokes the agent on AgentCore Runtime over HTTPS with the user's bearer token.

    With a JWT authorizer the call is not signed with AWS credentials: the token is the proof.
    """

    def __init__(self, region: str, runtime_arn: str):
        self.url = (f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/"
                    f"{quote(runtime_arn, safe='')}/invocations?qualifier=DEFAULT")

    async def invoke(self, token: str, session_id: str, payload: dict) -> AsyncIterator[dict]:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "X-Amzn-Bedrock-AgentCore-Runtime-Session-Id": session_id,
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(600, connect=30)) as http:
            async with http.stream("POST", self.url, headers=headers, json=payload) as response:
                if response.status_code != 200:
                    body = (await response.aread()).decode()[:500]
                    yield {"type": "error", "at": 0, "message": f"Runtime returned {response.status_code}: {body}"}
                    return
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = json.loads(line.removeprefix("data: "))
                        yield json.loads(data) if isinstance(data, str) else data
