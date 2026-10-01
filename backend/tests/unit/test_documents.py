from onboarding_demo.domain.documents import REQUIRED_DOCUMENTS, missing_documents


def test_lists_the_required_documents_not_yet_received():
    received = ["Commercial registry certificate", "Articles of association", "Proof of address"]

    assert missing_documents(received) == ["Beneficial owner declaration", "Manager ID documents"]


def test_nothing_is_missing_when_everything_was_received():
    assert missing_documents(list(REQUIRED_DOCUMENTS)) == []
