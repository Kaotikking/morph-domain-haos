"""Bounded UMP decisions for ordinary Morph life and social admission.

This module only adjudicates evidence. It never grants authority, changes custody,
advances DNA, or creates an egg. The habitat and Nursery transaction own effects.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from .dna_v1 import SOCIAL_STATES, validate_social_edge

DECISIONS = ("UNKNOWN", "RECOVER", "ENCOUNTER", "GARDENS_READY", "NURSERY_READY")
ACTIVITIES = ("EAT", "DRINK", "REST", "PLAY", "EXPLORE")
FAMILIAR_INDEX = SOCIAL_STATES.index("FAMILIAR")
SAFE_NEED = 64


def _known(morph: dict[str, Any]) -> bool:
    return (
        isinstance(morph, dict)
        and isinstance(morph.get("morph_id"), str)
        and bool(morph["morph_id"])
        and morph.get("authority") == "HAOS"
        and morph.get("phase") in {"JUVENILE", "MATURE", "AWAKENED"}
        and morph.get("place") in {"HORIZON", "SEREIN_GARDENS", "NURSERY"}
    )


def choose_horizon_activity(morph: dict[str, Any], *, window: int | None = None) -> dict[str, Any]:
    """Pick an urgent need or a stable, bounded ordinary-world activity."""
    if not _known(morph) or morph["place"] != "HORIZON":
        return {"decision": "UNKNOWN", "activity": None, "reason": "NOT_ADMITTED"}
    needs = morph.get("needs")
    if not isinstance(needs, dict) or any(
        type(needs.get(key)) is not int or not 0 <= needs[key] <= 255
        for key in ("food", "water", "rest", "play")
    ):
        return {"decision": "UNKNOWN", "activity": None, "reason": "NEEDS_UNKNOWN"}
    # Low need wins; deterministic order makes retries and restarts stable.
    order = (("food", "EAT"), ("water", "DRINK"), ("rest", "REST"), ("play", "PLAY"))
    lowest, activity = min(order, key=lambda item: (needs[item[0]], order.index(item)))
    if needs[lowest] >= 160:
        if window is None:
            activity = "EXPLORE"
        else:
            # A window-scoped choice varies life without rerolling after restart.
            choices = ("EAT", "DRINK", "REST", "REST", "PLAY", "PLAY", "PLAY",
                       "EXPLORE", "EXPLORE", "EXPLORE", "EXPLORE")
            roll = int.from_bytes(sha256(f"{morph['morph_id']}|{window}|HORIZON".encode()).digest()[:4], "big")
            activity = choices[roll % len(choices)]
        reason = "BOUNDED_VARIATION"
    else:
        reason = "BOUNDED_NEED"
    return {"decision": "ENCOUNTER", "activity": activity, "reason": reason}


def _mutual_edges(
    first: dict[str, Any], second: dict[str, Any],
    first_to_second: dict[str, Any], second_to_first: dict[str, Any],
) -> bool | None:
    try:
        a = validate_social_edge(first_to_second)
        b = validate_social_edge(second_to_first)
    except (TypeError, ValueError):
        return None
    if (
        a["subject_id"] != first["morph_id"]
        or a["object_id"] != second["morph_id"]
        or b["subject_id"] != second["morph_id"]
        or b["object_id"] != first["morph_id"]
    ):
        return None
    return (
        SOCIAL_STATES.index(a["state"]) >= FAMILIAR_INDEX
        and SOCIAL_STATES.index(b["state"]) >= FAMILIAR_INDEX
    )


def decide_pair(
    first: dict[str, Any], second: dict[str, Any],
    first_to_second: dict[str, Any], second_to_first: dict[str, Any],
    *,
    reciprocal_event: bool,
    consent_admitted: bool = False,
    cooldown_clear: bool = False,
    nursery_capacity: int = 0,
    lineage_compatible: bool | None = None,
) -> dict[str, Any]:
    """UMP weighs evidence; downstream place/transaction gates remain mandatory."""
    if not _known(first) or not _known(second) or first["morph_id"] == second["morph_id"]:
        return {"decision": "UNKNOWN", "reason": "IDENTITY_OR_AUTHORITY_UNKNOWN"}
    if first["place"] != second["place"]:
        return {"decision": "UNKNOWN", "reason": "NOT_COLOCATED"}
    mutual = _mutual_edges(first, second, first_to_second, second_to_first)
    if mutual is None:
        return {"decision": "UNKNOWN", "reason": "RELATIONSHIP_EVIDENCE_INVALID"}
    if first["place"] == "HORIZON":
        if not reciprocal_event:
            return {"decision": "UNKNOWN", "reason": "COLOCATION_IS_NOT_INTERACTION"}
        return {
            "decision": "GARDENS_READY" if mutual else "ENCOUNTER",
            "reason": "MUTUAL_FAMILIARITY" if mutual else "RECIPROCAL_EVENT",
        }
    if not mutual:
        return {"decision": "RECOVER", "reason": "MUTUAL_FAMILIARITY_REQUIRED"}
    if first["place"] == "SEREIN_GARDENS":
        return {
            "decision": "GARDENS_READY" if reciprocal_event else "RECOVER",
            "reason": "RECIPROCAL_EVENT" if reciprocal_event else "SOCIAL_EVIDENCE_PENDING",
        }
    if first["place"] != "NURSERY":
        return {"decision": "UNKNOWN", "reason": "PLACE_UNKNOWN"}
    if first["phase"] not in {"MATURE", "AWAKENED"} or second["phase"] not in {"MATURE", "AWAKENED"}:
        return {"decision": "RECOVER", "reason": "MATURITY_REQUIRED"}
    if lineage_compatible is None:
        return {"decision": "UNKNOWN", "reason": "COMPATIBILITY_UNKNOWN"}
    if not lineage_compatible:
        return {"decision": "RECOVER", "reason": "INCOMPATIBLE"}
    if not reciprocal_event or not consent_admitted or not cooldown_clear or type(nursery_capacity) is not int or nursery_capacity < 1:
        return {"decision": "RECOVER", "reason": "NURSERY_GATE_NOT_MET"}
    return {"decision": "NURSERY_READY", "reason": "EVIDENCE_ADMITTED"}
