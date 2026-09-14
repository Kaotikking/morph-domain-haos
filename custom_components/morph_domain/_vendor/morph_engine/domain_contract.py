"""MorphDomain ten-domain boundary over a portable nine-core Morph.

This is a local contract, not an admission claim for Serein's ten services.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from .core_contract import CORE_ORDER

DOMAIN_ORDER = ("kernel", *CORE_ORDER)
BOOT_ORDER = ("outpost", *DOMAIN_ORDER)
LOCATIONS = ("VOID", "NURSERY", "HORIZON", "SEREIN_GARDENS", "CODE_HAVEN")
KERNEL_OWNS = ("authority", "time", "location-law", "transfer-policy", "write-boundary")
CORE_OWNERSHIP = {
    "platform": ("runtime", "embodiment"),
    "root": ("identity", "lineage"),
    "memory": ("life", "chronicle"),
    "knowledge": ("environment", "learned-preferences"),
    "ui": ("expression", "visual-presentation"),
    "audio": ("elemental-voice", "audio-memory"),
    "personality": ("mood", "traits", "social-disposition"),
    "modular": ("capabilities", "extensions"),
    "cloud": ("place", "custody", "reconciliation"),
}


def describe_domain() -> dict[str, Any]:
    """Describe ownership without inventing a tenth portable Morph core."""
    return {
        "schema": "serein.morph-domain-ten-domains.local.v1",
        "domains": list(DOMAIN_ORDER),
        "boot_order": list(BOOT_ORDER),
        "kernel": {"scope": "MorphDomain", "owns": list(KERNEL_OWNS),
                   "portable_morph_core": False},
        "containment": {"state": "NOT_ADMITTED", "cross_domain": "VERSIONED_API_ONLY",
                        "default": "DENY", "private_state_isolation_proven": False,
                        "api_registry_proven": False},
        "portable_morph_cores": list(CORE_ORDER),
        "locations": list(LOCATIONS),
        "ownership": {key: list(value) for key, value in CORE_OWNERSHIP.items()},
    }


def project_portable_cores(core: dict[str, Any]) -> dict[str, Any]:
    """Local fixture projection only; not a cross-domain runtime API."""
    from ..morph_sdk.morph_core import validate_nine_core

    source = validate_nine_core(core)
    return {name: deepcopy(source[name]) for name in CORE_ORDER}
