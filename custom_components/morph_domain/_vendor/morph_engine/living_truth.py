"""DNAv1 Living Truth primitives for MorphDomain.

DNA is immutable. Every mutable expression uses UMP tiers 1..5. Tier 0 is a
reserved founder/source marker and is never a mutable state.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha256
import json
from typing import Any, Final


FOUNDER_SOURCE_TIER: Final = 0
MUTABLE_TIERS: Final = frozenset({1, 2, 3, 4, 5})
PLACES: Final = ("VOID", "NURSERY", "HORIZON", "SEREIN_GARDENS", "CODE_HAVEN")
RELATIONSHIP_LABELS: Final = {
    1: "TRACE", 2: "NOTICE", 3: "FAMILIAR", 4: "BONDED", 5: "KIN",
}
RECOGNITION_LABELS: Final = {
    1: "PRESENT", 2: "NOTICED", 3: "ORIENTED", 4: "RESPONDED", 5: "REMEMBERED",
}
HAVEN_LABELS: Final = {
    1: "ADMITTED", 2: "EXAMINED", 3: "TREATED", 4: "OBSERVED", 5: "RELEASED",
}
HEALTH_LABELS: Final = {
    1: "CRITICAL", 2: "UNWELL", 3: "STABLE", 4: "RECOVERING", 5: "THRIVING",
}


class LivingTruthError(ValueError):
    """Fail-closed Living Truth contract error."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def validate_mutable_tier(value: Any, field_name: str) -> int:
    """Accept only literal integer tiers 1..5; bool and founder tier fail closed."""
    if type(value) is not int or value not in MUTABLE_TIERS:
        raise LivingTruthError(
            "INVALID_MUTABLE_TIER",
            f"{field_name} must be an integer from 1 through 5; 0 is founder-only",
        )
    return value


def step_tier(current: int, delta: int) -> int:
    """Move one bounded UMP step without ever entering founder tier 0."""
    validate_mutable_tier(current, "current")
    if type(delta) is not int or delta not in {-1, 0, 1}:
        raise LivingTruthError("INVALID_TIER_STEP", "tier movement must be -1, 0, or 1")
    return min(5, max(1, current + delta))


def founder_source_marker(value: Any) -> int:
    """Validate the immutable founder/source marker separately from mutable state."""
    if type(value) is not int or value != FOUNDER_SOURCE_TIER:
        raise LivingTruthError("INVALID_FOUNDER_MARKER", "founder/source marker must be 0")
    return value


@dataclass
class FiveTierAxis:
    """A future-safe DNAv1 axis: founder source at 0, lived expression at 1..5."""

    axis_id: str
    founder_line: str
    source_definition: dict[str, Any]
    current_tier: int = FOUNDER_SOURCE_TIER

    def __post_init__(self) -> None:
        if not self.axis_id or not self.founder_line or not isinstance(self.source_definition, dict):
            raise LivingTruthError("INVALID_AXIS_SOURCE", "axis founder source must be attributable")
        if self.current_tier != FOUNDER_SOURCE_TIER:
            validate_mutable_tier(self.current_tier, self.axis_id)

    @property
    def is_founder_source(self) -> bool:
        return self.current_tier == FOUNDER_SOURCE_TIER

    def transition(self, delta: int) -> int:
        """Activate 0→1 once, then use ordinary bounded ±1 UMP movement."""
        if type(delta) is not int or delta not in {-1, 0, 1}:
            raise LivingTruthError("INVALID_TIER_STEP", "tier movement must be -1, 0, or 1")
        if self.current_tier == FOUNDER_SOURCE_TIER:
            if delta != 1:
                raise LivingTruthError(
                    "FOUNDER_SOURCE_IMMUTABLE",
                    "founder source 0 can only begin lived expression at tier 1",
                )
            self.current_tier = 1
        else:
            self.current_tier = step_tier(self.current_tier, delta)
        return self.current_tier

    def machine_record(self) -> dict[str, Any]:
        return {
            "schema": "morph-domain.five-tier-axis.dnav1",
            "axis_id": self.axis_id,
            "founder_line": self.founder_line,
            "source_tier": FOUNDER_SOURCE_TIER,
            "source_definition": deepcopy(self.source_definition),
            "current_tier": self.current_tier,
        }

    def battle_marker(self) -> dict[str, Any]:
        """Expose founder provenance without treating source tier 0 as power."""
        return {
            "axis_id": self.axis_id,
            "founder_line": self.founder_line,
            "founder_source_tier": FOUNDER_SOURCE_TIER,
            "is_founder_line": True,
            "expression_tier": (
                None if self.current_tier == FOUNDER_SOURCE_TIER else self.current_tier
            ),
        }


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        raise LivingTruthError("INVALID_TIME", "event time must include a timezone")
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _digest(value: Any) -> str:
    return sha256(canonical_json(value).encode("utf-8")).hexdigest()


@dataclass
class LivingTruthLedger:
    """Append-only, hash-linked world truth with audience-safe projections."""

    events: list[dict[str, Any]] = field(default_factory=list)

    def append(
        self,
        *,
        event_id: str,
        morph_id: str,
        kind: str,
        place: str,
        actor: str,
        observed_at: datetime,
        public_truth: dict[str, Any],
        operator_truth: dict[str, Any],
        dna_digest_before: str,
        dna_digest_after: str,
    ) -> dict[str, Any]:
        if not all(isinstance(value, str) and value for value in (event_id, morph_id, kind, actor)):
            raise LivingTruthError("MISSING_ATTRIBUTION", "event identity, Morph, kind, and actor are required")
        if place not in PLACES:
            raise LivingTruthError("INVALID_PLACE", "event place is not canonical")
        if dna_digest_before != dna_digest_after:
            raise LivingTruthError("DNA_MUTATION_DENIED", "Living Truth may not change DNA")
        if any(row["event_id"] == event_id for row in self.events):
            existing = next(row for row in self.events if row["event_id"] == event_id)
            return deepcopy(existing)
        previous = self.events[-1]["record_digest"] if self.events else None
        record = {
            "schema": "morph-domain.living-truth.dnav1",
            "event_id": event_id,
            "morph_id": morph_id,
            "kind": kind,
            "place": place,
            "actor": actor,
            "observed_at": _iso(observed_at),
            "public_truth": deepcopy(public_truth),
            "operator_truth": deepcopy(operator_truth),
            "dna_digest": dna_digest_before,
            "previous_digest": previous,
        }
        record["record_digest"] = _digest(record)
        self.events.append(record)
        return deepcopy(record)

    def verify(self) -> bool:
        previous = None
        seen: set[str] = set()
        for row in self.events:
            if row.get("event_id") in seen or row.get("previous_digest") != previous:
                return False
            candidate = {key: deepcopy(value) for key, value in row.items() if key != "record_digest"}
            if row.get("record_digest") != _digest(candidate):
                return False
            seen.add(row["event_id"])
            previous = row["record_digest"]
        return True

    def view(self, audience: str, *, morph_id: str | None = None) -> list[dict[str, Any]]:
        """Operators see the chart; Morphs see only gentle social truth."""
        if audience not in {"OPERATOR", "MORPH"}:
            raise LivingTruthError("INVALID_AUDIENCE", "audience is not admitted")
        selected = [row for row in self.events if morph_id is None or row["morph_id"] == morph_id]
        if audience == "OPERATOR":
            return deepcopy(selected)
        return [{
            "event_id": row["event_id"],
            "morph_id": row["morph_id"],
            "kind": row["kind"],
            "place": row["place"],
            "observed_at": row["observed_at"],
            "truth": deepcopy(row["public_truth"]),
        } for row in selected]


@dataclass
class CodeHavenCase:
    """Five-stage hospital chart; every transition is attributable and append-only."""

    case_id: str
    morph_id: str
    dna_digest: str
    stage: int = 1
    entries: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        validate_mutable_tier(self.stage, "Code Haven stage")
        if self.stage != 1:
            raise LivingTruthError("INVALID_ADMISSION", "a new case must begin at ADMITTED")

    def record(
        self,
        *,
        entry_id: str,
        actor: str,
        action: str,
        result: str,
        observed_at: datetime,
        next_stage: int | None = None,
        public_note: str,
        private_evidence: dict[str, Any],
        dna_digest_after: str,
    ) -> dict[str, Any]:
        if dna_digest_after != self.dna_digest:
            raise LivingTruthError("DNA_MUTATION_DENIED", "Code Haven may verify or restore, never redesign DNA")
        target = self.stage if next_stage is None else validate_mutable_tier(next_stage, "Code Haven stage")
        if target not in {self.stage, self.stage + 1}:
            raise LivingTruthError("INVALID_HAVEN_TRANSITION", "Code Haven stages may hold or advance exactly one step")
        if any(row["entry_id"] == entry_id for row in self.entries):
            return deepcopy(next(row for row in self.entries if row["entry_id"] == entry_id))
        row = {
            "entry_id": entry_id,
            "case_id": self.case_id,
            "morph_id": self.morph_id,
            "from_stage": self.stage,
            "to_stage": target,
            "stage_label": HAVEN_LABELS[target],
            "actor": actor,
            "action": action,
            "result": result,
            "observed_at": _iso(observed_at),
            "public_note": public_note,
            "private_evidence": deepcopy(private_evidence),
            "dna_digest": self.dna_digest,
        }
        row["entry_digest"] = _digest(row)
        self.entries.append(row)
        self.stage = target
        return deepcopy(row)

    def public_logbook(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "morph_id": self.morph_id,
            "stage": self.stage,
            "status": HAVEN_LABELS[self.stage],
            "entries": [{
                "entry_id": row["entry_id"],
                "status": row["stage_label"],
                "observed_at": row["observed_at"],
                "note": row["public_note"],
            } for row in self.entries],
        }

    def operator_chart(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "morph_id": self.morph_id,
            "dna_digest": self.dna_digest,
            "stage": self.stage,
            "status": HAVEN_LABELS[self.stage],
            "entries": deepcopy(self.entries),
        }

