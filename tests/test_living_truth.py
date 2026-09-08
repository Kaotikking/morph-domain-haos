from copy import deepcopy
from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys

import pytest


SOURCE = Path(__file__).parents[1] / "custom_components/morph_domain/_vendor/morph_engine/living_truth.py"
spec = importlib.util.spec_from_file_location("living_truth_test", SOURCE)
living = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = living
spec.loader.exec_module(living)


NOW = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
DNA = "a" * 64


def test_zero_is_founder_only_and_mutable_state_is_exactly_one_through_five():
    assert living.founder_source_marker(0) == 0
    for tier in range(1, 6):
        assert living.validate_mutable_tier(tier, "test") == tier
    for invalid in (0, -1, 6, True, 1.0, "1"):
        with pytest.raises(living.LivingTruthError) as caught:
            living.validate_mutable_tier(invalid, "test")
        assert caught.value.code == "INVALID_MUTABLE_TIER"


def test_tier_math_is_bounded_and_can_never_regress_into_founder_zero():
    assert living.step_tier(1, -1) == 1
    assert living.step_tier(1, 1) == 2
    assert living.step_tier(5, 1) == 5
    with pytest.raises(living.LivingTruthError):
        living.step_tier(3, 2)


def test_founder_zero_makes_new_mutable_axes_schema_stable_without_rebuild():
    axis = living.FiveTierAxis(
        axis_id="weather_attunement",
        founder_line="BREEZE",
        source_definition={"primitive": "AIR", "recessive": "ELECTRICITY"},
    )
    assert axis.is_founder_source
    assert axis.machine_record()["source_tier"] == 0
    assert axis.machine_record()["current_tier"] == 0
    assert axis.transition(1) == 1
    assert not axis.is_founder_source
    assert axis.transition(1) == 2
    assert axis.transition(-1) == 1
    assert axis.transition(-1) == 1
    assert axis.machine_record()["source_definition"] == {
        "primitive": "AIR", "recessive": "ELECTRICITY"
    }


def test_founder_zero_cannot_be_used_as_a_mutable_or_regressive_destination():
    axis = living.FiveTierAxis("greeting", "PULSE", {"primitive": "WATER"})
    for delta in (-1, 0):
        with pytest.raises(living.LivingTruthError) as caught:
            axis.transition(delta)
        assert caught.value.code == "FOUNDER_SOURCE_IMMUTABLE"


def test_battle_marker_keeps_founder_provenance_out_of_power_math():
    axis = living.FiveTierAxis("combat_expression", "EMBER", {"primitive": "FIRE"})
    source = axis.battle_marker()
    assert source["founder_source_tier"] == 0
    assert source["is_founder_line"] is True
    assert source["expression_tier"] is None

    axis.transition(1)
    active = axis.battle_marker()
    assert active["founder_source_tier"] == 0
    assert active["expression_tier"] == 1
    assert active["expression_tier"] in living.MUTABLE_TIERS


def test_living_truth_is_append_only_hash_linked_and_dna_immutable():
    ledger = living.LivingTruthLedger()
    first = ledger.append(
        event_id="arrival-1", morph_id="breeze", kind="ARRIVAL", place="HORIZON",
        actor="HAOS", observed_at=NOW, public_truth={"recognition": 2},
        operator_truth={"authority": "HAOS"}, dna_digest_before=DNA, dna_digest_after=DNA,
    )
    assert first["previous_digest"] is None
    assert ledger.verify()
    assert ledger.append(
        event_id="arrival-1", morph_id="breeze", kind="ARRIVAL", place="HORIZON",
        actor="HAOS", observed_at=NOW, public_truth={"recognition": 2},
        operator_truth={"authority": "HAOS"}, dna_digest_before=DNA, dna_digest_after=DNA,
    ) == first
    assert len(ledger.events) == 1
    with pytest.raises(living.LivingTruthError) as caught:
        ledger.append(
            event_id="bad", morph_id="breeze", kind="CARE", place="HORIZON",
            actor="HAOS", observed_at=NOW, public_truth={}, operator_truth={},
            dna_digest_before=DNA, dna_digest_after="b" * 64,
        )
    assert caught.value.code == "DNA_MUTATION_DENIED"


def test_tampering_is_detected_and_morph_view_never_leaks_private_evidence():
    ledger = living.LivingTruthLedger()
    ledger.append(
        event_id="haven-1", morph_id="sentinel", kind="HAVEN_STATUS", place="CODE_HAVEN",
        actor="HAOS", observed_at=NOW, public_truth={"status": "RECOVERING"},
        operator_truth={"diagnostic": "private-detail", "rollback": "checkpoint-1"},
        dna_digest_before=DNA, dna_digest_after=DNA,
    )
    morph_view = ledger.view("MORPH")
    assert morph_view[0]["truth"] == {"status": "RECOVERING"}
    assert "operator_truth" not in morph_view[0]
    altered = deepcopy(ledger.events[0])
    ledger.events[0]["public_truth"]["status"] = "READY"
    assert not ledger.verify()
    ledger.events[0] = altered
    assert ledger.verify()


def test_code_haven_is_a_five_stage_hospital_chart_with_no_skips():
    case = living.CodeHavenCase("case-1", "sentinel", DNA)
    assert case.public_logbook()["status"] == "ADMITTED"
    for index, expected in enumerate(("EXAMINED", "TREATED", "OBSERVED", "RELEASED"), start=2):
        case.record(
            entry_id=f"entry-{index}", actor="HAOS", action=expected,
            result="PASS", observed_at=NOW, next_stage=index,
            public_note=expected.title(), private_evidence={"check": index},
            dna_digest_after=DNA,
        )
        assert case.public_logbook()["status"] == expected
    assert [row["to_stage"] for row in case.operator_chart()["entries"]] == [2, 3, 4, 5]
    assert "private_evidence" not in case.public_logbook()["entries"][0]


def test_code_haven_records_failed_treatment_without_advancing_or_erasing_it():
    case = living.CodeHavenCase("case-2", "pulse", DNA)
    failed = case.record(
        entry_id="failed-check", actor="HAOS", action="DIAGNOSTIC",
        result="FAILED", observed_at=NOW, public_note="Still being examined",
        private_evidence={"error": "CHECK_FAILED"}, dna_digest_after=DNA,
    )
    assert failed["from_stage"] == failed["to_stage"] == 1
    assert case.stage == 1
    assert case.operator_chart()["entries"][0]["result"] == "FAILED"
    with pytest.raises(living.LivingTruthError) as caught:
        case.record(
            entry_id="skip", actor="HAOS", action="RELEASE", result="PASS",
            observed_at=NOW, next_stage=5, public_note="Ready",
            private_evidence={}, dna_digest_after=DNA,
        )
    assert caught.value.code == "INVALID_HAVEN_TRANSITION"


def test_all_human_labels_are_backed_by_exactly_five_mutable_machine_states():
    assert set(living.RELATIONSHIP_LABELS) == set(range(1, 6))
    assert set(living.RECOGNITION_LABELS) == set(range(1, 6))
    assert set(living.HAVEN_LABELS) == set(range(1, 6))
    assert set(living.HEALTH_LABELS) == set(range(1, 6))
    assert 0 not in living.RELATIONSHIP_LABELS

