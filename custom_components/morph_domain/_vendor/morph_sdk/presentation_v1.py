"""Morph World presentation foundation v1: pure, deterministic, side-effect free."""

from __future__ import annotations

from hashlib import sha256
import json
import re

SCHEMA = "serein.morph-id-card.v1"
ELEMENTS = {"01": "FIRE", "02": "AIR", "03": "EARTH", "04": "WATER"}
CORES = ("identity", "lineage", "life", "expression", "capability", "relationship", "memory", "presentation", "authority")
CARE_KEYS = ("SUS", "ATT", "PLY", "SOC", "AFF")
CARE_PATHS = {
    "RESTORATIVE": ("SUS", "ATT"),
    "ATTUNED": ("ATT", "AFF"),
    "EXPLORATORY": ("PLY", "AFF"),
    "RELATIONAL": ("SOC", "AFF"),
    "GUARDIAN": ("SUS", "SOC"),
}
CAPABILITY_PATHS = ("MOVEMENT", "PROTECTION", "RESTORATION", "PERCEPTION", "PROJECTION")
RITUAL = ("IDENTIFY", "CALL", "FORM", "REVEAL", "SIGNATURE", "SETTLE")
BRANCH_RE = re.compile(r"^(?:F|L1|E)-(?:01|02|03|04)$|^L2-(?:01|02|03|04)\.(?:01|02|03|04)$")


def validate_branch_id(branch_id: str) -> str:
    if not BRANCH_RE.fullmatch(branch_id):
        raise ValueError("unknown Morph branch id")
    if branch_id.startswith("L2-"):
        left, right = branch_id[3:].split(".")
        if left >= right:
            raise ValueError("composite element vector must be unique and sorted")
    return branch_id


def validate_care(care: dict[str, int]) -> dict[str, int]:
    if set(care) != set(CARE_KEYS):
        raise ValueError("care vector must contain SUS, ATT, PLY, SOC, AFF exactly")
    if any(type(value) is not int or not 0 <= value <= 5 for value in care.values()):
        raise ValueError("care values must be integers from 0 through 5")
    return dict(care)


def resolve_care(care: dict[str, int], earned_stage: int = 1) -> dict[str, object]:
    values = validate_care(care)
    if not 1 <= earned_stage <= 5:
        raise ValueError("earned_stage must be 1 through 5")
    stage = max(earned_stage, max(1, min(values.values())))
    scores = {name: sum(values[key] for key in keys) for name, keys in CARE_PATHS.items()}
    best = max(scores.values())
    branches = tuple(name for name, score in scores.items() if score == best)
    return {"earned_stage": stage, "eligible_branches": branches, "active_branch": branches[0] if len(branches) == 1 else "PENDING"}


def presentation_recipe(*, element: str, care_branch: str, capability_path: str,
                        trait_polarity: int, origin_signature: str,
                        context: str) -> dict[str, object]:
    if element not in ELEMENTS.values():
        raise ValueError("unknown primitive element")
    if care_branch not in CARE_PATHS and care_branch != "PENDING":
        raise ValueError("unknown care branch")
    if capability_path not in CAPABILITY_PATHS:
        raise ValueError("unknown capability path")
    if trait_polarity not in (-1, 0, 1):
        raise ValueError("trait polarity must be -1, 0, or 1")
    return {
        "lineage_base": element,
        "care_branch_expression": care_branch,
        "power_capability_expression": capability_path,
        "trait_modifier": trait_polarity,
        "origin_signature": origin_signature,
        "current_context": context,
        "ritual": RITUAL,
    }


def onboarding_decision(*, imported_morph: bool, existing_starter: bool) -> str:
    if imported_morph:
        return "IMPORT_PRESERVED_NO_STARTER"
    if existing_starter:
        return "EXISTING_STARTER_PRESERVED"
    return "CREATE_ONE_L1_STARTER"


def horizon_discovery(*, legendary_present: bool, lineage_known: bool, evidence: int) -> dict[str, object]:
    if not 0 <= evidence <= 5:
        raise ValueError("discovery evidence must be 0 through 5")
    unlocked = legendary_present and not lineage_known and evidence == 5
    return {"blueprint_unlocked": unlocked, "creates_morph": False}


def validate_id_card(card: dict[str, object]) -> dict[str, object]:
    if card.get("schema") != SCHEMA or set(card) != {"schema", *CORES}:
        raise ValueError("Morph ID Card schema or nine-core shape is invalid")
    if any(not isinstance(card[core], dict) for core in CORES):
        raise ValueError("each Morph ID Card core must be an object")
    lineage = card["lineage"]
    validate_branch_id(str(lineage.get("branch_id", "")))
    owner = card["authority"].get("active_owner")
    if not isinstance(owner, str) or not owner:
        raise ValueError("one active owner is required")
    return card


def compact_card(card: dict[str, object]) -> dict[str, str]:
    valid = validate_id_card(card)
    canonical = json.dumps(valid, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "schema": SCHEMA,
        "morph_id": str(valid["identity"].get("morph_id", "")),
        "branch_id": str(valid["lineage"]["branch_id"]),
        "active_owner": str(valid["authority"]["active_owner"]),
        "digest": sha256(canonical.encode()).hexdigest(),
    }

