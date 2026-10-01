from onboarding_demo.domain.ownership import Holding, beneficial_owners, effective_ownership, people_only


def test_direct_shareholder_keeps_their_percentage():
    holdings = [Holding(owner="Ana", owned="Company", percent=40)]

    assert effective_ownership(holdings, company="Company") == {"Ana": 40}


def test_indirect_ownership_multiplies_along_the_chain():
    holdings = [
        Holding(owner="Holding Co", owned="Company", percent=50),
        Holding(owner="Miguel", owned="Holding Co", percent=60),
    ]

    assert effective_ownership(holdings, company="Company") == {"Miguel": 30}


def test_people_owning_through_several_paths_are_summed():
    holdings = [
        Holding(owner="Miguel", owned="Company", percent=10),
        Holding(owner="Holding Co", owned="Company", percent=50),
        Holding(owner="Miguel", owned="Holding Co", percent=40),
    ]

    assert effective_ownership(holdings, company="Company") == {"Miguel": 30}


def test_beneficial_owners_hold_more_than_25_percent():
    ownership = {"Ana": 40, "Miguel": 31.5, "Joao": 13.5, "Rui": 25}

    assert beneficial_owners(ownership) == ["Ana", "Miguel"]


def test_only_people_can_be_beneficial_owners_not_the_companies_in_between():
    holdings = [
        Holding(owner="Ana", owned="Company", percent=40),
        Holding(owner="Holding Co", owned="Company", percent=45),
        Holding(owner="Miguel", owned="Holding Co", percent=70),
    ]
    reported = {"Ana": 40, "Holding Co": 45, "Miguel": 31.5}  # a script that also lists companies

    assert people_only(reported, holdings) == {"Ana": 40, "Miguel": 31.5}
