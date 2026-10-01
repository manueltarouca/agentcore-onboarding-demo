"""Fictional bank systems exposed to the agent as Gateway tools.

The same functions run inside the Lambda behind AgentCore Gateway (see infra/) and in
the fake gateway used by tests, so both behave the same way.
"""
COMPANIES = {
    "500000000": {
        "name": "Lusitania Holdings SGPS",
        "legal_form": "SGPS (holding company)",
        "registered_office": "Lisbon",
        "status": "Active",
        "incorporated": "2011-03-14",
    }
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


TOOLS = {
    "registry_lookup": registry_lookup,
    "screen_person": screen_person,
    "create_compliance_case": create_compliance_case,
    "approve_customer": approve_customer,
}
