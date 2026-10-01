"""Documents the bank needs before opening a business account."""

REQUIRED_DOCUMENTS = (
    "Commercial registry certificate",
    "Articles of association",
    "Beneficial owner declaration",
    "Manager ID documents",
    "Proof of address",
)


def missing_documents(received: list[str]) -> list[str]:
    return [doc for doc in REQUIRED_DOCUMENTS if doc not in received]
