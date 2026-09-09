"""Gen-1 drop-in package admission and form resolution."""

from __future__ import annotations

from hashlib import sha256
import json
import re

SCHEMA_VERSION = "1.0.0"
ELEMENTS = {"01": "FIRE", "02": "AIR", "03": "EARTH", "04": "WATER"}
PACKAGE_KINDS = ("FOUNDER", "EVOLUTION", "PRESENTATION")
EVOLUTION_CLASSES = ("NATURAL", "CONTEXT", "RESONANCE", "CULMINATION")
RESERVED_EVOLUTION_CLASSES = ("FRAME_ARMOR", "COMBINED", "BATTLE")
EVIDENCE_KEYS = ("CARE", "RELATIONSHIP", "WEATHER", "LOCATION", "FRAME", "ACTIVITY", "CAPABILITY", "EVENT", "ENERGY")
MORPH_CORES = ("platform", "root", "memory", "knowledge", "ui", "audio", "personality", "modular", "cloud")
PACKAGE_ID = re.compile(r"^PKG-(FOUNDER|EVOLUTION|PRESENTATION)-[A-Z0-9_.-]+@\d+\.\d+\.\d+$")
FORM_ID = re.compile(r"^FORM-(?:01|02|03|04)(?:\.(?:01|02|03|04))*-[A-Z0-9_.-]+$")


def canonical_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return sha256(encoded.encode()).hexdigest()


def validate_evidence(evidence: dict[str, int]) -> dict[str, int]:
    if not set(evidence).issubset(EVIDENCE_KEYS):
        raise ValueError("unknown evidence category")
    if any(type(value) is not int or not 0 <= value <= 5 for value in evidence.values()):
        raise ValueError("evidence weights must be integers from 0 through 5")
    return dict(evidence)


def validate_package(package: dict[str, object]) -> dict[str, object]:
    required = {"schema", "package_id", "kind", "compatibility", "payload", "fallback", "fixtures"}
    if set(package) != required or package["schema"] != "serein.morph-package.v1":
        raise ValueError("invalid package envelope")
    if package["kind"] not in PACKAGE_KINDS or not PACKAGE_ID.fullmatch(str(package["package_id"])):
        raise ValueError("invalid package identity")
    if not isinstance(package["compatibility"], dict) or package["compatibility"].get("engine_major") != 1:
        raise ValueError("incompatible engine major")
    if not package["fallback"] or not isinstance(package["fixtures"], list):
        raise ValueError("fallback and fixtures are required")
    payload = package["payload"]
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    {"FOUNDER": _validate_founder, "EVOLUTION": _validate_evolution, "PRESENTATION": _validate_presentation}[package["kind"]](payload)
    return package


def _validate_founder(payload: dict[str, object]) -> None:
    required = {"element_id", "founder_id", "public_lineage_id", "starter_id", "name", "primary", "recessive", "signature", "word_pools", "palette", "catalysts"}
    if set(payload) != required:
        raise ValueError("invalid Founder template")
    element = str(payload["element_id"])
    if element not in ELEMENTS:
        raise ValueError("unregistered element")
    if payload["founder_id"] != f"F-{element}" or payload["public_lineage_id"] != f"E-{element}" or payload["starter_id"] != f"L1-{element}":
        raise ValueError("Founder package IDs must derive from one element ID")
    if payload["primary"] != ELEMENTS[element]:
        raise ValueError("primary element mismatch")


def _validate_evolution(payload: dict[str, object]) -> None:
    required = {"form_id", "class", "lineages", "evidence", "catalysts", "capabilities", "stability", "reversion", "presentation_id", "exclusions"}
    if set(payload) != required or not FORM_ID.fullmatch(str(payload["form_id"])):
        raise ValueError("invalid Evolution template")
    if payload["class"] not in EVOLUTION_CLASSES:
        raise ValueError("inactive or unknown evolution class")
    validate_evidence(payload["evidence"])
    if payload["reversion"] not in ("RESTING_FORM", "CONTEXT_END", "ENERGY_FLOOR", "STABLE"):
        raise ValueError("invalid reversion rule")


def _validate_presentation(payload: dict[str, object]) -> None:
    required = {"presentation_id", "forms", "capability_tiers", "silhouette", "palette", "effects", "animations", "voice", "localization", "accessibility", "frame_profiles"}
    if set(payload) != required:
        raise ValueError("invalid Presentation template")
    if "SERN-LOW" not in payload["frame_profiles"]:
        raise ValueError("canonical constrained fallback is required")


def admit_packages(packages: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    admitted: dict[str, dict[str, object]] = {}
    for package in packages:
        valid = validate_package(package)
        package_id = str(valid["package_id"])
        if package_id in admitted:
            raise ValueError("duplicate package")
        admitted[package_id] = valid
    return admitted


def eligible_forms(*, lineage_ids: set[str], evidence: dict[str, int], catalysts: set[str],
                   packages: dict[str, dict[str, object]]) -> tuple[str, ...]:
    observed = validate_evidence(evidence)
    forms: list[str] = []
    for package in packages.values():
        if package["kind"] != "EVOLUTION":
            continue
        payload = package["payload"]
        if not lineage_ids.intersection(payload["lineages"]):
            continue
        if any(observed.get(key, 0) < value for key, value in payload["evidence"].items()):
            continue
        if not set(payload["catalysts"]).issubset(catalysts):
            continue
        forms.append(str(payload["form_id"]))
    return tuple(sorted(forms))


def select_presentation(*, form_id: str, frame_profile: str,
                        packages: dict[str, dict[str, object]]) -> dict[str, str]:
    for package in packages.values():
        if package["kind"] != "PRESENTATION":
            continue
        payload = package["payload"]
        if form_id in payload["forms"]:
            chosen = frame_profile if frame_profile in payload["frame_profiles"] else "SERN-LOW"
            return {"presentation_id": str(payload["presentation_id"]), "frame_profile": chosen}
    return {"presentation_id": "SEREIN-CANONICAL-FALLBACK", "frame_profile": "SERN-LOW"}

