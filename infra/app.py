"""CDK entry point:  cd infra && cdk deploy --outputs-file outputs.json"""
import os

import aws_cdk as cdk

from stack import OnboardingStack

app = cdk.App()
OnboardingStack(
    app, "OnboardingAgentDemo",
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=os.environ.get("CDK_DEFAULT_REGION", "us-west-2")),
)
app.synth()
