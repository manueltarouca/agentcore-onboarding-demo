"""Risk classification after screening the beneficial owners."""
from dataclasses import dataclass
from enum import StrEnum


class Risk(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class ScreeningResult:
    person: str
    pep: bool  # politically exposed person
    sanctioned: bool


def classify(results: list[ScreeningResult]) -> Risk:
    if any(r.sanctioned for r in results):
        return Risk.HIGH
    if any(r.pep for r in results):
        return Risk.MEDIUM
    return Risk.LOW
