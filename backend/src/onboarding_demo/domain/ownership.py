"""Who really owns a company, directly or through other companies.

This is the calculation the agent asks Code Interpreter to run. We keep a tested
version here so the demo can check the sandbox result against a known answer.
"""
from dataclasses import dataclass

BENEFICIAL_OWNER_THRESHOLD = 25  # percent; the owner must hold MORE than this


@dataclass(frozen=True)
class Holding:
    owner: str
    owned: str
    percent: float


def effective_ownership(holdings: list[Holding], company: str) -> dict[str, float]:
    """Return each person's total share of `company`, following every ownership chain.

    A "person" is any owner that does not itself have owners in `holdings`.
    """
    owners_of: dict[str, list[Holding]] = {}
    for holding in holdings:
        owners_of.setdefault(holding.owned, []).append(holding)

    totals: dict[str, float] = {}

    def walk(entity: str, share: float) -> None:
        for holding in owners_of.get(entity, []):
            part = share * holding.percent / 100
            if holding.owner in owners_of:
                walk(holding.owner, part)
            else:
                totals[holding.owner] = round(totals.get(holding.owner, 0) + part, 4)

    walk(company, 100)
    return totals


def beneficial_owners(ownership: dict[str, float]) -> list[str]:
    return [person for person, percent in ownership.items() if percent > BENEFICIAL_OWNER_THRESHOLD]


def people_only(ownership: dict[str, float], holdings: list[Holding]) -> dict[str, float]:
    """Drop companies from an ownership result. A company is anything that is itself owned."""
    companies = {h.owned for h in holdings}
    return {owner: percent for owner, percent in ownership.items() if owner not in companies}
