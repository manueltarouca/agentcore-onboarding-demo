"""Start the web app:  uv run python -m onboarding_demo.web.main   (reads infra/outputs.json)"""
import json
import os
from pathlib import Path

import uvicorn

from onboarding_demo.web.api import create_app
from onboarding_demo.web.aws import CognitoAuth, RuntimeClient

REPO = Path(__file__).resolve().parents[4]
outputs = next(iter(json.loads((REPO / "infra" / "outputs.json").read_text()).values()))
region = outputs["Region"]

runtime = RuntimeClient(region, outputs["RuntimeArn"])
auth = CognitoAuth(region, outputs["UserPoolClientId"], {
    "rita.almeida": outputs["PasswordSecretRita"],
    "compliance.officer": outputs["PasswordSecretCompliance"],
})
app = create_app(
    runtime=runtime,
    auth=auth,
    outputs=outputs,
    replay_file=REPO / "recordings" / "replay.json",
    static_dir=REPO / "frontend" / "dist",
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
