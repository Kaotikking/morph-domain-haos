"""Local source-only proof for the HAOS-owned QOL interaction loop."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from importlib import import_module
import pytest

from test_haos_morph_habitat import hosted_v3, habitat, transfer


def pair_ledger(now):
    ledger = hosted_v3(now)
    first = ledger.data["morphs"]["pulse"]
    second = deepcopy(first)
    second["morph_id"] = "ember"
    second["snapshot"]["payload"]["morph_core"]["identity"]["morph_id"] = "ember"
    transfer.refresh_snapshot(second)
    ledger.data["morphs"]["ember"] = second
    return ledger


def test_horizon_encounters_build_mutual_familiarity_without_double_counting():
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    ledger = pair_ledger(now)
    assert habitat.run_social_reflexes(ledger, now)
    first = habitat.habitat_status(ledger, "pulse", now)["social"]
    assert first["edges"]["ember"]["state"] == "AWARE"
    assert first["edges"]["ember"]["evidence_count"] == 1
    assert not habitat.run_social_reflexes(ledger, now)


def test_horizon_resource_visits_are_frequent_without_repeating_social_meetings():
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    ledger = pair_ledger(now)
    assert habitat.run_social_reflexes(ledger, now)
    assert not habitat.run_social_reflexes(ledger, now)
    later = now + timedelta(minutes=5)
    assert habitat.run_social_reflexes(ledger, later)
    first = habitat.habitat_status(ledger, "pulse", later)
    assert first["social"]["edges"]["ember"]["evidence_count"] == 1
    assert first["social"]["last_activity"]["kind"] != "SHARED_PLAY"
    assert not habitat.run_social_reflexes(ledger, later)
    assert habitat.habitat_status(ledger, "pulse", now)["social"]["edges"]["ember"]["evidence_count"] == 1
    for hours in (2, 4):
        assert habitat.run_social_reflexes(ledger, now + timedelta(hours=hours))
    left = habitat.habitat_status(ledger, "pulse", now)["social"]
    right = habitat.habitat_status(ledger, "ember", now)["social"]
    assert left["edges"]["ember"]["state"] == "FAMILIAR"
    assert right["edges"]["pulse"]["state"] == "FAMILIAR"
    assert left["edges"]["ember"]["evidence_count"] == 3
    assert right["edges"]["pulse"]["evidence_count"] == 3


def test_restart_replay_preserves_identity_and_does_not_mutate_portable_life():
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    ledger = pair_ledger(now)
    before = {morph_id: (morph["generation"], morph["snapshot_digest"], morph["authority"],
                         morph["snapshot"]["payload"]["play_q8"])
              for morph_id, morph in ledger.data["morphs"].items()}
    assert habitat.run_social_reflexes(ledger, now)
    restarted = transfer.MorphTransferLedger(deepcopy(ledger.data))
    assert not habitat.run_social_reflexes(restarted, now)
    for morph_id, morph in restarted.data["morphs"].items():
        assert (morph["generation"], morph["authority"]) == (before[morph_id][0], before[morph_id][2])
        assert morph["snapshot_digest"] != before[morph_id][1]
        assert morph["snapshot"]["payload"]["play_q8"] >= before[morph_id][3]
    assert habitat.habitat_status(restarted, "pulse", now)["social"]["edges"]["ember"]["evidence_count"] == 1


def test_corrupt_directional_evidence_fails_closed():
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    ledger = pair_ledger(now)
    first = ledger.data["morphs"]["pulse"]
    habitat.habitat_status(ledger, "pulse", now)
    first["habitat"]["social"]["edges"]["ember"] = {
        "schema": "wrong", "subject_id": "pulse", "object_id": "ember",
        "state": "FAMILIAR", "evidence_count": 10,
    }
    habitat.run_social_reflexes(ledger, now)
    assert habitat.habitat_status(ledger, "ember", now)["social"]["edges"] == {}
    assert first["habitat"]["social"]["edges"]["ember"]["schema"] == "wrong"
    assert not any(row["type"] == "SOCIAL_INTERACTION" for row in first["habitat"]["history"])


def test_gardens_deepens_only_an_existing_mutual_relationship():
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    ledger = pair_ledger(now)
    for hours in (0, 2, 4):
        habitat.run_social_reflexes(ledger, now + timedelta(hours=hours))
    later = now + timedelta(hours=6)
    for morph_id in ("pulse", "ember"):
        habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA,
                                      "event_id": f"garden:{morph_id}",
                                      "morph_id": morph_id, "place": "SEREIN_GARDENS"}, later)
    for hours in (6, 8, 10):
        assert habitat.run_social_reflexes(ledger, now + timedelta(hours=hours))
    assert habitat.habitat_status(ledger, "pulse", later)["social"]["edges"]["ember"]["state"] == "BONDED"


def test_egg_and_remote_morph_never_acquire_social_evidence():
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    ledger = pair_ledger(now)
    ledger.data["morphs"]["ember"]["snapshot"]["payload"]["morph_core"]["embodiment"]["body_class"] = "morph-egg"
    assert habitat.run_social_reflexes(ledger, now)
    assert habitat.habitat_status(ledger, "pulse", now)["social"]["edges"] == {}
    assert habitat.habitat_status(ledger, "ember", now)["social"]["edges"] == {}
    assert not habitat.run_social_reflexes(ledger, now)
    ledger.data["morphs"]["ember"]["authority"] = "ANDROID"
    assert not habitat.run_social_reflexes(ledger, now)


def test_horizon_low_need_selects_real_care_not_just_a_log_entry():
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    ledger = hosted_v3(now)
    morph = ledger.data["morphs"]["pulse"]
    morph["snapshot"]["payload"]["food_q8"] = 20
    morph["snapshot"]["payload"]["morph_core"]["state"]["needs_q8"]["food"] = 20
    transfer.refresh_snapshot(morph)
    before = morph["snapshot_digest"]
    assert habitat.run_social_reflexes(ledger, now)
    status = habitat.habitat_status(ledger, "pulse", now)
    assert status["life"]["food_q8"] == 102
    assert status["care_levels"]["food"] == 2
    assert status["social"]["last_activity"]["kind"] == "EAT"
    assert status["snapshot_digest"] != before
    call = status["life_call"]["recent"][-1]
    assert call["schema"] == "serein.morph-life-call.v1"
    assert call["need_class"] == "EAT"
    assert call["preferred_channel"] == "MORPH_LOCAL"
    assert call["state"] == "RESOLVED"
    assert call["resolution"]["resolver"] == "ENVIRONMENT"
    assert status["life_call"]["active"] is None
    assert status["life_call"]["presentation_policy"] == "DEVICE_DECIDES"
    assert not habitat.run_social_reflexes(ledger, now)
    assert habitat.habitat_status(ledger, "pulse", now)["life"]["food_q8"] == 102


def test_horizon_exploration_has_bounded_real_effect_and_is_replay_safe():
    now = datetime(2026, 9, 13, 12, 30, tzinfo=UTC)
    ledger = hosted_v3(now)
    morph = ledger.data["morphs"]["pulse"]
    payload = morph["snapshot"]["payload"]
    for field in ("food_q8", "water_q8", "rest_q8", "play_q8"):
        payload[field] = 255
    before_attention = payload["attention_q8"]
    before_arousal = payload["arousal_q8"]
    assert habitat.run_social_reflexes(ledger, now)
    status = habitat.habitat_status(ledger, "pulse", now)
    assert status["social"]["last_activity"]["kind"] == "EXPLORE"
    assert habitat.care_level(status["life"]["attention_q8"]) == min(
        5, habitat.care_level(before_attention) + 1)
    assert status["life"]["arousal_q8"] == min(255, before_arousal + 4)
    assert status["life"]["memories"][-1]["code"] == "NOVEL"
    assert not habitat.run_social_reflexes(transfer.MorphTransferLedger(deepcopy(ledger.data)), now)


def test_low_need_morph_does_not_socialize_instead_of_self_care():
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    ledger = pair_ledger(now)
    ledger.data["morphs"]["pulse"]["snapshot"]["payload"]["water_q8"] = 12
    ledger.data["morphs"]["pulse"]["snapshot"]["payload"]["morph_core"]["state"]["needs_q8"]["water"] = 12
    transfer.refresh_snapshot(ledger.data["morphs"]["pulse"])
    assert habitat.run_social_reflexes(ledger, now)
    pulse = habitat.habitat_status(ledger, "pulse", now)
    ember = habitat.habitat_status(ledger, "ember", now)
    assert pulse["life"]["water_q8"] == 102
    assert pulse["care_levels"]["water"] == 2
    assert pulse["social"]["last_activity"]["kind"] == "DRINK"
    assert pulse["social"]["edges"] == {}
    assert ember["social"]["edges"] == {}


@pytest.mark.parametrize("low_field,activity,changed_field", [
    ("food", "EAT", "food_q8"),
    ("water", "DRINK", "water_q8"),
    ("rest", "REST", "rest_q8"),
    ("play", "PLAY", "play_q8"),
])
def test_every_horizon_need_activity_changes_the_matching_life_field(
    low_field, activity, changed_field
):
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    ledger = hosted_v3(now)
    morph = ledger.data["morphs"]["pulse"]
    payload = morph["snapshot"]["payload"]
    payload[changed_field] = 10
    payload["morph_core"]["state"]["needs_q8"][low_field] = 10
    transfer.refresh_snapshot(morph)
    assert habitat.run_social_reflexes(ledger, now)
    status = habitat.habitat_status(ledger, "pulse", now)
    assert status["social"]["last_activity"]["kind"] == activity
    assert status["life"][changed_field] > 10
    reloaded = transfer.MorphTransferLedger(deepcopy(ledger.data))
    assert not habitat.run_social_reflexes(reloaded, now)
    assert habitat.habitat_status(reloaded, "pulse", now)["life"][changed_field] == status["life"][changed_field]


def test_lineage_is_an_encounter_preference_not_an_instant_relationship():
    engine = import_module("serein_gateway_test._vendor.morph_engine.habitat")
    now = datetime(2026, 9, 13, 12, tzinfo=UTC)
    ledger = pair_ledger(now)
    pulse = ledger.data["morphs"]["pulse"]
    ember = ledger.data["morphs"]["ember"]
    assert engine._kinship_score(pulse, ember) == 1  # same known founder line
    ember["snapshot"]["payload"]["morph_core"]["identity"]["parent_ids"] = ["pulse"]
    assert engine._kinship_score(pulse, ember) == 3  # direct parent/child
    ember["snapshot"]["payload"]["morph_core"]["identity"]["parent_ids"] = []
    ember["snapshot"]["payload"]["morph_core"]["identity"]["founder_lineage"] = "founder:other"
    assert engine._kinship_score(pulse, ember) == 0
    assert habitat.habitat_status(ledger, "pulse", now)["social"]["edges"] == {}

