"""The fictional onboarding cases used in the demo. No real people or companies.

Everything else (the agent, the bank's tools, the web app, the UI) reads its case from here,
so adding a case is adding an entry to CASES (plus a registry page in infra/registry_page/).
"""
from dataclasses import dataclass, field

from onboarding_demo.domain.ownership import Holding


@dataclass(frozen=True)
class OnboardingCase:
    case_id: str
    company: str
    company_number: str
    relationship_manager: str
    documents_received: tuple[str, ...]
    holdings: tuple[Holding, ...]
    client_username: str = ""  # the client's Cognito user, for the chat
    registry_page_url: str = ""
    conversation: tuple[tuple[str, str], ...] = field(default_factory=tuple)

    @property
    def registry_page(self) -> str:
        """The registry website page for this company (infra/registry_page/<number>.html)."""
        return f"{self.company_number}.html"


LUSITANIA = OnboardingCase(
    case_id="CASE-2026-0142",
    company="Lusitania Holdings SGPS",
    company_number="500000000",
    relationship_manager="Rita Almeida",
    client_username="lusitania.client",
    documents_received=("Commercial registry certificate", "Articles of association", "Proof of address"),
    holdings=(
        Holding(owner="Ana Costa", owned="Lusitania Holdings SGPS", percent=40),
        Holding(owner="Tejo Capital", owned="Lusitania Holdings SGPS", percent=45),
        Holding(owner="Other shareholders", owned="Lusitania Holdings SGPS", percent=15),
        Holding(owner="Miguel Santos", owned="Tejo Capital", percent=70),
        Holding(owner="Joao Pereira", owned="Tejo Capital", percent=30),
    ),
    conversation=(
        ("user", "New business customer: Lusitania Holdings SGPS, company number 500000000."),
        ("user", "They already sent the registry certificate, articles of association and proof of address."),
    ),
)

# Low risk: two people own it directly and neither is politically exposed or sanctioned,
# so Policy lets the agent approve it on its own. No human step.
DOURO = OnboardingCase(
    case_id="CASE-2026-0143",
    company="Douro Ceramics Lda",
    company_number="500000001",
    relationship_manager="Rita Almeida",
    client_username="douro.client",
    documents_received=("Commercial registry certificate", "Articles of association", "Beneficial owner declaration",
                        "Manager ID documents", "Proof of address"),
    holdings=(
        Holding(owner="Sofia Ribeiro", owned="Douro Ceramics Lda", percent=55),
        Holding(owner="Pedro Alves", owned="Douro Ceramics Lda", percent=45),
    ),
    conversation=(
        ("user", "New business customer: Douro Ceramics Lda, company number 500000001."),
        ("user", "They sent every document we asked for."),
    ),
)

CASES = {case.case_id: case for case in (LUSITANIA, DOURO)}
DEFAULT_CASE = LUSITANIA


def get_case(case_id: str | None) -> OnboardingCase:
    return CASES.get(case_id or "", DEFAULT_CASE)


def case_for_client(username: str) -> OnboardingCase:
    return next(case for case in CASES.values() if case.client_username == username)
