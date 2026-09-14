"""Installed-style logical routing keeps HAOS's Store as sole Morph authority."""

import pytest

import test_haos_morph_habitat  # installs the local Home Assistant package shim
from serein_gateway_test._vendor.morph_engine.domain_contract import DOMAIN_ORDER
from serein_gateway_test._vendor.morph_engine.domain_runtime import API_VERSION, DomainDenied
from serein_gateway_test._vendor.morph_engine.haos_runtime import build_haos_runtime


def test_haos_router_boots_in_order_only_after_store_load():
    ledger = test_haos_morph_habitat.transfer.MorphTransferLedger.empty()
    with pytest.raises(DomainDenied, match="PREFLIGHT_FAILED"):
        build_haos_runtime(store_loaded=False, ledger_data=ledger.data)
    with pytest.raises(DomainDenied, match="PREFLIGHT_FAILED"):
        build_haos_runtime(store_loaded=True, ledger_data={})
    runtime = build_haos_runtime(store_loaded=True, ledger_data=ledger.data)
    assert runtime.admitted == DOMAIN_ORDER


def test_only_kernel_can_request_a_bounded_core_review():
    ledger = test_haos_morph_habitat.transfer.MorphTransferLedger.empty()
    runtime = build_haos_runtime(store_loaded=True, ledger_data=ledger.data)
    request = {"schema": API_VERSION, "request_id": "evt-1:memory",
               "event_ticket": "evt-1", "required": True,
               "before": {"value": 1}, "after": {"value": 2}}
    with pytest.raises(DomainDenied, match="ROUTE_DENIED"):
        runtime.call(caller="ui", owner="memory", action="event.review.v1", request=request)
    with pytest.raises(DomainDenied, match="ROUTE_DENIED"):
        runtime.call(caller="kernel", owner="memory", action="private.read", request=request)
    receipt = runtime.call(caller="kernel", owner="memory", action="event.review.v1", request=request)
    assert receipt["core"] == "memory" and receipt["disposition"] == "ADMITTED"
    assert "before" not in receipt and "after" not in receipt


def test_required_core_cannot_be_silent():
    runtime = build_haos_runtime(store_loaded=True,
                                 ledger_data=test_haos_morph_habitat.transfer.MorphTransferLedger.empty().data)
    with pytest.raises(DomainDenied, match="REQUIRED_CORE_SILENT"):
        runtime.call(caller="kernel", owner="memory", action="event.review.v1",
                     request={"schema": API_VERSION, "request_id": "evt-2:memory",
                              "event_ticket": "evt-2", "required": True,
                              "before": {}, "after": {}})
