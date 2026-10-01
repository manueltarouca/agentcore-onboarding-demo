"""Custom resource: create a demo Cognito user with a password kept in Secrets Manager.

The password is read here, at deploy time, so it never appears in the CloudFormation
template. (CloudFormation does not resolve Secrets Manager references inside custom
resource properties.)
"""


def on_event(event, context=None, cognito=None, secrets=None):
    props = event["ResourceProperties"]
    if event["RequestType"] != "Create":
        return {"PhysicalResourceId": event.get("PhysicalResourceId", props["Username"])}
    if cognito is None or secrets is None:
        import boto3  # provided by the Lambda runtime

        cognito, secrets = boto3.client("cognito-idp"), boto3.client("secretsmanager")
    password = secrets.get_secret_value(SecretId=props["PasswordSecret"])["SecretString"]
    pool, username = props["UserPoolId"], props["Username"]
    try:
        cognito.admin_create_user(UserPoolId=pool, Username=username, MessageAction="SUPPRESS")
    except cognito.exceptions.UsernameExistsException:
        pass  # created by an earlier deploy: still make sure password and group are right
    cognito.admin_set_user_password(UserPoolId=pool, Username=username, Password=password, Permanent=True)
    cognito.admin_add_user_to_group(UserPoolId=pool, Username=username, GroupName=props["Group"])
    return {"PhysicalResourceId": username}
