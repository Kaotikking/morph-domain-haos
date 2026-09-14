from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components/morph_domain/_vendor"))

from morph_sdk.dna_v1 import SOCIAL_SCHEMA
from morph_sdk.ump_world import choose_horizon_activity, decide_pair


def morph(morph_id, place="HORIZON", phase="MATURE"):
    return {
        "morph_id": morph_id, "authority": "HAOS", "place": place,
        "phase": phase, "needs": {"food": 200, "water": 200, "rest": 200, "play": 200},
    }


def edge(subject, object_id, state="FAMILIAR"):
    return {
        "schema": SOCIAL_SCHEMA, "subject_id": subject, "object_id": object_id,
        "state": state, "evidence_count": 3,
    }


def pair(a, b, **kwargs):
    return decide_pair(a, b, edge(a["morph_id"], b["morph_id"]),
                       edge(b["morph_id"], a["morph_id"]), **kwargs)


def test_horizon_needs_are_deterministic_and_bounded():
    a = morph("a")
    assert choose_horizon_activity(a)["activity"] == "EXPLORE"
    a["needs"]["water"] = 40
    assert choose_horizon_activity(a)["activity"] == "DRINK"
    a["needs"]["water"] = -1
    assert choose_horizon_activity(a)["decision"] == "UNKNOWN"


def test_horizon_healthy_activity_varies_without_restart_reroll():
    a = morph("six-morph-soak")
    choices = [choose_horizon_activity(a, window=window)["activity"] for window in range(32)]
    assert len(set(choices)) >= 3
    assert set(choices).issubset({"EAT", "DRINK", "REST", "PLAY", "EXPLORE"})
    assert choices == [choose_horizon_activity(a, window=window)["activity"] for window in range(32)]
    a["needs"]["water"] = 40
    assert all(choose_horizon_activity(a, window=window)["activity"] == "DRINK"
               for window in range(32))


def test_colocation_does_not_make_friends():
    a, b = morph("a"), morph("b")
    assert pair(a, b, reciprocal_event=False)["decision"] == "UNKNOWN"
    assert pair(a, b, reciprocal_event=True)["decision"] == "GARDENS_READY"
    weak = decide_pair(a, b, edge("a", "b", "FAMILIAR"),
                       edge("b", "a", "AWARE"), reciprocal_event=True)
    assert weak["decision"] == "ENCOUNTER"


def test_wrong_direction_and_remote_authority_fail_closed():
    a, b = morph("a"), morph("b")
    wrong = decide_pair(a, b, edge("b", "a"), edge("a", "b"), reciprocal_event=True)
    assert wrong["decision"] == "UNKNOWN"
    b["authority"] = "ESP32"
    assert pair(a, b, reciprocal_event=True)["decision"] == "UNKNOWN"


def test_gardens_requires_reciprocal_evidence():
    a, b = morph("a", "SEREIN_GARDENS"), morph("b", "SEREIN_GARDENS")
    assert pair(a, b, reciprocal_event=False)["decision"] == "RECOVER"
    assert pair(a, b, reciprocal_event=True)["decision"] == "GARDENS_READY"


def test_nursery_never_grants_breeding_on_ump_alone():
    a, b = morph("a", "NURSERY"), morph("b", "NURSERY")
    base = dict(reciprocal_event=True, consent_admitted=True,
                cooldown_clear=True, nursery_capacity=1, lineage_compatible=True)
    assert pair(a, b, **base)["decision"] == "NURSERY_READY"
    for key, value in (("consent_admitted", False), ("cooldown_clear", False),
                       ("nursery_capacity", 0), ("lineage_compatible", False)):
        params = dict(base, **{key: value})
        assert pair(a, b, **params)["decision"] != "NURSERY_READY"
    assert pair(a, b, **dict(base, lineage_compatible=None))["decision"] == "UNKNOWN"
    b["phase"] = "JUVENILE"
    assert pair(a, b, **base)["decision"] == "RECOVER"
