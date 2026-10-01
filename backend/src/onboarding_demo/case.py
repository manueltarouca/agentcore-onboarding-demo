"""The fictional onboarding case used in the demo. No real people or companies."""
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
    registry_page_url: str = ""
    conversation: tuple[tuple[str, str], ...] = field(default_factory=tuple)


LUSITANIA = OnboardingCase(
    case_id="CASE-2026-0142",
    company="Lusitania Holdings SGPS",
    company_number="500000000",
    relationship_manager="Rita Almeida",
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
