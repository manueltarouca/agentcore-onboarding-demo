"""Everything the onboarding agent needs in AWS, in one stack.

    Cognito            who the users are (relationship manager, compliance officer)
    Lambda             the bank's own systems, exposed as tools
    Gateway + Policy   turns the Lambda into MCP tools and decides who may call what
    Memory             short and long-term memory for the agent
    Runtime            hosts the agent (built from backend/Dockerfile)
    S3 + CloudFront    a public "registry" web page the agent reads with Browser
"""
from pathlib import Path

from aws_cdk import (
    CfnOutput, CustomResource, Duration, RemovalPolicy, Stack,
    aws_bedrockagentcore as agentcore,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_cognito as cognito,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_s3 as s3,
    aws_s3_deployment as s3_deployment,
    aws_secretsmanager as secretsmanager,
    custom_resources as cr,
)
from constructs import Construct

ROOT = Path(__file__).resolve().parent.parent
PREFIX = "onboarding"
MODEL_ID = "global.anthropic.claude-sonnet-4-6"
EVALUATORS = "Builtin.GoalSuccessRate,Builtin.Helpfulness"
USERS = {
    "rita.almeida": "relationship-managers",
    "compliance.officer": "compliance",
}


class OnboardingStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---- Identity: Cognito users and groups ------------------------------------------
        user_pool = cognito.UserPool(
            self, "Users", user_pool_name=f"{PREFIX}-users", self_sign_up_enabled=False,
            removal_policy=RemovalPolicy.DESTROY,
        )
        client = user_pool.add_client(
            "WebClient", user_pool_client_name=f"{PREFIX}-web",
            auth_flows=cognito.AuthFlow(user_password=True), generate_secret=False,
        )
        self._users_provider = self._users_custom_resource(user_pool)
        passwords = {}
        for username, group in USERS.items():
            passwords[username] = self._demo_user(user_pool, username, group)

        # ---- The bank's systems (outside AgentCore), as a Lambda ------------------------
        tools_function = lambda_.Function(
            self, "BankTools", function_name=f"{PREFIX}-bank-tools",
            runtime=lambda_.Runtime.PYTHON_3_12, architecture=lambda_.Architecture.ARM_64,
            handler="onboarding_demo.tools_lambda.handler",
            code=lambda_.Code.from_asset(str(ROOT / "backend" / "src"), exclude=["**/__pycache__"]),
            timeout=Duration.seconds(15),
        )

        # ---- Gateway with Policy ---------------------------------------------------------
        policy_engine = agentcore.PolicyEngine(self, "PolicyEngine", policy_engine_name=f"{PREFIX}_policies")
        gateway = agentcore.Gateway(
            self, "Gateway", gateway_name=f"{PREFIX}-gateway",
            authorizer_configuration=agentcore.GatewayAuthorizer.using_cognito(
                user_pool=user_pool, allowed_clients=[client]),
            policy_engine_configuration=agentcore.GatewayPolicyEngineConfig(
                policy_engine=policy_engine, mode=agentcore.PolicyEngineMode.ENFORCE),
            exception_level=agentcore.GatewayExceptionLevel.DEBUG,
        )
        gateway.add_lambda_target(
            "BankTarget", gateway_target_name="bank", lambda_function=tools_function,
            tool_schema=agentcore.ToolSchema.from_local_asset(str(ROOT / "infra" / "tool_schema.json")),
        )
        for name, cedar in self._policies(gateway.gateway_arn).items():
            agentcore.Policy(self, f"Policy{name}", policy_engine=policy_engine, policy_name=f"{PREFIX}_{name}",
                             statement=agentcore.PolicyStatement.from_cedar(cedar))

        # ---- Memory ------------------------------------------------------------------------
        memory = agentcore.Memory(
            self, "Memory", memory_name=f"{PREFIX}_memory", expiration_duration=Duration.days(30),
            memory_strategies=[
                agentcore.MemoryStrategy.using_user_preference(
                    strategy_name="preferences", namespaces=["/onboarding/{actorId}/preferences/"]),
                agentcore.MemoryStrategy.using_semantic(
                    strategy_name="facts", namespaces=["/onboarding/{actorId}/facts/"]),
                agentcore.MemoryStrategy.using_episodic(
                    strategy_name="episodes", namespaces=["/onboarding/{actorId}/episodes/"],
                    # Reflections generalise across episodes; their namespace must be a parent of the episodes'.
                    reflection_configuration=agentcore.EpisodicReflectionConfiguration(
                        namespaces=["/onboarding/{actorId}/"])),
            ],
        )

        # ---- Third-party registry website (read by Browser) ------------------------------
        site_bucket = s3.Bucket(self, "RegistrySite", removal_policy=RemovalPolicy.DESTROY, auto_delete_objects=True)
        distribution = cloudfront.Distribution(
            self, "RegistrySiteCdn", default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(site_bucket)),
        )
        s3_deployment.BucketDeployment(
            self, "RegistrySiteFiles", destination_bucket=site_bucket, distribution=distribution,
            sources=[s3_deployment.Source.asset(str(ROOT / "infra" / "registry_page"))],
        )

        # ---- Runtime: the agent ------------------------------------------------------------
        runtime_name = f"{PREFIX}_agent"
        runtime = agentcore.Runtime(
            self, "Agent", runtime_name=runtime_name,
            agent_runtime_artifact=agentcore.AgentRuntimeArtifact.from_asset(str(ROOT / "backend")),
            authorizer_configuration=agentcore.RuntimeAuthorizerConfiguration.using_cognito(user_pool, [client]),
            request_header_configuration=agentcore.RequestHeaderConfiguration(allowlisted_headers=["Authorization"]),
            environment_variables={
                "GATEWAY_URL": f"{gateway.gateway_url}",
                "GATEWAY_TARGET": "bank",
                "MEMORY_ID": memory.memory_id,
                "MODEL_ID": MODEL_ID,
                "RUNTIME_NAME": runtime_name,
                "EVALUATOR_IDS": EVALUATORS,
                "REGISTRY_PAGE_URL": f"https://{distribution.distribution_domain_name}/",
                "AWS_REGION": self.region,
            },
            tracing_enabled=True,
        )
        self._grant_agent_permissions(runtime.role, memory)

        # ---- Outputs used by the web app and the console links -------------------------
        outputs = {
            "Region": self.region,
            "UserPoolId": user_pool.user_pool_id,
            "UserPoolClientId": client.user_pool_client_id,
            "RuntimeArn": runtime.agent_runtime_arn,
            "RuntimeId": runtime.agent_runtime_id,
            "GatewayId": gateway.gateway_id,
            "GatewayUrl": gateway.gateway_url,
            "PolicyEngineId": policy_engine.policy_engine_id,
            "MemoryId": memory.memory_id,
            "ToolsFunctionName": tools_function.function_name,
            "RegistryPageUrl": f"https://{distribution.distribution_domain_name}/",
        }
        for username, secret in passwords.items():
            outputs[f"PasswordSecret{username.split('.')[0].title()}"] = secret.secret_name
        for key, value in outputs.items():
            CfnOutput(self, key, value=value)

    def _demo_user(self, user_pool: cognito.UserPool, username: str, group: str) -> secretsmanager.Secret:
        """A Cognito user with a generated password kept in Secrets Manager."""
        key = username.replace(".", "-")
        secret = secretsmanager.Secret(
            self, f"Password-{key}", secret_name=f"{PREFIX}/{username}",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                password_length=20, require_each_included_type=True,  # Cognito wants a symbol too
                exclude_characters="\"'\\/@` "),
            removal_policy=RemovalPolicy.DESTROY,
        )
        group_resource = cognito.CfnUserPoolGroup(self, f"Group-{key}", user_pool_id=user_pool.user_pool_id,
                                                  group_name=group)
        secret.grant_read(self._users_provider.on_event_handler)
        user = CustomResource(self, f"User-{key}", service_token=self._users_provider.service_token, properties={
            "UserPoolId": user_pool.user_pool_id, "Username": username, "Group": group,
            "PasswordSecret": secret.secret_name,
        })
        user.node.add_dependency(group_resource)
        user.node.add_dependency(secret)
        return secret

    def _users_custom_resource(self, user_pool: cognito.UserPool) -> cr.Provider:
        handler = lambda_.Function(
            self, "DemoUsersHandler", runtime=lambda_.Runtime.PYTHON_3_12, architecture=lambda_.Architecture.ARM_64,
            handler="index.on_event", code=lambda_.Code.from_asset(str(ROOT / "infra" / "users_lambda")),
            timeout=Duration.seconds(30),
        )
        handler.add_to_role_policy(iam.PolicyStatement(
            actions=["cognito-idp:AdminCreateUser", "cognito-idp:AdminSetUserPassword", "cognito-idp:AdminAddUserToGroup"],
            resources=[user_pool.user_pool_arn]))
        return cr.Provider(self, "DemoUsersProvider", on_event_handler=handler)

    @staticmethod
    def _policies(gateway_arn: str) -> dict[str, str]:
        """Cedar policies. Everything not permitted here is denied by default."""
        gateway = f'AgentCore::Gateway::"{gateway_arn}"'
        return {
            "everyday_tools": f"""permit(
  principal is AgentCore::OAuthUser,
  action in [AgentCore::Action::"bank___registry_lookup",
             AgentCore::Action::"bank___screen_person",
             AgentCore::Action::"bank___create_compliance_case"],
  resource == {gateway}
);""",
            "approve_low_risk": f"""permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"bank___approve_customer",
  resource == {gateway}
) when {{ context.input.risk == "low" }};""",
            "approve_by_compliance": f"""permit(
  principal is AgentCore::OAuthUser,
  action == AgentCore::Action::"bank___approve_customer",
  resource == {gateway}
) when {{ principal.hasTag("username") && principal.getTag("username") == "compliance.officer" }};""",
        }

    def _grant_agent_permissions(self, role: iam.IRole, memory: agentcore.Memory) -> None:
        statements = {
            "Model": (["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"], ["*"]),
            "Memory": (["bedrock-agentcore:CreateEvent", "bedrock-agentcore:ListEvents",
                        "bedrock-agentcore:RetrieveMemoryRecords"], [memory.memory_arn]),
            "CodeInterpreter": (["bedrock-agentcore:StartCodeInterpreterSession",
                                 "bedrock-agentcore:InvokeCodeInterpreter",
                                 "bedrock-agentcore:StopCodeInterpreterSession"], ["*"]),
            "Browser": (["bedrock-agentcore:StartBrowserSession", "bedrock-agentcore:ConnectBrowserAutomationStream",
                         "bedrock-agentcore:StopBrowserSession", "bedrock-agentcore:GetBrowserSession"], ["*"]),
            "Evaluations": (["bedrock-agentcore:Evaluate", "bedrock-agentcore:ListAgentRuntimes",
                             "logs:StartQuery", "logs:GetQueryResults", "logs:DescribeLogGroups"], ["*"]),
            "Registry": (["bedrock-agentcore:CreateRegistry", "bedrock-agentcore:ListRegistries",
                          "bedrock-agentcore:CreateRegistryRecord"], ["*"]),
        }
        for sid, (actions, resources) in statements.items():
            role.add_to_principal_policy(iam.PolicyStatement(sid=sid, actions=actions, resources=resources))
