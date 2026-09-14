"""Event-scoped logical Core routing over HAOS's single Morph Store.

This is in-process policy separation, not process or filesystem isolation.
It never creates another life ledger or writes a second database.
"""

from __future__ import annotations

from typing import Any

from .domain_contract import DOMAIN_ORDER
from .domain_runtime import API_VERSION, DomainDenied, MorphDomainRuntime, Route
from ..morph_sdk.transfer import sha256_json


def build_haos_runtime(*, store_loaded: bool, ledger_data: dict[str, Any]) -> MorphDomainRuntime:
    """Boot the logical router only after HAOS has loaded its private Store."""
    runtime = MorphDomainRuntime()
    valid = (isinstance(ledger_data, dict) and isinstance(ledger_data.get("morphs"), dict)
             and isinstance(ledger_data.get("operations"), dict))
    runtime.preflight(host_ready=store_loaded, local_state_valid=valid)
    for branch in ("authority", "operations", "interface"):
        runtime.boot_kernel_branch(branch, healthy=True)
    for owner in DOMAIN_ORDER[1:]:
        runtime.register(Route(owner, "event.review.v1", frozenset({"kernel"}),
                               lambda request, name=owner: _review_owned(name, request)))
        runtime.admit(owner, identity_valid=True, policy_loaded=True,
                      api_registered=True, healthy=True)
    return runtime


def _review_owned(owner: str, request: dict[str, Any]) -> dict[str, Any]:
    """Review only the addressed Core's before/after slice."""
    before = request.get("before")
    after = request.get("after")
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise DomainDenied("CORE_SLICE_REQUIRED")
    changed = before != after
    if request.get("required") is True and not changed:
        raise DomainDenied("REQUIRED_CORE_SILENT")
    return {"core": owner, "required": request.get("required") is True,
            "disposition": "ADMITTED" if changed else "PROCESSED_NO_CHANGE",
            "before_sha256": sha256_json(before), "after_sha256": sha256_json(after)}


def review_event(runtime: MorphDomainRuntime, *, ticket: str,
                 before: dict[str, Any], after: dict[str, Any],
                 required: frozenset[str], reject_core: str | None = None) -> list[dict[str, Any]]:
    """Route nine bounded Core reviews under one event ticket."""
    receipts = []
    for owner in DOMAIN_ORDER[1:]:
        if owner == reject_core:
            raise DomainDenied("CORE_REJECTED")
        receipts.append(runtime.call(caller="kernel", owner=owner,
            action="event.review.v1", request={"schema": API_VERSION,
                "request_id": f"{ticket}:{owner}", "event_ticket": ticket,
                "required": owner in required, "before": before[owner],
                "after": after[owner]}))
    return receipts
