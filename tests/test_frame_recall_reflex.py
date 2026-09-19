"""The HAOS recall reflex must admit a frozen ESPHome nine-core successor."""

from datetime import UTC, datetime
import hashlib
import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).parents[1] / "custom_components" / "morph_domain"
PACKAGE = "frame_recall_fixture"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package
for name in ("voluptuous", "homeassistant", "homeassistant.components", "homeassistant.components.http",
             "homeassistant.core", "homeassistant.helpers", "homeassistant.helpers.storage"):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["voluptuous"].Invalid = ValueError
sys.modules["homeassistant.components.http"].HomeAssistantView = object
sys.modules["homeassistant.core"].HomeAssistant = object
sys.modules["homeassistant.helpers.storage"].Store = type(
    "Store", (), {"__class_getitem__": classmethod(lambda cls, _: cls)})
spec = importlib.util.spec_from_file_location(PACKAGE + ".morph_transfer", ROOT / "morph_transfer.py")
adapter = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = adapter
spec.loader.exec_module(adapter)

from frame_recall_fixture._vendor.morph_sdk.morph_core import align_in_code_haven


def test_frozen_sentinel_recall_builds_an_admissible_next_generation():
    now = datetime(2026, 9, 19, 12, tzinfo=UTC)
    morph_id = "serein-morph:v1:" + "5" * 64
    frame = "esp32-frame:v1:pet-frame-sentinel"
    identity = {"morph_id": morph_id, "founder_lineage": "founder:sentinel",
                "device_birth_lineage": "serein-lineage:v1:" + "5" * 64,
                "born_at": "2026-08-24T00:00:00Z", "generation": 0,
                "parent_ids": [], "primitive_element": "EARTH", "genome_version": "dnav1"}
    legacy = {"schema": "serein.morph-core.v1", "identity": identity,
              "life": {"growth_q16": 50, "care_counts": {"feed": 1, "water": 1, "play": 1, "rest": 1},
                       "relationship_counts": {"founder_encounters": 0}, "journey_count": 1,
                       "elemental_mastery_q16": {"earth": 40}},
              "state": {"place": "HORIZON", "authority": "REMOTE_ACTIVE", "active_frame": frame,
                        "needs_q8": {"attention": 200, "energy": 191, "food": 200, "play": 200,
                                     "rest": 200, "water": 200}, "mood": "settle", "expression": "earth-stage-3"},
              "embodiment": {"body_id": "pet-frame-sentinel", "body_class": "pet-frame",
                              "capabilities": ["display", "wifi", "audio"]},
              "chronicle": {"schema": "serein.living-code-chronicle.v1", "events": []}}
    core = align_in_code_haven(legacy, "a" * 64, "alignment:test", now.isoformat(),
                               "haos-code-haven", "b" * 64, historic_role="founder")
    extension_payload = {"birth_epoch": 1, "care_counts": {"feed": 1, "water": 1, "play": 1, "rest": 1},
                         "development_q8": 0, "elemental_mastery_q16": {"EARTH": 40},
                         "expression_stage": 3, "founder_encounters": 0, "founder_seen_mask": 0,
                         "growth_q16": 50, "world_location": 0}
    payload = {"saved_epoch_seconds": 1, "behavior": "SETTLE", "arousal_q8": 64,
               "security_q8": 180, "curiosity_q8": 128, "social_q8": 128, "fatigue_q8": 64,
               "food_q8": 200, "water_q8": 200, "play_q8": 200, "rest_q8": 200,
               "attention_q8": 200, "memories": [], "morph_core": core,
               "engine_extension": {"schema": "serein.esphome.sentinel-life-extension.v1",
                                    "payload": extension_payload,
                                    "sha256": adapter.sha256_json(extension_payload)}}
    snapshot = {"schema": adapter.MORPH_CORE_LIFE_SCHEMA, "payload": payload,
                "sha256": adapter.sha256_json(payload)}
    genome = "founder=SENTINEL\n"
    morph = {"morph_id": morph_id, "founder_id": "SENTINEL",
             "device_birth_lineage": identity["device_birth_lineage"], "source_frame": frame,
             "authority": frame, "generation": 2, "engine_version": adapter.ESPHOME_ENGINE_VERSION,
             "engine_state": "REMOTE_ACTIVE",
             "genome": genome, "genome_sha256": hashlib.sha256(genome.encode()).hexdigest(),
             "snapshot": snapshot, "snapshot_digest": adapter.validate_snapshot(snapshot)}
    offer = adapter.build_frame_recall_offer(
        morph, "sentinel-3-test",
        "v1|saved=2|behavior=SETTLE|arousal=64|security=180|curiosity=128|social=128|fatigue=32|food=220|water=221|play=222|rest=223|attention=224",
        "v1|birth=1|fed=2|watered=2|played=2|napped=2|attention=2|growth=60|development=1|earth=55|stage=3|feed_count=2|water_count=2|play_count=2|rest_count=2|world=0|seen=0|encounters=1",
        "v1|morph=sentinel|founder=founder:sentinel|birth_lineage=x|primitive=EARTH|genome=dnav1|body=pet-frame-sentinel|class=pet-frame|place=HORIZON|journeys=2|chronicle=2",
        now)
    ledger = adapter.MorphTransferLedger({"schema": adapter.API_SCHEMA, "morphs": {morph_id: morph}, "operations": {}})
    prepared = ledger.prepare_inbound(offer, now)
    assert prepared["generation"] == 3
    assert offer["snapshot"]["payload"]["morph_core"]["cloud"]["authority"] == "HAOS_ACTIVE"
    assert offer["snapshot"]["payload"]["morph_core"]["memory"]["life"]["journey_count"] == 2

