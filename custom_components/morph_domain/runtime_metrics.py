"""Bounded, non-private runtime telemetry for the Morph Engine."""

from __future__ import annotations

from time import perf_counter
from typing import Any


class MorphRuntimeMetrics:
    """Collect process-local counters without touching authoritative Morph state."""

    def __init__(self) -> None:
        self.api_reads = 0
        self.api_mutations = 0
        self.storage_writes_performed = 0
        self.storage_writes_avoided = 0
        self.tick_count = 0
        self.last_api_duration_ms = 0.0
        self.max_api_duration_ms = 0.0
        self.last_tick_duration_ms = 0.0
        self.max_tick_duration_ms = 0.0
        self.last_tick_morphs_evaluated = 0
        self.last_tick_morphs_advanced = 0
        self.expiry_reconciliation_batches = 0

    @staticmethod
    def begin() -> float:
        return perf_counter()

    @staticmethod
    def _elapsed_ms(started: float) -> float:
        return round(max(0.0, (perf_counter() - started) * 1000.0), 3)

    def record_api(self, started: float, *, read: bool) -> None:
        elapsed = self._elapsed_ms(started)
        self.last_api_duration_ms = elapsed
        self.max_api_duration_ms = max(self.max_api_duration_ms, elapsed)
        if read:
            self.api_reads += 1
        else:
            self.api_mutations += 1

    def record_storage_decision(self, *, performed: bool) -> None:
        if performed:
            self.storage_writes_performed += 1
        else:
            self.storage_writes_avoided += 1

    def record_expiry_reconciliation(self, *, changed: bool) -> None:
        if changed:
            self.expiry_reconciliation_batches += 1

    def record_tick(self, started: float, *, evaluated: int, advanced: int) -> None:
        elapsed = self._elapsed_ms(started)
        self.tick_count += 1
        self.last_tick_duration_ms = elapsed
        self.max_tick_duration_ms = max(self.max_tick_duration_ms, elapsed)
        self.last_tick_morphs_evaluated = evaluated
        self.last_tick_morphs_advanced = advanced

    def snapshot(self, ledger_data: dict[str, Any]) -> dict[str, Any]:
        """Return bounded operational metrics; never expose Morph payloads."""
        morphs = ledger_data.get("morphs", {})
        chronicle_events = sum(
            len(morph.get("chronicle", []))
            + len(morph.get("habitat", {}).get("history", []))
            for morph in morphs.values()
            if isinstance(morph, dict)
        )
        return {
            "schema": "serein.morph-engine-observability.v1",
            "status": "ACTIVE" if self.tick_count else "STARTING",
            "tick_count": self.tick_count,
            "last_tick_duration_ms": self.last_tick_duration_ms,
            "max_tick_duration_ms": self.max_tick_duration_ms,
            "last_tick_morphs_evaluated": self.last_tick_morphs_evaluated,
            "last_tick_morphs_advanced": self.last_tick_morphs_advanced,
            "api_reads": self.api_reads,
            "api_mutations": self.api_mutations,
            "last_api_duration_ms": self.last_api_duration_ms,
            "max_api_duration_ms": self.max_api_duration_ms,
            "storage_writes_performed": self.storage_writes_performed,
            "storage_writes_avoided": self.storage_writes_avoided,
            "expiry_reconciliation_batches": self.expiry_reconciliation_batches,
            "morph_count": len(morphs),
            "chronicle_event_count": chronicle_events,
        }
