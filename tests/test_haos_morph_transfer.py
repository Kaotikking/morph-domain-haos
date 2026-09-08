from copy import deepcopy
from datetime import UTC, datetime, timedelta
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).parents[1]
MODULE = ROOT / "custom_components/morph_domain/_vendor/morph_sdk/transfer.py"

for name in ("voluptuous", "homeassistant", "homeassistant.components", "homeassistant.components.http", "homeassistant.core", "homeassistant.helpers", "homeassistant.helpers.storage"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["voluptuous"].Invalid = ValueError
sys.modules["homeassistant.components.http"].HomeAssistantView = object
sys.modules["homeassistant.core"].HomeAssistant = object
sys.modules["homeassistant.helpers.storage"].Store = type("Store", (), {"__class_getitem__": classmethod(lambda cls, _: cls)})
spec = importlib.util.spec_from_file_location("morph_transfer", MODULE)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def snapshot():
    payload = {"saved_epoch_seconds": 1788549653, "behavior": "SETTLE", "arousal_q8": 128,
               "security_q8": 128, "curiosity_q8": 128, "social_q8": 128, "fatigue_q8": 0,
               "food_q8": 200, "water_q8": 200, "play_q8": 200, "rest_q8": 200,
               "attention_q8": 200, "memories": []}
    return {"schema": module.LIFE_SCHEMA, "payload": payload,
            "sha256": hashlib.sha256(canonical(payload).encode()).hexdigest()}


def offer(now, transfer="t1"):
    genome = "founder=PULSE\nbirth=1788549653\n"
    return {"schema": module.API_SCHEMA, "transfer_id": transfer, "morph_id": "pulse",
            "founder_id": "PULSE", "device_birth_lineage": "legacy-adoption:android-rooted-prime",
            "source_frame": "android-frame:opaque-app-identity", "target_frame": "HAOS",
            "generation": 1, "predecessor_generation": 0,
            "created_at": now.isoformat(), "expires_at": (now + timedelta(minutes=5)).isoformat(),
            "engine_version": module.ENGINE_VERSION, "genome": genome,
            "genome_sha256": hashlib.sha256(genome.encode()).hexdigest(), "snapshot": snapshot()}


def esp32_offer(now, transfer="spark-t1"):
    request = offer(now, transfer)
    request.update({
        "morph_id": "spark",
        "founder_id": "SPARK",
        "device_birth_lineage": "serein-lineage:v1:spark-fixture",
        "source_frame": "esp32-frame:v1:spark-fixture",
        "engine_version": module.ESPHOME_ENGINE_VERSION,
    })
    extension_payload = {
        "growth_q16": 4242,
        "development_q8": 153,
        "elemental_mastery_q16": {"AIR": 9123},
        "care_counts": {"feed": 2, "water": 3, "play": 4, "rest": 1},
        "world_location": 0,
    }
    payload = dict(request["snapshot"]["payload"])
    payload["engine_extension"] = {
        "schema": "serein.esphome.spark-life-extension.v1",
        "payload": extension_payload,
        "sha256": hashlib.sha256(canonical(extension_payload).encode()).hexdigest(),
    }
    request["snapshot"] = {
        "schema": module.PORTABLE_LIFE_SCHEMA,
        "payload": payload,
        "sha256": hashlib.sha256(canonical(payload).encode()).hexdigest(),
    }
    return request


def morph_core_offer(now, transfer="spark-core-t1"):
    request = esp32_offer(now, transfer)
    payload = request["snapshot"]["payload"]
    core_event = {"event_id": "spark.birth", "kind": "birth", "observed_at": now.isoformat(),
                  "source": "esp32-frame:v1:spark-fixture", "place": "HORIZON",
                  "frame": "esp32-frame:v1:spark-fixture", "evidence_digest": "1" * 64}
    request["snapshot"]["payload"]["morph_core"] = {
        "schema": "serein.morph-core.v1",
        "identity": {"morph_id": "spark", "founder_lineage": "founder:spark",
                     "device_birth_lineage": "serein-lineage:v1:spark-fixture",
                     "born_at": now.isoformat(), "generation": 0, "parent_ids": [],
                     "primitive_element": "AIR", "genome_version": "dnav1"},
        "life": {"growth_q16": 4242, "care_counts": {"play": 4}, "relationship_counts": {},
                 "journey_count": 1, "elemental_mastery_q16": {"air": 9123}},
        "state": {"place": "HORIZON", "authority": "REMOTE_ACTIVE",
                  "active_frame": "esp32-frame:v1:spark-fixture",
                  "needs_q8": {"attention": payload["attention_q8"], "energy": 255 - payload["fatigue_q8"],
                               "food": payload["food_q8"], "play": payload["play_q8"],
                               "rest": payload["rest_q8"], "water": payload["water_q8"]},
                  "mood": payload["behavior"].lower(), "expression": "breeze"},
        "embodiment": {"body_id": "spark-fixture", "body_class": "camera-frame",
                       "capabilities": ["camera", "display"]},
        "chronicle": {"schema": "serein.living-code-chronicle.v1", "events": [core_event]}}
    request["snapshot"]["schema"] = module.MORPH_CORE_LIFE_SCHEMA
    request["snapshot"]["sha256"] = hashlib.sha256(canonical(request["snapshot"]["payload"]).encode()).hexdigest()
    return request


def test_round_trip_single_authority_and_idempotency():
    now = datetime(2026, 9, 5, tzinfo=UTC)
    ledger = module.MorphTransferLedger.empty()
    prepared = ledger.prepare_inbound(offer(now), now)
    assert prepared["operation_state"] == "PREPARED" and prepared["authority"] == "android-frame:opaque-app-identity"
    assert ledger.prepare_inbound(offer(now), now) == prepared
    active = ledger.commit_inbound("t1", prepared["snapshot_digest"], now)
    assert active["operation_state"] == "ACTIVE_HAOS" and active["authority"] == "HAOS"
    assert active["generation"] == active["current_generation"] == 1
    assert active["snapshot_digest"] == active["current_snapshot_digest"]
    returned = ledger.prepare_return({"schema": module.API_SCHEMA, "return_id": "r1", "morph_id": "pulse",
        "target_frame": "android-frame:opaque-app-identity", "expires_at": (now + timedelta(minutes=5)).isoformat()}, now)
    assert returned["operation_state"] == "RETURN_PREPARED" and returned["authority"] == "FROZEN_FOR_RETURN"
    assert ledger.prepare_return({"schema": module.API_SCHEMA, "return_id": "r1", "morph_id": "pulse",
        "target_frame": "android-frame:opaque-app-identity", "expires_at": (now + timedelta(minutes=5)).isoformat()}, now)["operation_state"] == "RETURN_PREPARED"
    final = ledger.commit_return("r1", returned["snapshot_digest"], now)
    assert final["operation_state"] == "RETURNED_ANDROID" and final["authority"] == "android-frame:opaque-app-identity"
    assert ledger.status("t1")["authority"] == "android-frame:opaque-app-identity"
    try: ledger.commit_return("r1", "0" * 64, now)
    except module.TransferError as err: assert err.code == "DIGEST_MISMATCH"
    else: raise AssertionError("repeat return accepted wrong digest")


def test_duplicate_changed_payload_and_bad_digest_fail_closed():
    now = datetime(2026, 9, 5, tzinfo=UTC)
    ledger = module.MorphTransferLedger.empty()
    request = offer(now)
    ledger.prepare_inbound(request, now)
    changed = offer(now); changed["founder_id"] = "SPARK"
    try: ledger.prepare_inbound(changed, now)
    except module.TransferError as err: assert err.code == "REPLAY_CONFLICT"
    else: raise AssertionError("changed replay accepted")
    bad = offer(now, "t2"); bad["snapshot"]["sha256"] = "0" * 64
    try: ledger.prepare_inbound(bad, now)
    except module.TransferError as err: assert err.code == "DIGEST_MISMATCH"
    else: raise AssertionError("bad digest accepted")


def test_expired_wrong_target_and_unknown_engine_fail_closed():
    now = datetime(2026, 9, 5, tzinfo=UTC)
    cases = []
    expired = offer(now - timedelta(hours=1)); cases.append((expired, "EXPIRED"))
    wrong = offer(now, "t2"); wrong["target_frame"] = "OTHER"; cases.append((wrong, "INVALID_TARGET"))
    engine = offer(now, "t3"); engine["engine_version"] = "unknown"; cases.append((engine, "INCOMPATIBLE_ENGINE"))
    for request, code in cases:
        try: module.MorphTransferLedger.empty().prepare_inbound(request, now)
        except module.TransferError as err: assert err.code == code
        else: raise AssertionError(f"{code} case accepted")


def test_life_payload_must_match_android_codec_exactly():
    now = datetime(2026, 9, 5, tzinfo=UTC)
    cases = []
    missing = offer(now, "missing"); missing["snapshot"]["payload"].pop("water_q8"); cases.append(missing)
    bad_q8 = offer(now, "q8"); bad_q8["snapshot"]["payload"]["food_q8"] = 256; cases.append(bad_q8)
    bad_behavior = offer(now, "behavior"); bad_behavior["snapshot"]["payload"]["behavior"] = "IDLE"; cases.append(bad_behavior)
    too_many = offer(now, "memories"); too_many["snapshot"]["payload"]["memories"] = [
        {"code": "PLAY", "age_ms": 0, "weight": 1} for _ in range(9)]; cases.append(too_many)
    for request in cases:
        request["snapshot"]["sha256"] = hashlib.sha256(canonical(request["snapshot"]["payload"]).encode()).hexdigest()
        try: module.MorphTransferLedger.empty().prepare_inbound(request, now)
        except module.TransferError as err: assert err.code in {"INVALID_SCHEMA", "INVALID_LIFE_STATE"}
        else: raise AssertionError("invalid Android life payload accepted")


def test_generation_identity_and_commit_race_fail_closed():
    now = datetime(2026, 9, 5, tzinfo=UTC)
    ledger = module.MorphTransferLedger.empty()
    prepared = ledger.prepare_inbound(offer(now), now)
    # A concurrent authority change after prepare must be rechecked at commit.
    ledger.data["morphs"]["pulse"] = {
        "morph_id": "pulse", "founder_id": "PULSE",
        "device_birth_lineage": "legacy-adoption:android-rooted-prime",
        "generation": 0, "authority": "different-frame", "engine_state": "REMOTE_ACTIVE",
        "engine_version": module.ENGINE_VERSION, "snapshot": snapshot(), "genome": "founder=PULSE\nbirth=1788549653\n",
        "genome_sha256": offer(now)["genome_sha256"], "snapshot_digest": prepared["snapshot_digest"],
        "source_frame": "android-frame:opaque-app-identity", "committed_at": now.isoformat()}
    try: ledger.commit_inbound("t1", prepared["snapshot_digest"], now)
    except module.TransferError as err: assert err.code == "AUTHORITY_CONFLICT"
    else: raise AssertionError("commit ignored authority race")

    bad_generation = offer(now, "bad-generation"); bad_generation["generation"] = 2
    try: module.MorphTransferLedger.empty().prepare_inbound(bad_generation, now)
    except module.TransferError as err: assert err.code == "GENERATION_CONFLICT"
    else: raise AssertionError("non-successor generation accepted")


def test_expired_interrupted_return_recovers_haos_authority_after_restart():
    now = datetime(2026, 9, 5, tzinfo=UTC)
    ledger = module.MorphTransferLedger.empty()
    prepared = ledger.prepare_inbound(offer(now), now)
    ledger.commit_inbound("t1", prepared["snapshot_digest"], now)
    returned = ledger.prepare_return({"schema": module.API_SCHEMA, "return_id": "r-expired", "morph_id": "pulse",
        "target_frame": "android-frame:opaque-app-identity", "expires_at": (now + timedelta(seconds=1)).isoformat()}, now)
    assert returned["authority"] == "FROZEN_FOR_RETURN"
    restarted = module.MorphTransferLedger(json.loads(json.dumps(ledger.data)))
    assert restarted.reconcile_expired(now + timedelta(seconds=2))
    status = restarted.status("r-expired")
    assert status["operation_state"] == "RETURN_EXPIRED"
    assert status["authority"] == "HAOS" and status["morph_state"] == "ACTIVE_DEFERRED_TICK"


def test_esp32_portable_extension_survives_round_trip_unchanged():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = module.MorphTransferLedger.empty()
    request = esp32_offer(now)
    original_extension = json.loads(json.dumps(request["snapshot"]["payload"]["engine_extension"]))
    prepared = ledger.prepare_inbound(request, now)
    ledger.commit_inbound("spark-t1", prepared["snapshot_digest"], now)
    returned = ledger.prepare_return({
        "schema": module.API_SCHEMA,
        "return_id": "spark-r1",
        "morph_id": "spark",
        "target_frame": "esp32-frame:v1:spark-fixture",
        "expires_at": (now + timedelta(minutes=5)).isoformat(),
    }, now)
    assert returned["snapshot"]["payload"]["engine_extension"] == original_extension
    final = ledger.commit_return("spark-r1", returned["snapshot_digest"], now)
    assert final["authority"] == "esp32-frame:v1:spark-fixture"
    returned_extension = returned["snapshot"]["payload"]["engine_extension"]["payload"]
    assert returned_extension["growth_q16"] >= original_extension["payload"]["growth_q16"]
    assert returned_extension["elemental_mastery_q16"]["AIR"] >= original_extension["payload"]["elemental_mastery_q16"]["AIR"]


def test_esp32_extension_digest_and_legacy_schema_fail_closed():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    bad_digest = esp32_offer(now, "bad-extension")
    bad_digest["snapshot"]["payload"]["engine_extension"]["sha256"] = "0" * 64
    bad_digest["snapshot"]["sha256"] = hashlib.sha256(
        canonical(bad_digest["snapshot"]["payload"]).encode()).hexdigest()
    try:
        module.MorphTransferLedger.empty().prepare_inbound(bad_digest, now)
    except module.TransferError as err:
        assert err.code == "ENGINE_EXTENSION_DIGEST_MISMATCH"
    else:
        raise AssertionError("bad ESP32 extension digest accepted")

    legacy = esp32_offer(now, "legacy-schema")
    legacy["snapshot"] = snapshot()
    try:
        module.MorphTransferLedger.empty().prepare_inbound(legacy, now)
    except module.TransferError as err:
        assert err.code == "INCOMPATIBLE_LIFE_SCHEMA"
    else:
        raise AssertionError("ESP32 offer accepted lossy Android-only schema")


def test_morph_core_v3_is_bound_to_transfer_identity_and_survives_return():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = module.MorphTransferLedger.empty()
    request = morph_core_offer(now)
    prepared = ledger.prepare_inbound(request, now)
    ledger.commit_inbound("spark-core-t1", prepared["snapshot_digest"], now)
    returned = ledger.prepare_return({"schema": module.API_SCHEMA, "return_id": "spark-core-r1",
        "morph_id": "spark", "target_frame": "esp32-frame:v1:spark-fixture",
        "expires_at": (now + timedelta(minutes=5)).isoformat()}, now)
    returned_core = returned["snapshot"]["payload"]["morph_core"]
    original_core = request["snapshot"]["payload"]["morph_core"]
    assert module.core_identity(returned_core) == original_core["identity"]
    assert module.core_life(returned_core) == original_core["life"]
    assert returned_core["memory"]["chronicle"]["events"][:-1] == original_core["chronicle"]["events"]
    assert module.core_state(returned_core)["authority"] == "FROZEN"
    bad = morph_core_offer(now, "spark-core-bad")
    bad["snapshot"]["payload"]["morph_core"]["identity"]["device_birth_lineage"] = "other"
    bad["snapshot"]["sha256"] = hashlib.sha256(canonical(bad["snapshot"]["payload"]).encode()).hexdigest()
    try: module.MorphTransferLedger.empty().prepare_inbound(bad, now)
    except module.TransferError as err: assert err.code == "IDENTITY_CONFLICT"
    else: raise AssertionError("transfer envelope accepted different Morph Core identity")


def test_v3_shared_state_and_android_extension_are_exact():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    mismatch = morph_core_offer(now, "state-mismatch")
    mismatch["snapshot"]["payload"]["morph_core"]["state"]["needs_q8"]["energy"] -= 1
    mismatch["snapshot"]["sha256"] = hashlib.sha256(canonical(mismatch["snapshot"]["payload"]).encode()).hexdigest()
    try: module.MorphTransferLedger.empty().prepare_inbound(mismatch, now)
    except module.TransferError as err: assert err.code == "MORPH_CORE_STATE_CONFLICT"
    else: raise AssertionError("conflicting Morph Core state accepted")

    android = morph_core_offer(now, "android-core")
    android["engine_version"] = module.ENGINE_VERSION
    android["source_frame"] = "android-frame:opaque-app-identity"
    android["snapshot"]["payload"]["morph_core"]["state"]["active_frame"] = android["source_frame"]
    extension = {"schema": module.ANDROID_EXTENSION_SCHEMA, "payload": {}}
    extension["sha256"] = hashlib.sha256(canonical(extension["payload"]).encode()).hexdigest()
    android["snapshot"]["payload"]["engine_extension"] = extension
    android["snapshot"]["sha256"] = hashlib.sha256(canonical(android["snapshot"]["payload"]).encode()).hexdigest()
    module.MorphTransferLedger.empty().prepare_inbound(android, now)
    android["snapshot"]["payload"]["engine_extension"]["payload"] = {"invented": True}
    android["snapshot"]["payload"]["engine_extension"]["sha256"] = hashlib.sha256(
        canonical(android["snapshot"]["payload"]["engine_extension"]["payload"]).encode()).hexdigest()
    android["snapshot"]["sha256"] = hashlib.sha256(canonical(android["snapshot"]["payload"]).encode()).hexdigest()
    try: module.MorphTransferLedger.empty().prepare_inbound(android, now)
    except module.TransferError as err: assert err.code == "INVALID_ENGINE_EXTENSION"
    else: raise AssertionError("invented Android extension accepted")


def test_v3_upgrade_and_downgrade_require_explicit_migration():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = module.MorphTransferLedger.empty()
    first = morph_core_offer(now, "core-first")
    prepared = ledger.prepare_inbound(first, now)
    ledger.commit_inbound("core-first", prepared["snapshot_digest"], now)
    ledger.data["morphs"]["spark"]["authority"] = first["source_frame"]
    downgrade = esp32_offer(now, "core-down")
    downgrade["generation"] = 2; downgrade["predecessor_generation"] = 1
    try: ledger.prepare_inbound(downgrade, now)
    except module.TransferError as err: assert err.code == "LIFE_SCHEMA_DOWNGRADE"
    else: raise AssertionError("v3 downgrade accepted")

    legacy = module.MorphTransferLedger.empty()
    old = esp32_offer(now, "legacy-first")
    prepared = legacy.prepare_inbound(old, now)
    legacy.commit_inbound("legacy-first", prepared["snapshot_digest"], now)
    legacy.data["morphs"]["spark"]["authority"] = old["source_frame"]
    upgrade = morph_core_offer(now, "legacy-up")
    upgrade["generation"] = 2; upgrade["predecessor_generation"] = 1
    try: legacy.prepare_inbound(upgrade, now)
    except module.TransferError as err: assert err.code == "MORPH_CORE_MIGRATION_REQUIRED"
    else: raise AssertionError("legacy state was silently promoted to v3")


def migration_request(ledger, now, migration_id="spark-migration-1"):
    upgraded = morph_core_offer(now, "unused-migration-envelope")["snapshot"]
    upgraded["payload"]["morph_core"]["state"]["place"] = "CODE_HAVEN"
    upgraded["payload"]["morph_core"]["state"]["active_frame"] = "haos-code-haven"
    upgraded["sha256"] = module.sha256_json(upgraded["payload"])
    return {
        "schema": module.MORPH_CORE_MIGRATION_SCHEMA,
        "migration_id": migration_id,
        "morph_id": "spark",
        "founder_id": "SPARK",
        "device_birth_lineage": "serein-lineage:v1:spark-fixture",
        "genome_sha256": ledger.data["morphs"]["spark"]["genome_sha256"],
        "source_frame": "esp32-frame:v1:spark-fixture",
        "current_authority": "esp32-frame:v1:spark-fixture",
        "generation": 1,
        "predecessor_snapshot_digest": ledger.data["morphs"]["spark"]["snapshot_digest"],
        "created_at": now.isoformat(),
        "actor": "haos-morph-core-migrator",
        "reason": "attributable-v2-to-v3-admission",
        "evidence_digest": hashlib.sha256(b"spark-v2-to-v3-evidence").hexdigest(),
        "snapshot": upgraded,
    }


def legacy_source_owned_ledger(now):
    ledger = module.MorphTransferLedger.empty()
    old = esp32_offer(now, "legacy-for-migration")
    prepared = ledger.prepare_inbound(old, now)
    ledger.commit_inbound(old["transfer_id"], prepared["snapshot_digest"], now)
    # Models the completed prior return: the original frame is sole authority.
    ledger.data["morphs"]["spark"]["authority"] = old["source_frame"]
    ledger.data["morphs"]["spark"]["engine_state"] = "REMOTE_ACTIVE"
    return ledger


def test_explicit_v2_to_v3_migration_preserves_owner_generation_and_lineage():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = legacy_source_owned_ledger(now)
    before = deepcopy(ledger.data["morphs"]["spark"])
    request = migration_request(ledger, now)
    result = ledger.migrate_to_morph_core(request, now)
    current = ledger.data["morphs"]["spark"]

    assert result["operation_state"] == "MIGRATED"
    assert result["migration_id"] == request["migration_id"]
    assert result["authority"] == before["authority"] == request["source_frame"]
    assert current["generation"] == before["generation"] == 1
    assert current["morph_id"] == before["morph_id"]
    assert current["founder_id"] == before["founder_id"]
    assert current["device_birth_lineage"] == before["device_birth_lineage"]
    assert current["source_frame"] == before["source_frame"]
    assert current["snapshot"]["schema"] == module.MORPH_CORE_LIFE_SCHEMA
    assert current["snapshot"]["payload"]["engine_extension"] == before["snapshot"]["payload"]["engine_extension"]
    assert ledger.migrate_to_morph_core(request, now) == result
    readback = ledger.status(request["migration_id"], include_snapshot=True)
    assert readback["operation_state"] == "MIGRATED"
    assert readback["snapshot"] == request["snapshot"]
    assert readback["founder_id"] == request["founder_id"]
    assert "engine_version" not in readback
    assert "genome" not in readback
    evidence = ledger.evidence_bundle(request["migration_id"])
    assert evidence["schema"] == module.MORPH_EVIDENCE_SCHEMA
    assert evidence["predecessor_snapshot"] == before["snapshot"]
    assert evidence["request"] == request
    assert evidence["result"] == readback
    assert evidence["bundle_digest"] == module.sha256_json({key: value for key, value in evidence.items() if key != "bundle_digest"})


def test_migration_rejects_wrong_predecessor_changed_replay_and_second_upgrade():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    wrong = legacy_source_owned_ledger(now)
    request = migration_request(wrong, now)
    request["predecessor_snapshot_digest"] = "0" * 64
    try: wrong.migrate_to_morph_core(request, now)
    except module.TransferError as err: assert err.code == "PREDECESSOR_DIGEST_MISMATCH"
    else: raise AssertionError("migration accepted the wrong predecessor digest")

    ledger = legacy_source_owned_ledger(now)
    request = migration_request(ledger, now)
    ledger.migrate_to_morph_core(request, now)
    replay = deepcopy(request); replay["reason"] = "changed"
    try: ledger.migrate_to_morph_core(replay, now)
    except module.TransferError as err: assert err.code == "REPLAY_CONFLICT"
    else: raise AssertionError("changed migration replay was accepted")
    second = deepcopy(request); second["migration_id"] = "spark-migration-2"
    second["predecessor_snapshot_digest"] = ledger.data["morphs"]["spark"]["snapshot_digest"]
    try: ledger.migrate_to_morph_core(second, now)
    except module.TransferError as err: assert err.code == "LIFE_SCHEMA_DOWNGRADE"
    else: raise AssertionError("already-v3 Morph accepted another migration")


def test_migration_rejects_morph_core_write_outside_code_haven():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = legacy_source_owned_ledger(now)
    request = migration_request(ledger, now)
    state = request["snapshot"]["payload"]["morph_core"]["state"]
    state["place"] = "HORIZON"
    state["active_frame"] = "haos-horizon"
    request["snapshot"]["sha256"] = module.sha256_json(request["snapshot"]["payload"])
    try: ledger.migrate_to_morph_core(request, now)
    except module.TransferError as err: assert err.code == "CODE_HAVEN_REQUIRED"
    else: raise AssertionError("migration wrote Morph Core outside Code Haven")


def test_code_haven_repairs_only_the_canonical_primitive_and_records_it():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = module.MorphTransferLedger.empty()
    offer = morph_core_offer(now, "repair-fixture")
    core = offer["snapshot"]["payload"]["morph_core"]
    core["identity"]["primitive_element"] = "WATER"
    core["state"]["place"] = "CODE_HAVEN"
    core["state"]["active_frame"] = "haos-code-haven"
    offer["snapshot"]["sha256"] = module.sha256_json(offer["snapshot"]["payload"])
    prepared = ledger.prepare_inbound(offer, now)
    ledger.commit_inbound(offer["transfer_id"], prepared["snapshot_digest"], now)
    before = deepcopy(ledger.data["morphs"]["spark"])
    request = {
        "schema": module.MORPH_CORE_REPAIR_SCHEMA, "repair_id": "spark-element-repair-1",
        "morph_id": "spark", "current_authority": "HAOS", "generation": 1,
        "predecessor_snapshot_digest": before["snapshot_digest"],
        "expected_current_element": "WATER", "corrected_element": "AIR",
        "created_at": now.isoformat(), "actor": "haos-code-haven",
        "reason": "operator-corrected-founder-primitive",
        "evidence_digest": hashlib.sha256(b"operator correction").hexdigest(),
    }
    result = ledger.repair_primitive_element(request, now)
    current = ledger.data["morphs"]["spark"]
    assert result["operation_state"] == "REPAIRED"
    assert module.core_identity(current["snapshot"]["payload"]["morph_core"])["primitive_element"] == "AIR"
    assert current["morph_id"] == before["morph_id"]
    assert current["device_birth_lineage"] == before["device_birth_lineage"]
    assert current["generation"] == before["generation"]
    assert current["genome_sha256"] == before["genome_sha256"]
    assert current["snapshot"]["payload"]["morph_core"]["memory"]["chronicle"]["events"][-1]["kind"] == "lineage-correction"
    assert ledger.repair_primitive_element(request, now) == result
    evidence = ledger.evidence_bundle(request["repair_id"])
    assert evidence["predecessor_snapshot"] == before["snapshot"]
    assert evidence["request"] == request
    assert evidence["result"] == result


def test_migration_evidence_remains_historically_immutable_after_later_change():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = legacy_source_owned_ledger(now)
    request = migration_request(ledger, now)
    original_result = ledger.migrate_to_morph_core(request, now)
    original_bundle = ledger.evidence_bundle(request["migration_id"])
    morph = ledger.data["morphs"]["spark"]
    morph["authority"] = "HAOS"
    morph["snapshot"]["payload"]["food_q8"] -= 1
    morph["snapshot"]["payload"]["morph_core"]["state"]["needs_q8"]["food"] -= 1
    module.refresh_snapshot(morph)
    assert ledger.evidence_bundle(request["migration_id"]) == original_bundle
    assert original_bundle["result"] == original_result
    assert original_bundle["result"]["current_snapshot_digest"] != morph["snapshot_digest"]


def test_historical_operation_without_captured_evidence_fails_closed():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = legacy_source_owned_ledger(now)
    request = migration_request(ledger, now)
    ledger.migrate_to_morph_core(request, now)
    del ledger.data["operations"][request["migration_id"]]["completion_receipt"]
    try:
        ledger.evidence_bundle(request["migration_id"])
    except module.TransferError as err:
        assert err.code == "HISTORICAL_EVIDENCE_UNAVAILABLE"
    else:
        raise AssertionError("historical evidence was reconstructed from current state")


def test_automatic_code_haven_alignment_still_rejects_noncanonical_repair():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = module.MorphTransferLedger.empty()
    offer = morph_core_offer(now, "repair-reject-fixture")
    prepared = ledger.prepare_inbound(offer, now)
    ledger.commit_inbound(offer["transfer_id"], prepared["snapshot_digest"], now)
    morph = ledger.data["morphs"]["spark"]
    request = {
        "schema": module.MORPH_CORE_REPAIR_SCHEMA, "repair_id": "repair-reject-1",
        "morph_id": "spark", "current_authority": "HAOS", "generation": 1,
        "predecessor_snapshot_digest": morph["snapshot_digest"],
        "expected_current_element": "AIR", "corrected_element": "WATER",
        "created_at": now.isoformat(), "actor": "haos-code-haven", "reason": "bad-repair",
        "evidence_digest": hashlib.sha256(b"bad repair").hexdigest(),
    }
    try: ledger.repair_primitive_element(request, now)
    except module.TransferError as err: assert err.code == "NONCANONICAL_REPAIR"
    else: raise AssertionError("noncanonical primitive repair was accepted")


def test_migration_rejects_authority_generation_identity_and_attribution_changes():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    cases = []
    authority = legacy_source_owned_ledger(now); authority.data["morphs"]["spark"]["authority"] = "HAOS"
    cases.append((authority, migration_request(authority, now), "AUTHORITY_CONFLICT"))
    generation = legacy_source_owned_ledger(now); generation_request = migration_request(generation, now)
    generation_request["generation"] = 2; cases.append((generation, generation_request, "GENERATION_CONFLICT"))
    identity = legacy_source_owned_ledger(now); identity_request = migration_request(identity, now)
    identity_request["snapshot"]["payload"]["morph_core"]["identity"]["device_birth_lineage"] = "other"
    identity_request["snapshot"]["sha256"] = hashlib.sha256(canonical(identity_request["snapshot"]["payload"]).encode()).hexdigest()
    cases.append((identity, identity_request, "IDENTITY_CONFLICT"))
    attribution = legacy_source_owned_ledger(now); attribution_request = migration_request(attribution, now)
    attribution_request["actor"] = ""; cases.append((attribution, attribution_request, "INVALID_ATTRIBUTION"))
    rewritten = legacy_source_owned_ledger(now); rewritten_request = migration_request(rewritten, now)
    rewritten_request["snapshot"]["payload"]["food_q8"] -= 1
    rewritten_request["snapshot"]["payload"]["morph_core"]["state"]["needs_q8"]["food"] -= 1
    rewritten_request["snapshot"]["sha256"] = hashlib.sha256(canonical(rewritten_request["snapshot"]["payload"]).encode()).hexdigest()
    cases.append((rewritten, rewritten_request, "LEGACY_LIFE_REWRITE"))

    for ledger, request, code in cases:
        try: ledger.migrate_to_morph_core(request, now)
        except module.TransferError as err: assert err.code == code
        else: raise AssertionError(f"migration accepted {code} case")


def legacy_v1_haos_ledger(now):
    ledger = module.MorphTransferLedger.empty()
    old = offer(now, "pulse-v1-current")
    prepared = ledger.prepare_inbound(old, now)
    ledger.commit_inbound(old["transfer_id"], prepared["snapshot_digest"], now)
    ledger.data["morphs"]["pulse"]["generation"] = 2
    return ledger


def v1_migration_request(ledger, now, migration_id="pulse-migrate-v1-v3"):
    current = ledger.data["morphs"]["pulse"]
    payload = deepcopy(current["snapshot"]["payload"])
    extension_payload = {}
    payload["engine_extension"] = {
        "schema": module.ANDROID_EXTENSION_SCHEMA,
        "payload": extension_payload,
        "sha256": hashlib.sha256(canonical(extension_payload).encode()).hexdigest(),
    }
    evidence_digest = hashlib.sha256(b"pulse-v1-v3-attribution").hexdigest()
    core = {
        "schema": "serein.morph-core.v1",
        "identity": {"morph_id": "pulse", "founder_lineage": "founder:pulse",
                     "device_birth_lineage": current["device_birth_lineage"],
                     "born_at": now.isoformat(), "generation": 0, "parent_ids": [],
                     "primitive_element": "AIR", "genome_version": "dnav1"},
        "life": {"growth_q16": 0, "care_counts": {}, "relationship_counts": {},
                 "journey_count": 0, "elemental_mastery_q16": {}},
        "state": {"place": "CODE_HAVEN", "authority": "HAOS_ACTIVE",
                  "active_frame": "haos-code-haven",
                  "needs_q8": {"attention": payload["attention_q8"],
                               "energy": 255 - payload["fatigue_q8"],
                               "food": payload["food_q8"], "play": payload["play_q8"],
                               "rest": payload["rest_q8"], "water": payload["water_q8"]},
                  "mood": payload["behavior"].lower(), "expression": "legacy"},
        "embodiment": {"body_id": "haos-code-haven", "body_class": "haos-habitat",
                       "capabilities": []},
        "chronicle": {"schema": "serein.living-code-chronicle.v1", "events": [{
            "event_id": migration_id, "kind": "migration", "observed_at": now.isoformat(),
            "source": "haos-morph-core-migrator", "place": "CODE_HAVEN",
            "frame": "haos-code-haven", "evidence_digest": evidence_digest,
        }]},
    }
    payload["morph_core"] = core
    target = {"schema": module.MORPH_CORE_LIFE_SCHEMA, "payload": payload}
    target["sha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
    return {
        "schema": module.MORPH_CORE_MIGRATION_SCHEMA,
        "migration_id": migration_id,
        "morph_id": "pulse",
        "founder_id": current["founder_id"],
        "device_birth_lineage": current["device_birth_lineage"],
        "genome_sha256": current["genome_sha256"],
        "source_frame": current["source_frame"],
        "current_authority": "HAOS",
        "generation": 2,
        "predecessor_snapshot_digest": current["snapshot_digest"],
        "created_at": now.isoformat(),
        "actor": "haos-morph-core-migrator",
        "reason": "attributable-v1-to-v3-admission-with-unknown-history",
        "evidence_digest": evidence_digest,
        "snapshot": target,
    }


def test_explicit_v1_to_v3_migration_preserves_haos_authority_generation_and_legacy_life():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    ledger = legacy_v1_haos_ledger(now)
    before = deepcopy(ledger.data["morphs"]["pulse"])
    request = v1_migration_request(ledger, now)
    result = ledger.migrate_to_morph_core(request, now)
    current = ledger.data["morphs"]["pulse"]
    assert result["authority"] == current["authority"] == before["authority"] == "HAOS"
    assert result["current_generation"] == current["generation"] == before["generation"] == 2
    assert current["source_frame"] == before["source_frame"]
    assert current["device_birth_lineage"] == before["device_birth_lineage"]
    for field, value in before["snapshot"]["payload"].items():
        assert current["snapshot"]["payload"][field] == value
    assert ledger.migrate_to_morph_core(request, now) == result
    changed_replay = deepcopy(request); changed_replay["reason"] = "changed-replay"
    try: ledger.migrate_to_morph_core(changed_replay, now)
    except module.TransferError as err: assert err.code == "REPLAY_CONFLICT"
    else: raise AssertionError("changed v1 migration replay was accepted")


def test_v1_migration_rejects_wrong_authority_digest_identity_and_invented_history():
    now = datetime(2026, 9, 6, tzinfo=UTC)
    cases = []
    authority = legacy_v1_haos_ledger(now); req = v1_migration_request(authority, now)
    req["current_authority"] = req["source_frame"]; cases.append((authority, req, "AUTHORITY_CONFLICT"))
    digest = legacy_v1_haos_ledger(now); req = v1_migration_request(digest, now)
    req["predecessor_snapshot_digest"] = "0" * 64; cases.append((digest, req, "PREDECESSOR_DIGEST_MISMATCH"))
    identity = legacy_v1_haos_ledger(now); req = v1_migration_request(identity, now)
    req["founder_id"] = "OTHER"; cases.append((identity, req, "IDENTITY_CONFLICT"))
    core_identity = legacy_v1_haos_ledger(now); req = v1_migration_request(core_identity, now)
    req["snapshot"]["payload"]["morph_core"]["identity"]["morph_id"] = "other"
    req["snapshot"]["sha256"] = hashlib.sha256(canonical(req["snapshot"]["payload"]).encode()).hexdigest()
    cases.append((core_identity, req, "IDENTITY_CONFLICT"))
    extension = legacy_v1_haos_ledger(now); req = v1_migration_request(extension, now)
    req["snapshot"]["payload"]["engine_extension"]["payload"] = {"invented": True}
    req["snapshot"]["payload"]["engine_extension"]["sha256"] = hashlib.sha256(
        canonical(req["snapshot"]["payload"]["engine_extension"]["payload"]).encode()).hexdigest()
    req["snapshot"]["sha256"] = hashlib.sha256(canonical(req["snapshot"]["payload"]).encode()).hexdigest()
    cases.append((extension, req, "INVALID_ENGINE_EXTENSION"))
    history = legacy_v1_haos_ledger(now); req = v1_migration_request(history, now)
    req["snapshot"]["payload"]["morph_core"]["life"]["journey_count"] = 1
    req["snapshot"]["sha256"] = hashlib.sha256(canonical(req["snapshot"]["payload"]).encode()).hexdigest()
    cases.append((history, req, "INVENTED_HISTORY"))
    event = legacy_v1_haos_ledger(now); req = v1_migration_request(event, now)
    req["snapshot"]["payload"]["morph_core"]["chronicle"]["events"][0]["kind"] = "birth"
    req["snapshot"]["sha256"] = hashlib.sha256(canonical(req["snapshot"]["payload"]).encode()).hexdigest()
    cases.append((event, req, "INVENTED_HISTORY"))
    for ledger, request, code in cases:
        try: ledger.migrate_to_morph_core(request, now)
        except module.TransferError as err: assert err.code == code
        else: raise AssertionError(f"v1 migration accepted {code} case")


def dustdevil_in_void(now):
    request = morph_core_offer(now, "dustdevil-birth")
    morph_id = module.FIRST_WHOLE_MORPH_ID
    parents = ["serein-morph:v1:sentinel", "serein-morph:v1:breeze"]
    request.update({
        "morph_id": morph_id, "founder_id": "DESCENDANT",
        "device_birth_lineage": "nursery-lineage:37ca6f7dfd4fbba83f43ab4e88f8bf90",
        "source_frame": "haos-nursery", "generation": 1, "predecessor_generation": 0,
    })
    core = request["snapshot"]["payload"]["morph_core"]
    core["identity"].update({
        "morph_id": morph_id, "founder_lineage": "descendant:dustdevil",
        "device_birth_lineage": request["device_birth_lineage"], "generation": 1,
        "parent_ids": parents, "primitive_element": "AIR",
    })
    core["state"].update({"place": "VOID", "authority": "HAOS_ACTIVE",
                          "active_frame": "haos-void", "expression": "latent"})
    core["embodiment"] = {"body_id": "nursery-newborn", "body_class": "morph-child",
                           "capabilities": []}
    request["snapshot"]["sha256"] = hashlib.sha256(canonical(request["snapshot"]["payload"]).encode()).hexdigest()
    request["genome"] = "family=DUST\nparents=sentinel,breeze\n"
    request["genome_sha256"] = hashlib.sha256(request["genome"].encode()).hexdigest()
    ledger = module.MorphTransferLedger.empty()
    prepared = ledger.prepare_inbound(request, now)
    ledger.commit_inbound(request["transfer_id"], prepared["snapshot_digest"], now)
    morph = ledger.data["morphs"][morph_id]
    morph["habitat"] = {"place": "VOID", "engine_state": "STASIS"}
    return ledger


def inward_bloom_request(ledger, now, bloom_id="dustdevil.inward-bloom.v1"):
    morph = ledger.data["morphs"][module.FIRST_WHOLE_MORPH_ID]
    return {
        "schema": module.INWARD_BLOOM_SCHEMA, "bloom_id": bloom_id,
        "morph_id": morph["morph_id"], "current_authority": "HAOS",
        "generation": morph["generation"],
        "predecessor_snapshot_digest": morph["snapshot_digest"],
        "created_at": now.isoformat(), "actor": "haos-morphdomain",
        "evidence_digest": hashlib.sha256(b"dustdevil-live-birth-nursery-void").hexdigest(),
    }


def test_inward_bloom_creates_exact_nine_cores_and_deterministic_voice_without_life_drift():
    now = datetime(2026, 9, 8, 22, 0, tzinfo=UTC)
    ledger = dustdevil_in_void(now)
    morph = ledger.data["morphs"][module.FIRST_WHOLE_MORPH_ID]
    before = deepcopy(morph)
    request = inward_bloom_request(ledger, now)
    receipt = ledger.record_inward_bloom(request, now)
    current = ledger.data["morphs"][morph["morph_id"]]
    core = current["snapshot"]["payload"]["morph_core"]
    assert set(core) == {"schema", "platform", "root", "memory", "knowledge", "ui",
                         "audio", "personality", "modular", "cloud"}
    assert core["root"]["historic_role"] == "first-whole"
    assert core["root"]["emergence_event"] == "inward-bloom"
    assert core["audio"]["schema"] == "serein.elemental-voice.v1"
    assert core["audio"]["element_voice"] == "dust"
    assert core["audio"]["trait_modifier"] == "inward-bloom"
    assert core["personality"]["trait_stage"] == 0
    assert core["cloud"]["place"] == "VOID"
    assert core["memory"]["life"] == before["snapshot"]["payload"]["morph_core"]["life"]
    assert current["authority"] == before["authority"] == "HAOS"
    assert current["generation"] == before["generation"] == 1
    assert receipt["bloom_id"] == request["bloom_id"]
    assert ledger.record_inward_bloom(request, now) == receipt


def test_inward_bloom_rejects_other_morph_void_or_digest_replay():
    now = datetime(2026, 9, 8, 22, 0, tzinfo=UTC)
    ledger = dustdevil_in_void(now)
    wrong = inward_bloom_request(ledger, now)
    wrong["morph_id"] = "pulse"
    try: ledger.record_inward_bloom(wrong, now)
    except module.TransferError as err: assert err.code == "INWARD_BLOOM_NOT_ELIGIBLE"
    else: raise AssertionError("non-Dustdevil Inward Bloom was accepted")
    request = inward_bloom_request(ledger, now)
    request["predecessor_snapshot_digest"] = "0" * 64
    try: ledger.record_inward_bloom(request, now)
    except module.TransferError as err: assert err.code == "PREDECESSOR_DIGEST_MISMATCH"
    else: raise AssertionError("wrong predecessor was accepted")

