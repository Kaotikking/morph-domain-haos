from copy import deepcopy
from datetime import UTC, datetime

import pytest

from test_world_nine_core import aligned
from serein_gateway_test._vendor.morph_engine.battle import BATTLE_SCHEMA, history, preview, resolve
from serein_gateway_test._vendor.morph_sdk.transfer import TransferError

NOW = datetime(2026, 9, 20, 12, tzinfo=UTC)


def pair():
    ledger = aligned("pulse", "HORIZON")
    other = aligned("ember", "HORIZON")
    other.data["morphs"]["ember"]["snapshot"]["payload"]["morph_core"]["root"]["identity"]["primitive_element"] = "FIRE"
    ledger.data["morphs"].update(other.data["morphs"])
    return ledger


def request():
    return {"schema": BATTLE_SCHEMA, "battle_id": "spar-1", "first_morph_id": "pulse",
            "second_morph_id": "ember", "mode": "UNRANKED_SPARRING"}


def test_preview_is_read_only_and_exposes_four_canonical_move_tiers():
    ledger = pair()
    before = deepcopy(ledger.data)
    result = preview(ledger, "pulse", "ember", "spar-1")
    assert result["state"] == "READY"
    assert [m["tier"] for m in result["participants"][0]["moves"]] == ["STATUS", "SPEED", "POWER", "SUPER"]
    assert result["effects"] == {"custody": False, "dna": False, "injury": False, "rank": False}
    assert ledger.data == before


def test_spar_is_deterministic_idempotent_and_changes_no_morph_snapshot():
    ledger = pair()
    before = {k: v["snapshot_digest"] for k, v in ledger.data["morphs"].items()}
    first = resolve(ledger, request(), NOW)
    assert first["state"] == "COMPLETE" and first["mode"] == "UNRANKED_SPARRING"
    assert resolve(ledger, request(), NOW) == first
    assert {k: v["snapshot_digest"] for k, v in ledger.data["morphs"].items()} == before
    assert history(ledger)["battles"] == [first]


def test_beta_fails_closed_for_void_remote_egg_unknown_and_replay_mismatch():
    ledger = pair()
    ledger.data["morphs"]["pulse"]["habitat"]["place"] = "VOID"
    with pytest.raises(TransferError) as err:
        preview(ledger, "pulse", "ember", "x")
    assert err.value.code == "BATTLE_PLACE_REQUIRED"
    ledger = pair(); ledger.data["morphs"]["pulse"]["authority"] = "frame"
    with pytest.raises(TransferError) as err:
        preview(ledger, "pulse", "ember", "x")
    assert err.value.code == "HAOS_CUSTODY_REQUIRED"
    ledger = pair(); resolve(ledger, request(), NOW)
    changed = request(); changed["second_morph_id"] = "pulse"
    with pytest.raises(TransferError) as err:
        resolve(ledger, changed, NOW)
    assert err.value.code == "REPLAY_MISMATCH"

