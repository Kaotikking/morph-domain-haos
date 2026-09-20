"""Bounded HAOS-native projections of authoritative Morph state.

This module deliberately contains no Home Assistant imports so projection rules
remain deterministic and independently testable.  It never mutates Morph truth.
"""

from __future__ import annotations

from typing import Any


CORE_ORDER = (
    "platform",
    "root",
    "memory",
    "knowledge",
    "ui",
    "audio",
    "personality",
    "modular",
    "cloud",
)

PLACE_AREAS = {
    "VOID": "Void",
    "NURSERY": "Nursery",
    "SEREIN_GARDENS": "Serein Gardens",
    "HORIZON": "Horizon",
    "CODE_HAVEN": "Code Haven",
}


def display_name(morph: dict[str, Any]) -> str:
    """Return the player-facing name without replacing immutable identity."""
    presentation = morph.get("presentation") or {}
    name = presentation.get("display_name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    founder = str(morph.get("founder_id") or "").strip()
    if founder and founder not in {"DESCENDANT", "UNKNOWN"}:
        return founder.title()
    morph_id = str(morph.get("morph_id") or "UNKNOWN")
    return morph_id.rsplit(":", 1)[-1][:12]


def custody_state(morph: dict[str, Any]) -> str:
    """Project custody separately from the habitat's last canonical place."""
    authority = str(morph.get("authority") or "UNKNOWN")
    if authority == "HAOS":
        return str(morph.get("place") or "UNKNOWN")
    if authority == "FROZEN_FOR_RETURN":
        return "RETURNING"
    if authority.startswith(("esp32-frame:", "android-frame:")):
        return "FRAME"
    return "UNKNOWN"


def native_area(morph: dict[str, Any]) -> str | None:
    """Only HAOS-owned Morphs inhabit MorphDomain's native HAOS areas."""
    if morph.get("authority") != "HAOS":
        return None
    return PLACE_AREAS.get(str(morph.get("place")))


def nine_core(morph: dict[str, Any]) -> dict[str, Any]:
    """Return the portable nine-core object, or an empty bounded projection."""
    life = morph.get("life") or {}
    core = life.get("morph_core") or {}
    return core if isinstance(core, dict) else {}


def _chronicle_count(memory: dict[str, Any]) -> int:
    chronicle = memory.get("chronicle") or {}
    events = chronicle.get("events") or []
    archive = memory.get("chronicle_archive") or {}
    return len(events) + int(archive.get("count") or 0)


def core_projection(morph: dict[str, Any], core_name: str) -> tuple[Any, dict[str, Any]]:
    """Reduce one core to a useful state plus bounded HAOS attributes."""
    if core_name not in CORE_ORDER:
        raise ValueError("unknown Morph core")
    core = nine_core(morph)
    value = core.get(core_name) if isinstance(core.get(core_name), dict) else {}

    if core_name == "platform":
        embodiment = value.get("embodiment") or {}
        return embodiment.get("body_class", "UNKNOWN"), {
            "runtime": value.get("runtime", "UNKNOWN"),
            "body_id": embodiment.get("body_id", "UNKNOWN"),
            "capabilities": list(embodiment.get("capabilities") or [])[:16],
        }
    if core_name == "root":
        identity = value.get("identity") or {}
        return morph.get("founder_id", "UNKNOWN"), {
            "morph_id": morph.get("morph_id"),
            "founder_id": morph.get("founder_id"),
            "device_birth_lineage": morph.get("device_birth_lineage"),
            "primitive_element": identity.get("primitive_element", "UNKNOWN"),
            "lineage_generation": morph.get("lineage_generation"),
        }
    if core_name == "memory":
        return _chronicle_count(value), {
            "journey_count": (value.get("life") or {}).get("journey_count", 0),
            "chronicle_count": _chronicle_count(value),
        }
    if core_name == "knowledge":
        learned = value.get("learned") or {}
        return len(learned), {"learned_keys": sorted(str(key) for key in learned)[:16]}
    if core_name == "ui":
        return value.get("expression_stage", 0), {
            "expression": value.get("expression", "UNKNOWN"),
            "visual_seed": value.get("visual_seed"),
        }
    if core_name == "audio":
        return value.get("element_voice", "UNKNOWN"), {
            "render_model": value.get("render_model", "UNKNOWN"),
            "expression_level": value.get("expression_level", 0),
        }
    if core_name == "personality":
        return value.get("mood", "UNKNOWN"), {
            "active_trait": value.get("active_trait", "UNKNOWN"),
            "trait_stage": value.get("trait_stage", 0),
        }
    if core_name == "modular":
        capabilities = list(value.get("capabilities") or [])
        return len(capabilities), {"capabilities": capabilities[:16]}
    return custody_state(morph), {
        "place": morph.get("place", "UNKNOWN"),
        "authority": morph.get("authority", "UNKNOWN"),
        "habitat_engine_state": morph.get("habitat_engine_state", "UNKNOWN"),
        "reconciliation": value.get("reconciliation", "UNKNOWN"),
    }


