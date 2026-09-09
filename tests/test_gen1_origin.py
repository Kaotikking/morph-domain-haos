from copy import deepcopy
from datetime import UTC, datetime
import importlib.util
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "custom_components/morph_domain"
PKG = "gen1_origin_test"
pkg = types.ModuleType(PKG)
pkg.__path__ = [str(PACKAGE)]
sys.modules.setdefault(PKG, pkg)
vendor = types.ModuleType(f"{PKG}._vendor")
vendor.__path__ = [str(PACKAGE / "_vendor")]
sys.modules.setdefault(f"{PKG}._vendor", vendor)
sdk = types.ModuleType(f"{PKG}._vendor.morph_sdk")
sdk.__path__ = [str(PACKAGE / "_vendor/morph_sdk")]
sys.modules.setdefault(f"{PKG}._vendor.morph_sdk", sdk)


def load(name):
    dotted = name.replace("/", ".")
    full = f"{PKG}.{dotted}"
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(full, PACKAGE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[full] = module
    spec.loader.exec_module(module)
    return module


transfer = load("_vendor/morph_sdk/transfer")
origin = load("_vendor/morph_sdk/gen1_origin")
core_contract = load("_vendor/morph_sdk/morph_core")


def request(starter="L1-02", event="starter-claim-1"):
    return {"schema": origin.ORIGIN_SCHEMA, "event_id": event,
            "starter_id": starter}


def empty_ledger():
    ledger = transfer.MorphTransferLedger.empty()
    ledger.data["installation_id"] = "family-haos-beta"
    return ledger


def test_real_starter_birth_is_one_atomic_nursery_morph():
    ledger = empty_ledger()
    now = datetime(2026, 9, 9, 22, 0, tzinfo=UTC)
    result = origin.create_starter(ledger, request(), now)
    assert result["state"] == "STARTER_EGG_CREATED"
    assert result["starter_id"] == "L1-02"
    assert result["place"] == "NURSERY"
    assert result["parents"] == []
    assert result["private_founders_changed"] is False
    assert len(ledger.data["morphs"]) == 1
    morph = ledger.data["morphs"][result["morph_id"]]
    core = core_contract.validate_nine_core(morph["snapshot"]["payload"]["morph_core"])
    assert core["root"]["identity"]["founder_lineage"] == "l1-02"
    assert core["root"]["identity"]["primitive_element"] == "AIR"
    assert core["root"]["identity"]["parent_ids"] == []
    assert core["root"]["identity"]["generation"] == 0
    assert core["cloud"]["place"] == "NURSERY"
    assert core["memory"]["chronicle"]["events"][0]["kind"] == "starter-birth"
    assert core["knowledge"]["learned"] == {
        "E-01": "HORIZON_UNDISCOVERED", "E-02": "CHOSEN",
        "E-03": "HORIZON_UNDISCOVERED", "E-04": "HORIZON_UNDISCOVERED",
    }


def test_exact_retry_is_idempotent_and_changed_replay_fails():
    ledger = empty_ledger()
    now = datetime(2026, 9, 9, 22, 0, tzinfo=UTC)
    first = origin.create_starter(ledger, request(), now)
    assert origin.create_starter(ledger, request(), now) == first
    with pytest.raises(transfer.TransferError, match="payload changed") as err:
        origin.create_starter(ledger, request(starter="L1-01"), now)
    assert err.value.code == "REPLAY_CONFLICT"


def test_second_starter_and_existing_morph_fail_closed():
    now = datetime(2026, 9, 9, 22, 0, tzinfo=UTC)
    ledger = empty_ledger()
    origin.create_starter(ledger, request(), now)
    with pytest.raises(transfer.TransferError) as second:
        origin.create_starter(ledger, request(starter="L1-01", event="starter-claim-2"), now)
    assert second.value.code == "STARTER_ALREADY_CLAIMED"

    imported = empty_ledger()
    imported.data["morphs"]["existing"] = {"morph_id": "existing"}
    with pytest.raises(transfer.TransferError) as suppressed:
        origin.create_starter(imported, request(), now)
    assert suppressed.value.code == "IMPORT_SUPPRESSES_STARTER"


def test_status_exposes_options_without_creating_more_morphs():
    ledger = empty_ledger()
    before = deepcopy(ledger.data)
    available = origin.starter_status(ledger)
    assert available["state"] == "AVAILABLE"
    assert len(available["options"]) == 4
    assert ledger.data == before
    result = origin.create_starter(ledger, request(starter="L1-04"), datetime(2026, 9, 9, 22, 0, tzinfo=UTC))
    status = origin.starter_status(ledger)
    assert status["state"] == "CLAIMED"
    assert status["morph_id"] == result["morph_id"]
    assert sum(row["horizon_state"] == "CHOSEN" for row in status["options"]) == 1
    assert sum(row["horizon_state"] == "UNDISCOVERED" for row in status["options"]) == 3

