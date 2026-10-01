from onboarding_demo.adapters.aws.naming import memory_actor_id


def test_usernames_become_valid_memory_actor_ids():
    assert memory_actor_id("rita.almeida") == "rita-almeida"
    assert memory_actor_id("compliance.officer") == "compliance-officer"
