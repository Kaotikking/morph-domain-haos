"""MorphDomain locations and ten-domain ownership remain separate."""

from test_world_nine_core import aligned
from serein_gateway_test._vendor.morph_engine.domain_contract import (
    DOMAIN_ORDER, LOCATIONS, describe_domain, project_portable_cores,
)


def test_domain_has_kernel_plus_nine_and_locations_are_not_domains():
    contract = describe_domain()
    assert len(DOMAIN_ORDER) == 10
    assert contract["domains"][0] == "kernel"
    assert len(contract["portable_morph_cores"]) == 9
    assert contract["kernel"]["portable_morph_core"] is False
    assert set(LOCATIONS).isdisjoint(DOMAIN_ORDER)
    assert contract["boot_order"] == ["outpost", *DOMAIN_ORDER]
    assert contract["containment"]["state"] == "NOT_ADMITTED"
    assert contract["containment"]["default"] == "DENY"
    assert contract["containment"]["private_state_isolation_proven"] is False


def test_pulse_portable_projection_has_nine_cores_not_kernel():
    ledger = aligned("pulse", "HORIZON")
    core = ledger.data["morphs"]["pulse"]["snapshot"]["payload"]["morph_core"]
    projected = project_portable_cores(core)
    assert len(projected) == 9
    assert "kernel" not in projected
    assert projected["root"]["identity"]["morph_id"] == "pulse"
    assert projected["cloud"]["place"] == "HORIZON"
    projected["personality"]["mood"] = "changed-local-copy"
    assert core["personality"]["mood"] != "changed-local-copy"
