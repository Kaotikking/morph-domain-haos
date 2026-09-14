"""Local-only Gardens game, care, and authority proof."""

from copy import deepcopy
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import asyncio

import pytest

from test_haos_morph_habitat import hosted_v3, habitat, transfer


NOW = datetime(2026, 9, 13, 12, tzinfo=UTC)


def garden():
    ledger = hosted_v3(NOW)
    habitat.place_morph(ledger, {"schema": habitat.HABITAT_SCHEMA,
                                "event_id": "to-gardens", "morph_id": "pulse",
                                "place": "SEREIN_GARDENS"}, NOW)
    return ledger


def start(ledger, game, game_id):
    return habitat.start_garden_game(ledger, {
        "schema": habitat.HABITAT_SCHEMA, "game_id": game_id,
        "morph_id": "pulse", "operator_id": "operator-1", "game": game,
    }, NOW)


def play(ledger, game_id, move_id, choice):
    return habitat.play_garden_game(ledger, {
        "schema": habitat.HABITAT_SCHEMA, "game_id": game_id,
        "morph_id": "pulse", "operator_id": "operator-1",
        "move_id": move_id, "choice": choice,
    }, NOW)


def test_matching_has_eight_pairs_no_wildcard_and_one_reward():
    ledger = garden()
    initial = habitat.habitat_status(ledger, "pulse", NOW)
    state = start(ledger, "MATCHING", "match-1")
    assert len(state["board"]) == 16 and all(tile is None for tile in state["board"])
    session = ledger.data["morphs"]["pulse"]["habitat"]["games"]["sessions"]["match-1"]
    assert sorted(session["secret"]) == [n for n in range(8) for _ in range(2)]
    pairs = [[i for i, tile in enumerate(session["secret"]) if tile == n] for n in range(8)]
    for index, pair in enumerate(pairs):
        result = play(ledger, "match-1", f"move-{index}", pair)
    assert result["finished"] and result["score"] == 8 and result["rewarded"]
    after = habitat.habitat_status(ledger, "pulse", NOW)
    assert after["life"]["play_q8"] == min(255, initial["life"]["play_q8"] + 12)
    assert after["social"]["edges"] == {}
    before_digest = after["snapshot_digest"]
    assert play(ledger, "match-1", "move-7", pairs[7]) == result
    assert habitat.habitat_status(ledger, "pulse", NOW)["snapshot_digest"] == before_digest


def test_hand_and_pattern_finish_without_farming_care():
    ledger = garden()
    start(ledger, "WHICH_HAND", "hand-1")
    hand = ledger.data["morphs"]["pulse"]["habitat"]["games"]["sessions"]["hand-1"]
    for index, target in enumerate(hand["secret"]):
        result = play(ledger, "hand-1", f"hand-{index}", target)
    assert result["finished"] and result["score"] == 5 and result["rewarded"]
    first_digest = habitat.habitat_status(ledger, "pulse", NOW)["snapshot_digest"]
    start(ledger, "FOLLOW_PATTERN", "pattern-1")
    pattern = ledger.data["morphs"]["pulse"]["habitat"]["games"]["sessions"]["pattern-1"]
    for index, sequence in enumerate(pattern["secret"]):
        result = play(ledger, "pattern-1", f"pattern-{index}", sequence)
    assert result["finished"] and result["score"] == 3 and not result["rewarded"]
    assert habitat.habitat_status(ledger, "pulse", NOW)["snapshot_digest"] == first_digest


def test_all_wrong_hand_game_still_counts_as_shared_play_once():
    ledger = garden()
    before = habitat.habitat_status(ledger, "pulse", NOW)
    start(ledger, "WHICH_HAND", "all-wrong")
    session = ledger.data["morphs"]["pulse"]["habitat"]["games"]["sessions"]["all-wrong"]
    for index, target in enumerate(session["secret"]):
        result = play(ledger, "all-wrong", f"wrong-{index}", 1 - target)
    assert result["finished"] and result["score"] == 0 and result["rewarded"]
    after = habitat.habitat_status(ledger, "pulse", NOW)
    assert after["life"]["play_q8"] == min(255, before["life"]["play_q8"] + 12)
    assert after["life"]["attention_q8"] == min(255, before["life"]["attention_q8"] + 8)
    assert after["social"]["edges"] == {}
    assert any(row["type"] == "GAME_COMPLETED" and row["score"] == 0
               for row in ledger.data["morphs"]["pulse"]["habitat"]["history"])
    digest = after["snapshot_digest"]
    assert play(ledger, "all-wrong", "wrong-4", 1 - session["secret"][4]) == result
    assert habitat.habitat_status(ledger, "pulse", NOW)["snapshot_digest"] == digest


def test_gardens_and_operator_binding_fail_closed():
    ledger = hosted_v3(NOW)
    with pytest.raises(transfer.TransferError) as err:
        start(ledger, "MATCHING", "bad-place")
    assert err.value.code == "GARDENS_REQUIRED"
    ledger = garden()
    start(ledger, "WHICH_HAND", "hand-2")
    with pytest.raises(transfer.TransferError) as err:
        habitat.play_garden_game(ledger, {"schema": habitat.HABITAT_SCHEMA,
            "game_id": "hand-2", "morph_id": "pulse", "operator_id": "other",
            "move_id": "wrong-operator", "choice": 0}, NOW)
    assert err.value.code == "GAME_NOT_FOUND"
    ledger.data["morphs"]["pulse"]["authority"] = "ANDROID"
    with pytest.raises(transfer.TransferError) as err:
        play(ledger, "hand-2", "wrong-owner", 0)
    assert err.value.code == "AUTHORITY_CONFLICT"


def test_game_replays_after_restart_without_losing_state():
    ledger = garden()
    start(ledger, "WHICH_HAND", "hand-3")
    first = play(ledger, "hand-3", "turn-1", 0)
    restarted = transfer.MorphTransferLedger(deepcopy(ledger.data))
    assert play(restarted, "hand-3", "turn-1", 0) == first
    assert restarted.data["morphs"]["pulse"]["habitat"]["games"]["sessions"]["hand-3"]["turn"] == 1
    with pytest.raises(transfer.TransferError) as err:
        play(restarted, "hand-3", "turn-1", 1)
    assert err.value.code == "INVALID_MOVE"


def test_stale_unfinished_game_expires_without_reward_or_lockout():
    ledger = garden()
    start(ledger, "MATCHING", "stale-game")
    later = NOW + timedelta(minutes=16)
    started = habitat.start_garden_game(ledger, {"schema": habitat.HABITAT_SCHEMA,
        "game_id": "next-game", "morph_id": "pulse", "operator_id": "operator-1",
        "game": "WHICH_HAND"}, later)
    assert started["game"] == "WHICH_HAND"
    stale = ledger.data["morphs"]["pulse"]["habitat"]["games"]["sessions"]["stale-game"]
    assert stale["expired"] and not stale["rewarded"]
    with pytest.raises(transfer.TransferError) as err:
        habitat.play_garden_game(ledger, {"schema": habitat.HABITAT_SCHEMA,
            "game_id": "stale-game", "morph_id": "pulse", "operator_id": "operator-1",
            "move_id": "too-late", "choice": [0, 1]}, later)
    assert err.value.code == "GAME_EXPIRED"


def test_http_game_identity_comes_from_authenticated_haos_user():
    class Manager:
        async def handle_habitat(self, action, body):
            assert action == "game-start"
            assert body["operator_id"] == "haos-user-1"
            return {"game_id": body["game_id"]}

    class Request(dict):
        def __init__(self, body):
            super().__init__({"hass_user": SimpleNamespace(is_admin=True, id="haos-user-1")})
            self.app = {"hass": SimpleNamespace(data={transfer.DATA_KEY: Manager()})}
            self.body = body

        async def json(self):
            return self.body

    view = habitat.MorphHabitatView()
    view.json = lambda body, status_code=200: (status_code, body)
    valid = {"schema": habitat.HABITAT_SCHEMA, "game_id": "g1",
             "morph_id": "pulse", "game": "MATCHING"}
    status, result = asyncio.run(view.post(Request(valid), "game-start"))
    assert status == 200 and result["result"]["game_id"] == "g1"
    status, result = asyncio.run(view.post(Request({**valid, "operator_id": "forged"}), "game-start"))
    assert status == 400 and result["error"]["code"] == "INVALID_REQUEST"
