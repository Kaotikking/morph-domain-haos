"""SERN-native MorphDomain control-plane projection."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping

SCHEMA = "sern.morph_domain.v1"
MAX_ENVELOPE_BYTES = 16384
NINE_CORES = ("identity", "lineage", "life", "expression", "memory", "social", "environment", "authority", "transport")
MESSAGE_TYPES = frozenset({"STATE", "EVENT", "COMMAND", "RECEIPT", "OPEN_TRANSPORT"})


class SernEnvelopeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _strict_json(value: Any, path: str = "envelope") -> None:
    if value is None or type(value) in {str, int, bool}:
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise SernEnvelopeError("INVALID_JSON", f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _strict_json(item, f"{path}[{index}]")
        return
    if isinstance(value, dict) and all(isinstance(k, str) and k for k in value):
        for key, item in value.items():
            _strict_json(item, f"{path}.{key}")
        return
    raise SernEnvelopeError("INVALID_JSON", f"{path} is not strict JSON")


def _encoded(value: Any) -> bytes:
    _strict_json(value)
    try:
        data = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as err:
        raise SernEnvelopeError("INVALID_JSON", "envelope is not canonical JSON") from err
    if len(data) > MAX_ENVELOPE_BYTES:
        raise SernEnvelopeError("ENVELOPE_TOO_LARGE", "SERN envelope exceeds the control-plane limit")
    return data


@dataclass(frozen=True)
class MorphSernEnvelope:
    message_id: str
    message_type: str
    morph_id: str
    generation: int
    cores: Mapping[str, Any]

    def as_dict(self) -> dict[str, Any]:
        return {"schema": SCHEMA, "message_id": self.message_id, "message_type": self.message_type,
                "morph_id": self.morph_id, "generation": self.generation, "cores": dict(self.cores)}

    @property
    def digest(self) -> str:
        return hashlib.sha256(_encoded(self.as_dict())).hexdigest()


def validate_envelope(value: Mapping[str, Any]) -> MorphSernEnvelope:
    if not isinstance(value, dict) or set(value) != {"schema", "message_id", "message_type", "morph_id", "generation", "cores"}:
        raise SernEnvelopeError("INVALID_SHAPE", "envelope fields are not exact")
    _encoded(value)
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
    identity = cores["identity"]
    if identity:
        if not isinstance(identity, dict) or identity.get("morph_id") != value["morph_id"] or identity.get("generation") != value["generation"]:
            raise SernEnvelopeError("IDENTITY_BINDING_MISMATCH", "identity Core does not bind envelope identity and generation")
    transport = cores["transport"]
    if isinstance(transport, dict) and "payload" in transport:
        raise SernEnvelopeError("TRANSPORT_PAYLOAD_PROHIBITED", "SERN control envelopes may signal transport but never carry a Morph snapshot")
    return MorphSernEnvelope(value["message_id"], value["message_type"], value["morph_id"], value["generation"], dict(cores))
