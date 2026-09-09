"""Runtime observability remains bounded and outside authoritative Morph state."""

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "custom_components" / "morph_domain" / "runtime_metrics.py"
SPEC = importlib.util.spec_from_file_location("runtime_metrics", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
MorphRuntimeMetrics = MODULE.MorphRuntimeMetrics


def test_runtime_metrics_count_decisions_without_payloads() -> None:
    metrics = MorphRuntimeMetrics()
    started = metrics.begin()
    metrics.record_api(started, read=True)
    metrics.record_storage_decision(performed=False)
    metrics.record_expiry_reconciliation(changed=False)
    metrics.record_tick(started, evaluated=4, advanced=1)

    ledger = {
        "morphs": {
            "secret-morph-id": {
                "chronicle": [{"event": "one"}],
                "habitat": {"history": [{"event": "two"}]},
                "private_genome": "must-not-leak",
            }
        }
    }
    snapshot = metrics.snapshot(ledger)

    assert snapshot["schema"] == "serein.morph-engine-observability.v1"
    assert snapshot["status"] == "ACTIVE"
    assert snapshot["api_reads"] == 1
    assert snapshot["api_mutations"] == 0
    assert snapshot["storage_writes_avoided"] == 1
    assert snapshot["storage_writes_performed"] == 0
    assert snapshot["last_tick_morphs_evaluated"] == 4
    assert snapshot["last_tick_morphs_advanced"] == 1
    assert snapshot["morph_count"] == 1
    assert snapshot["chronicle_event_count"] == 2
    assert "secret-morph-id" not in str(snapshot)
    assert "must-not-leak" not in str(snapshot)


def test_runtime_metrics_track_high_water_marks() -> None:
    metrics = MorphRuntimeMetrics()
    metrics.record_storage_decision(performed=True)
    metrics.record_expiry_reconciliation(changed=True)
    metrics.record_api(metrics.begin(), read=False)
    first = metrics.snapshot({"morphs": {}})
    metrics.record_api(metrics.begin(), read=False)
    second = metrics.snapshot({"morphs": {}})

    assert second["api_mutations"] == 2
    assert second["storage_writes_performed"] == 1
    assert second["expiry_reconciliation_batches"] == 1
    assert second["max_api_duration_ms"] >= first["max_api_duration_ms"]
