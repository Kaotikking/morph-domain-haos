"""Reduced, read-only Morph Window contract for dedicated consumer frames."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from hashlib import sha256
import json
from typing import Any

WINDOW_SCHEMA = "serein.morph-window.v1"
AVATAR_SCHEMA = "serein.morph-pixel-avatar.v1"
WINDOW_TTL = timedelta(minutes=5)
WINDOW_STATES = {"LOCAL_PRESENCE", "DOMAIN_WINDOW", "RETURNING_HOME"}

PALETTES = {
    "FIRE": ("#00000000", "#FF713D", "#FFD16A"),
    "WATER": ("#00000000", "#45B8FF", "#77EADC"),
    "AIR": ("#00000000", "#D8F5FF", "#9EBEFF"),
    "EARTH": ("#00000000", "#91BD64", "#D7AD64"),
    "ORIGIN": ("#00000000", "#D9E6FF", "#829FC8"),
}

# Twelve-column masks stay legible on the smallest admitted pixel frame.  A
# deterministic DNA/presentation marking is overlaid without changing truth.
MASKS = {
    "FIRE": ("000001100000", "000011100000", "000111110000", "001111111000",
             "011111111100", "011111111100", "111111111110", "111111111110",
             "011111111100", "001111111000", "000111110000", "000011100000"),
    "WATER": ("000001100000", "000011110000", "000111111000", "001111111100",
              "011111111110", "111111111111", "111111111111", "111111111111",
              "011111111110", "001111111100", "000111111000", "000011110000"),
    "AIR": ("000000000000", "000011110000", "001111111000", "011111111100",
            "111111111110", "111111111111", "111111111111", "011111111110",
            "001111111100", "000111111000", "000011110000", "000000000000"),
    "EARTH": ("000111111000", "001111111100", "011111111110", "111111111111",
              "111111111111", "111111111111", "111111111111", "111111111111",
              "111111111111", "011111111110", "001111111100", "000111111000"),
    "ORIGIN": ("000011110000", "000111111000", "001111111100", "011111111110",
               "011111111110", "111111111111", "111111111111", "011111111110",
               "011111111110", "001111111100", "000111111000", "000011110000"),
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _element(status: dict[str, Any]) -> str:
    try:
        value = status["life"]["morph_core"]["root"]["identity"]["primitive_element"]
    except (KeyError, TypeError):
        value = None
    aliases = {"PULSE": "WATER", "SPARK": "AIR", "BREEZE": "AIR",
               "EMBER": "FIRE", "SENTINEL": "EARTH"}
    candidate = str(value or aliases.get(str(status.get("founder_id", "")).upper(), "ORIGIN")).upper()
    return candidate if candidate in PALETTES else "ORIGIN"


def _avatar(status: dict[str, Any]) -> dict[str, Any]:
    element = _element(status)
    presentation = status.get("presentation") if isinstance(status.get("presentation"), dict) else {}
    revision = int(presentation.get("revision", 0))
    seed = sha256(f'{status["morph_id"]}:{status["founder_id"]}:{revision}'.encode()).digest()
    rows = []
    bit = 0
    for row in MASKS[element]:
        pixels = list(row)
        for index, pixel in enumerate(pixels):
            if pixel == "1" and (seed[bit % len(seed)] >> (bit % 8)) & 1 and (index + bit) % 5 == 0:
                pixels[index] = "2"
            bit += 1
        rows.append("".join(pixels))
    avatar = {
        "schema": AVATAR_SCHEMA,
        "morph_id": status["morph_id"],
        "width": 12,
        "height": 12,
        "element": element,
        "palette": list(PALETTES[element]),
        "rows": rows,
        "presentation_revision": revision,
        "snapshot_digest": status["snapshot_digest"],
    }
    avatar["avatar_digest"] = sha256(_canonical(avatar).encode()).hexdigest()
    return avatar


def _scene(status: dict[str, Any]) -> dict[str, Any]:
    social = status.get("social") if isinstance(status.get("social"), dict) else {}
    activity = social.get("last_activity") if isinstance(social.get("last_activity"), dict) else {}
    kind = str(activity.get("kind") or status.get("life", {}).get("behavior") or "SETTLE").upper()
    expression = str(activity.get("expression") or kind).upper()
    participants = activity.get("participants") if isinstance(activity.get("participants"), list) else []
    companions = [str(value) for value in participants if str(value) != status["morph_id"]]
    return {"kind": kind, "expression": expression, "companions": companions[:2]}


def _returning(operations: dict[str, Any], morph_id: str) -> bool:
    terminal = {"FRAME_ACTIVE", "ACTIVE_HAOS", "RETURN_EXPIRED", "CANCELLED", "FAILED"}
    return any(operation.get("morph_id") == morph_id
               and operation.get("operation_kind") in {"RETURN_TO_FRAME", "RECALL_FROM_FRAME"}
               and operation.get("state") not in terminal
               for operation in operations.values())


def build_morph_window(status: dict[str, Any], operations: dict[str, Any], now: datetime) -> dict[str, Any]:
    """Build a custody-bound projection.  It never moves or mutates a Morph."""
    if not isinstance(status, dict) or not isinstance(operations, dict):
        raise ValueError("Morph Window requires admitted status and operation ledger")
    if _returning(operations, str(status["morph_id"])):
        state = "RETURNING_HOME"
    elif status.get("authority") == "HAOS":
        state = "DOMAIN_WINDOW"
    else:
        state = "LOCAL_PRESENCE"
    if state not in WINDOW_STATES:
        raise ValueError("invalid Morph Window state")
    issued = now.astimezone(UTC)
    result = {
        "schema": WINDOW_SCHEMA,
        "morph_id": status["morph_id"],
        "display_name": status.get("presentation", {}).get("display_name") or status["morph_id"],
        "state": state,
        "authority": status["authority"],
        "source_frame": status["source_frame"],
        "place": status["place"],
        "custody_revision": status["custody_revision"],
        "lineage_generation": status.get("lineage_generation"),
        "snapshot_digest": status["snapshot_digest"],
        "issued_at": issued.isoformat().replace("+00:00", "Z"),
        "expires_at": (issued + WINDOW_TTL).isoformat().replace("+00:00", "Z"),
        "scene": _scene(status),
        "life_call": deepcopy(status.get("life_call", {}).get("active")),
        "avatar": _avatar(status),
    }
    result["window_digest"] = sha256(_canonical(result).encode()).hexdigest()
    return deepcopy(result)

