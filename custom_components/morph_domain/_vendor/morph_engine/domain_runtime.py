"""Local ten-domain boot and API-only coordination proof.

Logical containment only: Python code in one HAOS process is not a security
principal. The HAOS event-review adapter uses this router over the existing
private Morph Store; it does not own a second Morph database.
"""

from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable

from .domain_contract import DOMAIN_ORDER

API_VERSION = "serein.morph-domain-api.v1"
KERNEL_BRANCHES = ("authority", "operations", "interface")


class DomainDenied(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Route:
    owner: str
    action: str
    callers: frozenset[str]
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    mutation: bool = False


class MorphDomainRuntime:
    """Fail-closed in-process coordinator with one admitted owner per API."""

    def __init__(self) -> None:
        self._admitted: list[str] = []
        self._routes: dict[tuple[str, str], Route] = {}
        self._kernel_branches: list[str] = []
        self._preflight = False
        self._audit: list[dict[str, Any]] = []
        self._receipt_sink: Callable[[str, str, str, str], None] | None = None

    def bind_receipt_sink(self, sink: Callable[[str, str, str, str], None]) -> None:
        self._receipt_sink = sink

    @property
    def admitted(self) -> tuple[str, ...]:
        return tuple(self._admitted)

    def preflight(self, *, host_ready: bool, local_state_valid: bool) -> None:
        if not host_ready or not local_state_valid:
            raise DomainDenied("PREFLIGHT_FAILED")
        self._preflight = True

    def boot_kernel_branch(self, branch: str, *, healthy: bool) -> None:
        if not self._preflight or not healthy:
            raise DomainDenied("KERNEL_NOT_READY")
        if len(self._kernel_branches) >= len(KERNEL_BRANCHES) or branch != KERNEL_BRANCHES[len(self._kernel_branches)]:
            raise DomainDenied("BOOT_ORDER_DENIED")
        self._kernel_branches.append(branch)
        if len(self._kernel_branches) == len(KERNEL_BRANCHES):
            self._admitted.append("kernel")

    def admit(self, domain: str, *, identity_valid: bool, policy_loaded: bool,
              api_registered: bool, healthy: bool) -> None:
        if len(self._admitted) >= len(DOMAIN_ORDER) or domain != DOMAIN_ORDER[len(self._admitted)]:
            raise DomainDenied("BOOT_ORDER_DENIED")
        if not all((identity_valid, policy_loaded, api_registered, healthy)):
            raise DomainDenied("DOMAIN_NOT_READY")
        self._admitted.append(domain)

    def register(self, route: Route) -> None:
        if route.owner not in DOMAIN_ORDER or route.owner == "kernel":
            raise DomainDenied("INVALID_OWNER")
        if not route.action or not route.callers or not route.callers.issubset(set(DOMAIN_ORDER)):
            raise DomainDenied("INVALID_ROUTE")
        key = (route.owner, route.action)
        if key in self._routes:
            raise DomainDenied("DUPLICATE_ROUTE")
        self._routes[key] = route

    def call(self, *, caller: str, owner: str, action: str,
             request: dict[str, Any]) -> dict[str, Any]:
        """All cross-domain calls enter Kernel's exact versioned road."""
        if not isinstance(request, dict) or request.get("schema") != API_VERSION:
            raise DomainDenied("SCHEMA_DENIED")
        route = self._routes.get((owner, action))
        if route is None or caller not in route.callers:
            raise DomainDenied("ROUTE_DENIED")
        if "kernel" not in self._admitted or caller not in self._admitted or owner not in self._admitted:
            raise DomainDenied("DOMAIN_UNAVAILABLE")
        if not isinstance(request.get("request_id"), str) or not request["request_id"]:
            raise DomainDenied("REQUEST_ID_REQUIRED")
        if route.mutation and any(row["request_id"] == request["request_id"] for row in self._audit):
            raise DomainDenied("REPLAY_DENIED")
        response = route.handler(deepcopy(request))
        if not isinstance(response, dict):
            raise DomainDenied("INVALID_RESPONSE")
        ticket = request.get("event_ticket")
        if self._receipt_sink is not None:
            if not isinstance(ticket, str):
                raise DomainDenied("EVENT_TICKET_REQUIRED")
            disposition = response.get("_domain_disposition")
            if disposition not in {"PROCESSED_NO_CHANGE", "ADMITTED", "REJECTED", "DEFERRED", "NOT_APPLICABLE"}:
                raise DomainDenied("DOMAIN_DISPOSITION_REQUIRED")
            self._receipt_sink(ticket, owner, request["request_id"],
                               disposition)
        self._audit.append({"request_id": request["request_id"], "caller": caller,
                            "owner": owner, "action": action, "mutation": route.mutation,
                            "event_ticket": ticket})
        return deepcopy(response)

    def withdraw(self, domain: str) -> None:
        if domain not in self._admitted or domain == "kernel":
            raise DomainDenied("DOMAIN_UNAVAILABLE")
        self._admitted.remove(domain)

    def audit(self) -> list[dict[str, Any]]:
        return deepcopy(self._audit)

    @contextmanager
    def atomic_audit(self):
        """Roll back uncommitted local route receipts with owner storage."""
        start = len(self._audit)
        try:
            yield
        except BaseException:
            del self._audit[start:]
            raise
