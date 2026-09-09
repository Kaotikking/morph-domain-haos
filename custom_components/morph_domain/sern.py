"""SERN-native MorphDomain control-plane projection.

This module does not replace the established 13-byte fleet packet and does not
carry a Morph snapshot. It emits an attributable control envelope whose nine
core fields can authorize a separate, governed transfer contract.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

SCHEMA = "sern.morph_domain.v1"
NINE_CORES = (
    "identity", "lineage", "life", "expression", "memory",
    "social", "environment", "authority", "transport",
)
MESSAGE_TYPES = frozenset({"STATE", "EVENT", "COMMAND", "RECEIPT", "OPEN_TRANSPORT"})


class SernEnvelopeError(ValueError):
    """A MorphDomain SERN envelope failed closed."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class MorphSernEnvelope:
    message_id: str
    message_type: str
    morph_id: str
    generation: int
    cores: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "message_id": self.message_id,
            "message_type": self.message_type,
            "morph_id": self.morph_id,
            "generation": self.generation,
            "cores": dict(self.cores),
        }

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.as_dict(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()


def validate_envelope(value: Mapping[str, Any]) -> MorphSernEnvelope:
    """Validate the exact nine-core control envelope and reject drift."""
    if set(value) != {"schema", "message_id", "message_type", "morph_id", "generation", "cores"}:
        raise SernEnvelopeError("INVALID_SHAPE", "envelope fields are not exact")
    if value["schema"] != SCHEMA:
        raise SernEnvelopeError("UNSUPPORTED_SCHEMA", "schema is not admitted")
    for field in ("message_id", "message_type", "morph_id"):
        if not isinstance(value[field], str) or not value[field]:
            raise SernEnvelopeError("INVALID_IDENTITY", f"{field} is invalid")
    if value["message_type"] not in MESSAGE_TYPES:
        raise SernEnvelopeError("INVALID_MESSAGE_TYPE", "message type is not admitted")
    if type(value["generation"]) is not int or value["generation"] < 0:
        raise SernEnvelopeError("INVALID_GENERATION", "generation is invalid")
    cores = value["cores"]
    if not isinstance(cores, Mapping) or tuple(cores.keys()) != NINE_CORES:
        raise SernEnvelopeError("INVALID_CORE_PROJECTION", "all nine ordered cores are required")
    return MorphSernEnvelope(
        value["message_id"], value["message_type"], value["morph_id"],
        value["generation"], dict(cores),
    )

