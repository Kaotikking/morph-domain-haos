"""Mutable Morph presentation contract, deliberately outside immutable DNA."""

from __future__ import annotations

from copy import deepcopy
import hashlib
import hmac
import json
import re
from typing import Any

PRESENTATION_SCHEMA = "serein.morph-presentation.v1"
PRESENTATION_BINDING_SCHEMA = "serein.morph-presentation-binding.v1"
CODE = re.compile(r"^[A-Z][A-Z0-9_-]{0,31}$")
PRONOUN_FIELDS = {"subject", "object", "possessive", "reflexive"}
VISUAL_FIELDS = {"palette_code", "silhouette_code", "marking_code"}


class PresentationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def neutral_presentation(morph_id: str) -> dict[str, Any]:
    return {"schema": PRESENTATION_SCHEMA, "morph_id": morph_id, "revision": 0,
            "gender_code": None, "pronouns": None,
            "visual_expression": {"palette_code": "ORIGIN_NEUTRAL",
                                  "silhouette_code": "ORIGIN_NEUTRAL",
                                  "marking_code": "ORIGIN_NEUTRAL"}}


def validate_presentation(value: dict[str, Any]) -> dict[str, Any]:
    fields = {"schema", "morph_id", "revision", "gender_code", "pronouns", "visual_expression"}
    if not isinstance(value, dict) or set(value) != fields:
        raise PresentationError("INVALID_PRESENTATION", "presentation fields are not exact")
    if value["schema"] != PRESENTATION_SCHEMA or not isinstance(value["morph_id"], str) or not value["morph_id"]:
        raise PresentationError("INVALID_PRESENTATION", "presentation identity is invalid")
    if type(value["revision"]) is not int or value["revision"] < 0:
        raise PresentationError("INVALID_PRESENTATION", "presentation revision is invalid")
    code = value["gender_code"]
    if code is not None and (not isinstance(code, str) or not CODE.fullmatch(code)):
        raise PresentationError("INVALID_PRESENTATION", "gender presentation code is invalid")
    pronouns = value["pronouns"]
    if pronouns is not None:
        if not isinstance(pronouns, dict) or set(pronouns) != PRONOUN_FIELDS:
            raise PresentationError("INVALID_PRESENTATION", "pronoun fields are not exact")
        if any(not isinstance(term, str) or not 1 <= len(term) <= 24 for term in pronouns.values()):
            raise PresentationError("INVALID_PRESENTATION", "pronoun terms are invalid")
    visual = value["visual_expression"]
    if not isinstance(visual, dict) or set(visual) != VISUAL_FIELDS:
        raise PresentationError("INVALID_PRESENTATION", "visual expression fields are not exact")
    if any(not isinstance(code, str) or not CODE.fullmatch(code) for code in visual.values()):
        raise PresentationError("INVALID_PRESENTATION", "visual expression code is invalid")
    return deepcopy(value)


def change_presentation(current: dict[str, Any], candidate: dict[str, Any], *, place: str) -> dict[str, Any]:
    before = validate_presentation(current)
    after = validate_presentation(candidate)
    if place != "CODE_HAVEN":
        raise PresentationError("CODE_HAVEN_REQUIRED", "presentation changes require Code Haven")
    if after["morph_id"] != before["morph_id"]:
        raise PresentationError("IDENTITY_CONFLICT", "presentation cannot change Morph identity")
    if after["revision"] != before["revision"] + 1:
        raise PresentationError("REVISION_CONFLICT", "presentation revision must advance exactly once")
    if after["visual_expression"] == before["visual_expression"]:
        raise PresentationError("VISUAL_DIVERGENCE_REQUIRED",
                                "a Morph cannot leave Code Haven looking the same")
    return {"schema": "serein.morph-presentation-receipt.v1", "morph_id": before["morph_id"],
            "before_digest": _digest(before), "after_digest": _digest(after),
            "presentation": after}


def bind_presentation(*, presentation: dict[str, Any], source_frame: str,
                      habitat_alias: str, generation: int, snapshot_digest: str,
                      place: str, authority: str) -> dict[str, Any]:
    """Bind mutable presentation to one authenticated habitat readback.

    This envelope is deliberately separate from the transfer snapshot.  It may
    be consumed only with the matching Morph, generation, snapshot and frame.
    """
    value = validate_presentation(presentation)
    if not source_frame or not habitat_alias:
        raise PresentationError("INVALID_PRESENTATION_BINDING", "frame binding is required")
    if type(generation) is not int or generation < 1:
        raise PresentationError("INVALID_PRESENTATION_BINDING", "generation is invalid")
    if not isinstance(snapshot_digest, str) or not re.fullmatch(r"[0-9a-f]{64}", snapshot_digest):
        raise PresentationError("INVALID_PRESENTATION_BINDING", "snapshot digest is invalid")
    payload = {"schema": PRESENTATION_BINDING_SCHEMA, "morph_id": value["morph_id"],
               "source_frame": source_frame, "habitat_alias": habitat_alias,
               "generation": generation, "snapshot_digest": snapshot_digest,
               "place": place, "authority": authority,
               "presentation_revision": value["revision"],
               "presentation_digest": _digest(value), "presentation": value}
    payload["binding_digest"] = _digest(payload)
    return payload


def validate_presentation_binding(value: dict[str, Any]) -> dict[str, Any]:
    fields = {"schema", "morph_id", "source_frame", "habitat_alias", "generation",
              "snapshot_digest", "place", "authority", "presentation_revision",
              "presentation_digest", "presentation", "binding_digest"}
    if not isinstance(value, dict) or set(value) != fields or value["schema"] != PRESENTATION_BINDING_SCHEMA:
        raise PresentationError("INVALID_PRESENTATION_BINDING", "binding fields are not exact")
    expected = bind_presentation(presentation=value["presentation"], source_frame=value["source_frame"],
        habitat_alias=value["habitat_alias"], generation=value["generation"],
        snapshot_digest=value["snapshot_digest"], place=value["place"], authority=value["authority"])
    if value["morph_id"] != expected["morph_id"] or value["presentation_revision"] != expected["presentation_revision"]:
        raise PresentationError("PRESENTATION_IDENTITY_CONFLICT", "binding identity or revision differs")
    if not hmac.compare_digest(str(value["presentation_digest"]), expected["presentation_digest"]):
        raise PresentationError("PRESENTATION_DIGEST_MISMATCH", "presentation digest differs")
    if not hmac.compare_digest(str(value["binding_digest"]), expected["binding_digest"]):
        raise PresentationError("PRESENTATION_BINDING_DIGEST_MISMATCH", "binding digest differs")
    return deepcopy(value)

