"""Local logical containment proof, not hostile same-process isolation."""

import pytest
import test_haos_morph_habitat  # local Home Assistant package shim

from serein_gateway_test._vendor.morph_engine.domain_contract import DOMAIN_ORDER
from serein_gateway_test._vendor.morph_engine.domain_runtime import (
    API_VERSION, DomainDenied, MorphDomainRuntime, Route,
)


def booted():
    runtime = MorphDomainRuntime()
    runtime.preflight(host_ready=True, local_state_valid=True)
    for branch in ("authority", "operations", "interface"):
        runtime.boot_kernel_branch(branch, healthy=True)
    for domain in DOMAIN_ORDER[1:]:
        runtime.admit(domain, identity_valid=True, policy_loaded=True,
                      api_registered=True, healthy=True)
    return runtime


def test_boot_requires_preflight_kernel_branches_and_exact_nine_core_order():
    runtime = MorphDomainRuntime()
    with pytest.raises(DomainDenied, match="BOOT_ORDER_DENIED"):
        runtime.admit("platform", identity_valid=True, policy_loaded=True,
                      api_registered=True, healthy=True)
    with pytest.raises(DomainDenied, match="PREFLIGHT_FAILED"):
        runtime.preflight(host_ready=False, local_state_valid=True)
    runtime.preflight(host_ready=True, local_state_valid=True)
    with pytest.raises(DomainDenied, match="BOOT_ORDER_DENIED"):
        runtime.boot_kernel_branch("interface", healthy=True)
    for branch in ("authority", "operations", "interface"):
        runtime.boot_kernel_branch(branch, healthy=True)
    with pytest.raises(DomainDenied, match="BOOT_ORDER_DENIED"):
        runtime.admit("memory", identity_valid=True, policy_loaded=True,
                      api_registered=True, healthy=True)
    with pytest.raises(DomainDenied, match="DOMAIN_NOT_READY"):
        runtime.admit("platform", identity_valid=True, policy_loaded=False,
                      api_registered=True, healthy=True)
    for domain in DOMAIN_ORDER[1:]:
        runtime.admit(domain, identity_valid=True, policy_loaded=True,
                      api_registered=True, healthy=True)
    assert runtime.admitted == DOMAIN_ORDER


def test_registered_api_allows_bounded_call_and_denies_wrong_caller_replay_and_withdrawal():
    runtime = booted()
    private = {"visits": 0}

    def visit(request):
        private["visits"] += 1
        return {"visits": private["visits"], "morph_id": request["morph_id"]}

    runtime.register(Route("knowledge", "record_world_visit", frozenset({"personality"}), visit, True))
    request = {"schema": API_VERSION, "request_id": "visit-1", "morph_id": "pulse"}
    assert runtime.call(caller="personality", owner="knowledge",
                        action="record_world_visit", request=request) == {"visits": 1, "morph_id": "pulse"}
    for caller, action, code in (("ui", "record_world_visit", "ROUTE_DENIED"),
                                 ("personality", "private_state", "ROUTE_DENIED"),
                                 ("personality", "record_world_visit", "REPLAY_DENIED")):
        with pytest.raises(DomainDenied, match=code):
            runtime.call(caller=caller, owner="knowledge", action=action, request=request)
    assert private["visits"] == 1
    runtime.withdraw("knowledge")
    with pytest.raises(DomainDenied, match="DOMAIN_UNAVAILABLE"):
        runtime.call(caller="personality", owner="knowledge", action="record_world_visit",
                     request={**request, "request_id": "visit-2"})
    assert runtime.admitted[-1] == "cloud"  # unrelated domain remains available
