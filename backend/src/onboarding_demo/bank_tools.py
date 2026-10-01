"""Fictional bank systems exposed to the agent as Gateway tools.

The same functions run inside the Lambda behind AgentCore Gateway (see infra/) and in
the fake gateway used by tests, so both behave the same way.
"""
from onboarding_demo.case import CASES
from onboarding_demo.domain.documents import missing_documents
from onboarding_demo.domain.ownership import beneficial_owners, effective_ownership, people_only
from onboarding_demo.domain.risk import ScreeningResult, classify

REGISTRY_DETAILS = {
    "500000000": {"legal_form": "SGPS (holding company)", "registered_office": "Lisbon", "status": "Active",
                  "incorporated": "2011-03-14"},
    "500000001": {"legal_form": "Lda (private limited company)", "registered_office": "Porto", "status": "Active",
                  "incorporated": "2016-09-02"},
}

COMPANIES = {
    case.company_number: {
        "name": case.company, **REGISTRY_DETAILS.get(case.company_number, {})
    }
    for case in CASES.values()
}

PEP_LIST = {"Miguel Santos": "Former member of a municipal executive"}
SANCTIONS_LIST: set[str] = set()


def registry_lookup(company_number: str) -> dict:
    company = COMPANIES.get(company_number)
    if company is None:
        return {"found": False, "company_number": company_number}
    return {"found": True, "company_number": company_number, **company}


def screen_person(name: str) -> dict:
    return {
        "person": name,
        "pep": name in PEP_LIST,
        "pep_reason": PEP_LIST.get(name, ""),
        "sanctioned": name in SANCTIONS_LIST,
    }


def create_compliance_case(case_id: str, reason: str) -> dict:
    return {"case_id": case_id, "queue": "Compliance review", "reason": reason, "status": "Open"}


def approve_customer(case_id: str, risk: str) -> dict:
    return {"case_id": case_id, "risk": risk, "status": "Approved"}


# What the client may see about their own case. Status and requests only: never the
# screening results or the risk (telling a customer they are under suspicion is "tipping off").
CLIENT_CASES = {
    case.case_id: {
        "company": case.company,
        "stage": "Under review",
        "documents_needed": missing_documents(list(case.documents_received)),
        "relationship_manager": case.relationship_manager,
    }
    for case in CASES.values()
}


def case_status(case_id: str) -> dict:
    case = CLIENT_CASES.get(case_id)
    return {"case_id": case_id, **case} if case else {"case_id": case_id, "found": False}


def book_callback(case_id: str, topic: str) -> dict:
    manager = CLIENT_CASES.get(case_id, {}).get("relationship_manager", "your relationship manager")
    return {"reference": f"CB-{abs(hash((case_id, topic))) % 10000:04d}", "with": manager,
            "topic": topic, "when": "Next business day, 10:00"}


def assessed_risk(case_id: str) -> str:
    """The bank's own risk assessment of a case, from its records. Internal: not a tool, never shown
    to the client. The chat uses it so the risk sent to Policy is never the model's guess."""
    case = CASES[case_id]
    holdings = list(case.holdings)
    owners = beneficial_owners(people_only(effective_ownership(holdings, case.company), holdings))
    return str(classify([ScreeningResult(p, pep=p in PEP_LIST, sanctioned=p in SANCTIONS_LIST) for p in owners]))


TOOLS = {
    "registry_lookup": registry_lookup,
    "screen_person": screen_person,
    "create_compliance_case": create_compliance_case,
    "approve_customer": approve_customer,
    "case_status": case_status,
    "book_callback": book_callback,
}
