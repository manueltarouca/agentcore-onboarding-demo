from users_lambda.index import on_event


class FakeCognito:
    def __init__(self):
        self.calls = []

    def admin_create_user(self, **kwargs):
        self.calls.append(("create", kwargs["Username"]))

    def admin_set_user_password(self, **kwargs):
        self.calls.append(("password", kwargs["Password"], kwargs["Permanent"]))

    def admin_add_user_to_group(self, **kwargs):
        self.calls.append(("group", kwargs["GroupName"]))


class FakeSecrets:
    def get_secret_value(self, SecretId):
        return {"SecretString": f"secret-of-{SecretId}"}


PROPS = {"UserPoolId": "pool", "Username": "rita.almeida", "Group": "relationship-managers", "PasswordSecret": "s1"}


def test_create_reads_the_password_from_secrets_manager_at_deploy_time():
    cognito = FakeCognito()

    result = on_event({"RequestType": "Create", "ResourceProperties": PROPS}, cognito=cognito, secrets=FakeSecrets())

    assert cognito.calls == [("create", "rita.almeida"), ("password", "secret-of-s1", True),
                             ("group", "relationship-managers")]
    assert result["PhysicalResourceId"] == "rita.almeida"


def test_delete_does_nothing_because_the_user_pool_is_deleted_with_the_stack():
    cognito = FakeCognito()

    on_event({"RequestType": "Delete", "PhysicalResourceId": "rita.almeida", "ResourceProperties": PROPS},
             cognito=cognito, secrets=FakeSecrets())

    assert cognito.calls == []


class ExistingUserCognito(FakeCognito):
    class exceptions:
        class UsernameExistsException(Exception):
            pass

    def admin_create_user(self, **kwargs):
        raise self.exceptions.UsernameExistsException()


def test_an_existing_user_still_gets_the_password_and_group():
    cognito = ExistingUserCognito()

    on_event({"RequestType": "Create", "ResourceProperties": PROPS}, cognito=cognito, secrets=FakeSecrets())

    assert cognito.calls == [("password", "secret-of-s1", True), ("group", "relationship-managers")]
