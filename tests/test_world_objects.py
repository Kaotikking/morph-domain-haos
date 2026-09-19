"""Local six-Morph Pet World model proof; not installed in HAOS."""

import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).parents[1] / "custom_components/morph_domain/_vendor/morph_engine/world_objects.py"
SPEC = importlib.util.spec_from_file_location("local_world_objects", SOURCE)
world = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(world)
OBJECTS, WorldObjectError = world.OBJECTS, world.WorldObjectError
choose_object, interact, new_history = world.choose_object, world.interact, world.new_history


MORPHS = ("pulse", "ember", "breeze", "sentinel", "dustdevil", "water-starter")


def population():
    return {morph_id: new_history(morph_id) for morph_id in MORPHS}


def test_world_event_detail_is_bounded_but_lifetime_counts_survive():
    rows = {"pulse": new_history("pulse")}
    for index in range(world.WORLD_EVENT_CAPACITY + 7):
        interact(rows, event_id=f"event-{index}", place="HORIZON",
                 object_id="spring-pool", participants=("pulse",),
                 willing={"pulse": True})
    assert len(rows["pulse"]["events"]) == world.WORLD_EVENT_CAPACITY
    assert "event-0" not in rows["pulse"]["events"]
    assert f"event-{world.WORLD_EVENT_CAPACITY + 6}" in rows["pulse"]["events"]
    assert rows["pulse"]["counts"]["spring-pool"] == world.WORLD_EVENT_CAPACITY + 7
    assert "spring-pool" in rows["pulse"]["preferences"]


def affinity(place, favored):
    return {item: 5 if item == favored else 1 for item in OBJECTS[place]}


def test_six_morphs_choose_distinct_shared_world_objects_and_keep_history():
    histories = population()
    favorites = ("rest-nook", "gathering-stone", "discovery-prism",
                 "walking-path", "rest-nook", "discovery-prism")
    for morph_id, favored in zip(MORPHS, favorites):
        chosen = choose_object("HORIZON", affinity("HORIZON", favored), histories[morph_id])
        assert chosen == favored
        for visit in range(3):
            result = interact(histories, event_id=f"{morph_id}:{visit}", place="HORIZON",
                              object_id=chosen, participants=(morph_id,), willing={morph_id: True})
            assert result["result"] == "ACCEPTED"
        assert histories[morph_id]["preferences"] == [favored]
    assert len({h["preferences"][0] for h in histories.values()}) == 4
    assert all(len(h["events"]) == 3 for h in histories.values())


def test_six_morphs_share_gardens_without_collapsing_individual_histories():
    histories = population()
    pairs = (("pulse", "ember", "play-orb"),
             ("breeze", "sentinel", "shared-chimes"),
             ("dustdevil", "water-starter", "quiet-pool"))
    for first, second, object_id in pairs:
        for visit in range(3):
            result = interact(histories, event_id=f"garden:{first}:{second}:{visit}",
                              place="SEREIN_GARDENS", object_id=object_id,
                              participants=(first, second), willing={first: True, second: True})
            assert result["credited"] == [first, second]
        assert histories[first]["preferences"] == [object_id]
        assert histories[second]["preferences"] == [object_id]
        assert histories[first]["events"] == histories[second]["events"]
    assert len({tuple(h["preferences"]) for h in histories.values()}) == 3


def test_horizon_allows_solo_or_mutual_but_gardens_requires_two_willing_sides():
    histories = population()
    assert interact(histories, event_id="solo", place="HORIZON", object_id="walking-path",
                    participants=("breeze",), willing={"breeze": True})["result"] == "ACCEPTED"
    assert interact(histories, event_id="pair", place="HORIZON", object_id="gathering-stone",
                    participants=("pulse", "ember"), willing={"pulse": True, "ember": True})["credited"] == ["pulse", "ember"]
    with pytest.raises(WorldObjectError, match="two participants"):
        interact(histories, event_id="garden-solo", place="SEREIN_GARDENS", object_id="play-orb",
                 participants=("pulse",), willing={"pulse": True})
    declined = interact(histories, event_id="declined", place="SEREIN_GARDENS",
                        object_id="shared-chimes", participants=("pulse", "sentinel"),
                        willing={"pulse": True, "sentinel": False})
    assert declined == {"event_id": "declined", "result": "DECLINED", "credited": []}
    assert "declined" not in histories["pulse"]["events"]
    accepted = interact(histories, event_id="garden", place="SEREIN_GARDENS",
                        object_id="shared-chimes", participants=("pulse", "sentinel"),
                        willing={"pulse": True, "sentinel": True})
    assert accepted["credited"] == ["pulse", "sentinel"]
    assert histories["pulse"]["events"]["garden"] == histories["sentinel"]["events"]["garden"]


def test_operator_garden_play_and_replay_do_not_fabricate_preference():
    histories = population()
    args = dict(event_id="operator-play", place="SEREIN_GARDENS", object_id="pattern-tiles",
                participants=("pulse", "OPERATOR"), willing={"pulse": True, "OPERATOR": True})
    assert interact(histories, **args)["result"] == "ACCEPTED"
    assert histories["pulse"]["counts"] == {"pattern-tiles": 1}
    assert histories["pulse"]["preferences"] == []
    assert interact(histories, **args)["result"] == "REPLAY"
    assert histories["pulse"]["counts"] == {"pattern-tiles": 1}
    with pytest.raises(WorldObjectError, match="replay payload changed"):
        interact(histories, **{**args, "object_id": "play-orb"})


def test_no_affinity_source_is_not_a_fake_personality():
    histories = population()
    with pytest.raises(WorldObjectError, match="complete bounded affinity"):
        choose_object("HORIZON", {"rest-nook": 5}, histories["pulse"])
    with pytest.raises(WorldObjectError, match="no willing object choice"):
        choose_object("HORIZON", {item: 0 for item in OBJECTS["HORIZON"]}, histories["pulse"])

