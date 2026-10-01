from onboarding_demo import bank_tools
from onboarding_demo.case import CASES, case_for_client, get_case


def test_every_case_is_found_by_its_id_and_by_its_client_user():
    for case in CASES.values():
        assert get_case(case.case_id) is case
        assert case_for_client(case.client_username) is case


def test_the_bank_systems_know_every_company_in_the_catalogue():
    for case in CASES.values():
        assert bank_tools.registry_lookup(case.company_number)["name"] == case.company
        assert bank_tools.case_status(case.case_id)["company"] == case.company


def test_a_client_with_all_documents_has_nothing_left_to_send():
    assert bank_tools.case_status("CASE-2026-0143")["documents_needed"] == []
