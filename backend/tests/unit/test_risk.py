from onboarding_demo.domain.risk import Risk, ScreeningResult, classify


def test_clean_screening_is_low_risk():
    assert classify([ScreeningResult("Ana", pep=False, sanctioned=False)]) == Risk.LOW


def test_a_politically_exposed_person_makes_it_medium_risk():
    results = [
        ScreeningResult("Ana", pep=False, sanctioned=False),
        ScreeningResult("Miguel", pep=True, sanctioned=False),
    ]

    assert classify(results) == Risk.MEDIUM


def test_a_sanctioned_person_makes_it_high_risk():
    results = [ScreeningResult("Miguel", pep=True, sanctioned=True)]

    assert classify(results) == Risk.HIGH
