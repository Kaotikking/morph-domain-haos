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


def test_private_serein_founders_do_not_block_public_starter():
    ledger = empty_ledger()
    for founder in ("EMBER", "BREEZE", "SENTINEL", "PULSE"):
        ledger.data["morphs"][founder.lower()] = {
            "morph_id": founder.lower(), "founder_id": founder,
            "device_birth_lineage": f"serein-lineage:v1:{founder.lower()}",
        }
    ledger.data["morphs"]["dustdevil"] = {
        "morph_id": "dustdevil", "founder_id": "DESCENDANT",
        "device_birth_lineage": "nursery-lineage:dustdevil",
        "source_frame": "haos-nursery",
    }
    result = origin.create_starter(
        ledger, request(starter="L1-03"), datetime(2026, 9, 9, 22, 0, tzinfo=UTC)
    )
    assert result["state"] == "STARTER_EGG_CREATED"
    assert result["private_founders_changed"] is False
    assert len(ledger.data["morphs"]) == 6


def test_unattributed_descendant_cannot_bypass_import_suppression():
    ledger = empty_ledger()
    ledger.data["morphs"]["unknown"] = {
        "morph_id": "unknown", "founder_id": "DESCENDANT",
        "device_birth_lineage": "external-lineage:unknown", "source_frame": "unknown",
    }
    with pytest.raises(transfer.TransferError) as denied:
        origin.create_starter(ledger, request(), datetime(2026, 9, 9, 22, 0, tzinfo=UTC))
    assert denied.value.code == "IMPORT_SUPPRESSES_STARTER"


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


def test_hatch_reveals_one_stable_pool_a_name_and_preserves_identity():
    ledger = empty_ledger()
    born = datetime(2026, 9, 9, 22, 0, tzinfo=UTC)
    created = origin.create_starter(ledger, request(starter="L1-04"), born)
    morph_id = created["morph_id"]
    before = deepcopy(ledger.data["morphs"][morph_id])
    hatch_request = {"schema": origin.ORIGIN_SCHEMA, "event_id": "hatch-water-1", "morph_id": morph_id}
    first = origin.hatch_starter(ledger, hatch_request, datetime(2026, 9, 12, 22, 0, tzinfo=UTC))
    assert first["state"] == "HATCHED"
    assert first["element"] == "WATER"
    assert first["display_name"] in origin.hatch_name.__globals__["pool"]("WATER", "A")
    assert origin.hatch_starter(ledger, hatch_request, datetime(2026, 9, 12, 22, 1, tzinfo=UTC)) == first
    after = ledger.data["morphs"][morph_id]
    for field in ("morph_id", "founder_id", "device_birth_lineage", "generation", "genome", "genome_sha256"):
        assert after[field] == before[field]
    assert after["presentation"]["display_name"] == first["display_name"]
    assert after["snapshot"]["payload"]["morph_core"]["platform"]["embodiment"]["body_class"] == "morph-juvenile"


def test_hatch_rejects_changed_replay_and_second_hatch():
    ledger = empty_ledger()
    created = origin.create_starter(ledger, request(starter="L1-01"), datetime(2026, 9, 9, 22, 0, tzinfo=UTC))
    req = {"schema": origin.ORIGIN_SCHEMA, "event_id": "hatch-fire-1", "morph_id": created["morph_id"]}
    origin.hatch_starter(ledger, req, datetime(2026, 9, 12, 22, 0, tzinfo=UTC))
    with pytest.raises(transfer.TransferError) as changed:
        origin.hatch_starter(ledger, {**req, "morph_id": "other"}, datetime(2026, 9, 12, 22, 1, tzinfo=UTC))
    assert changed.value.code == "REPLAY_CONFLICT"
    with pytest.raises(transfer.TransferError) as second:
        origin.hatch_starter(ledger, {**req, "event_id": "hatch-fire-2"}, datetime(2026, 9, 12, 22, 1, tzinfo=UTC))
    assert second.value.code == "ALREADY_HATCHED"

