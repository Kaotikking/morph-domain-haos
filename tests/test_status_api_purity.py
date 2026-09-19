"""Focused regression: authenticated Morph reads never perform maintenance."""

import asyncio
import importlib.util
from pathlib import Path
import sys
import types


ROOT = Path(__file__).parents[1] / "custom_components" / "morph_domain"
PACKAGE = "status_purity_fixture"
package = types.ModuleType(PACKAGE)
package.__path__ = [str(ROOT)]
sys.modules[PACKAGE] = package

for name in (
    "voluptuous", "homeassistant", "homeassistant.components",
    "homeassistant.components.http", "homeassistant.core",
    "homeassistant.helpers", "homeassistant.helpers.storage",
    "homeassistant.helpers.event",
):
    sys.modules.setdefault(name, types.ModuleType(name))
sys.modules["voluptuous"].Invalid = ValueError
sys.modules["homeassistant.components.http"].HomeAssistantView = object
sys.modules["homeassistant.core"].HomeAssistant = object
sys.modules["homeassistant.helpers.storage"].Store = type(
    "Store", (), {"__class_getitem__": classmethod(lambda cls, _: cls)}
)
sys.modules["homeassistant.helpers.event"].async_track_time_interval = lambda *args: None

vendor = types.ModuleType(PACKAGE + "._vendor")
vendor.__path__ = []
sdk = types.ModuleType(PACKAGE + "._vendor.morph_sdk")
sdk.__path__ = []
transfer_stub = types.ModuleType(PACKAGE + "._vendor.morph_sdk.transfer")


class TransferError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class Ledger:
    reconciliations = 0

    def __init__(self, data):
        self.data = data

    def reconcile_expired(self, now):
        self.reconciliations += 1
        self.data["expired"] = True
        return True

    def status(self, transfer_id, include_snapshot=False):
        return {"transfer_id": transfer_id, "state": "PREPARED"}

    def prepare_inbound(self, body, now):
        return {"transfer_id": body["transfer_id"], "state": "PREPARED"}


transfer_stub.DATA_KEY = "morph_domain_transfer"
transfer_stub.STORE_KEY = "morph_domain.transfer"
transfer_stub.LEGACY_STORE_KEY = "serein_gateway.morph_transfer"
transfer_stub.STORE_VERSION = 1
transfer_stub.MorphTransferLedger = Ledger
transfer_stub.TransferError = TransferError
transfer_stub._exact = lambda body, fields, label: (
    None if set(body) == fields else (_ for _ in ()).throw(ValueError(label))
)
for module in (vendor, sdk, transfer_stub):
    sys.modules[module.__name__] = module

metrics_stub = types.ModuleType(PACKAGE + ".runtime_metrics")


class Metrics:
    def record_expiry_reconciliation(self, **kwargs):
        pass

    def record_storage_decision(self, **kwargs):
        pass

    def record_api(self, *args, **kwargs):
        pass


metrics_stub.MorphRuntimeMetrics = Metrics
sys.modules[metrics_stub.__name__] = metrics_stub
migration_stub = types.ModuleType(PACKAGE + ".migration")
migration_stub.legacy_engine_enabled = lambda hass: False
sys.modules[migration_stub.__name__] = migration_stub
habitat_stub = types.ModuleType(PACKAGE + ".morph_habitat")
habitat_stub.habitat_status = lambda ledger, morph_id, now: {"morph_id": morph_id}
habitat_stub.habitat_list = lambda ledger, now: {"morphs": []}
habitat_stub.habitat_history = lambda ledger, morph_id, now: {"events": []}
habitat_stub.read_environment = lambda hass, now: (_ for _ in ()).throw(AssertionError("environment sampled on read"))
habitat_stub.advance_morph = lambda morph, now, env: (_ for _ in ()).throw(AssertionError("life advanced on read"))
for name in ("care_for_morph", "call_morph", "place_morph", "update_presentation",
             "register_founder_axis", "advance_founder_axis"):
    setattr(habitat_stub, name, lambda *args: None)
sys.modules[habitat_stub.__name__] = habitat_stub
origin_stub = types.ModuleType(PACKAGE + "._vendor.morph_sdk.gen1_origin")
for name in ("create_starter", "hatch_starter", "starter_status"):
    setattr(origin_stub, name, lambda *args: None)
sys.modules[origin_stub.__name__] = origin_stub
engine = types.ModuleType(PACKAGE + "._vendor.morph_engine")
engine.__path__ = []
engine_habitat = types.ModuleType(PACKAGE + "._vendor.morph_engine.habitat")
for name in ("habitat_status", "habitat_list", "habitat_history", "read_environment",
             "advance_morph", "care_for_morph", "call_morph", "place_morph",
             "update_presentation", "register_founder_axis", "advance_founder_axis"):
    setattr(engine_habitat, name, getattr(habitat_stub, name))
engine_habitat.HABITAT_DATA_KEY = "morph_habitat"
engine_habitat.HABITAT_SCHEMA = "test-habitat-schema"
engine_habitat.PLACES = {"HORIZON"}
engine_habitat.CARE_ACTIONS = {"rest"}
engine_habitat.TICK_INTERVAL = 60
sys.modules[engine.__name__] = engine
sys.modules[engine_habitat.__name__] = engine_habitat
sern = types.ModuleType(PACKAGE + ".sern")
sern.SernEnvelopeError = ValueError
sern.validate_envelope = lambda envelope: envelope
sys.modules[sern.__name__] = sern

spec = importlib.util.spec_from_file_location(PACKAGE + ".morph_transfer", ROOT / "morph_transfer.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
habitat_spec = importlib.util.spec_from_file_location(PACKAGE + ".morph_habitat", ROOT / "morph_habitat.py")
habitat_module = importlib.util.module_from_spec(habitat_spec)
sys.modules[habitat_spec.name] = habitat_module
habitat_spec.loader.exec_module(habitat_module)


class Store:
    def __init__(self):
        self.writes = 0

    async def async_save(self, data):
        self.writes += 1


def manager():
    obj = object.__new__(module.MorphTransferManager)
    obj.hass = object()
    obj.ledger = Ledger({"morphs": {}, "operations": {}})
    obj.store = Store()
    obj.lock = asyncio.Lock()
    obj.metrics = Metrics()
    return obj


def test_transfer_status_does_not_reconcile_or_save():
    obj = manager()
    result = asyncio.run(obj.handle("status", {"transfer_id": "t1"}))
    assert result["transfer_id"] == "t1"
    assert obj.store.writes == 0
    assert obj.ledger.reconciliations == 0
    assert obj.ledger.data == {"morphs": {}, "operations": {}}


def test_habitat_status_does_not_reconcile_advance_or_save():
    obj = manager()
    result = asyncio.run(obj.handle_habitat("status", {"morph_id": "dustdevil"}))
    assert result == {"morph_id": "dustdevil"}
    assert obj.store.writes == 0
    assert obj.ledger.reconciliations == 0
    assert obj.ledger.data == {"morphs": {}, "operations": {}}


def test_habitat_list_does_not_reconcile_advance_or_save():
    obj = manager()
    result = asyncio.run(obj.handle_habitat("list", {}))
    assert result == {"morphs": []}
    assert obj.store.writes == 0
    assert obj.ledger.reconciliations == 0
    assert obj.ledger.data == {"morphs": {}, "operations": {}}


def test_habitat_history_does_not_reconcile_advance_or_save():
    obj = manager()
    result = asyncio.run(obj.handle_habitat("history", {"morph_id": "dustdevil"}))
    assert result == {"events": []}
    assert obj.store.writes == 0
    assert obj.ledger.reconciliations == 0
    assert obj.ledger.data == {"morphs": {}, "operations": {}}


def test_get_routes_require_authentication_and_bind_exact_id():
    assert module.MorphTransferStatusView.requires_auth is True
    assert module.MorphTransferStatusView.url.endswith("/{transfer_id}")
    assert habitat_module.MorphHabitatStatusView.requires_auth is True
    assert habitat_module.MorphHabitatStatusView.url.endswith("/{morph_id}")
    assert habitat_module.MorphHabitatListView.requires_auth is True
    assert habitat_module.MorphHabitatListView.url.endswith("/list")
    assert habitat_module.MorphHabitatHistoryView.requires_auth is True
    assert habitat_module.MorphHabitatHistoryView.url.endswith("/{morph_id}")
    assert habitat_module.MorphHabitatRuntimeView.requires_auth is True
    assert habitat_module.MorphHabitatRuntimeView.url.endswith("/runtime")


def test_get_routes_use_existing_pure_status_actions():
    obj = manager()
    request = types.SimpleNamespace(app={"hass": types.SimpleNamespace(data={"morph_domain_transfer": obj})})
    transfer_view = module.MorphTransferStatusView()
    transfer_view.json = lambda payload, status_code=200: (status_code, payload)
    status, payload = asyncio.run(transfer_view.get(request, "t3"))
    assert status == 200 and payload["result"]["transfer_id"] == "t3"
    habitat_view = habitat_module.MorphHabitatStatusView()
    habitat_view.json = lambda payload, status_code=200: (status_code, payload)
    status, payload = asyncio.run(habitat_view.get(request, "dustdevil"))
    assert status == 200 and payload["result"]["morph_id"] == "dustdevil"
    list_view = habitat_module.MorphHabitatListView()
    list_view.json = lambda payload, status_code=200: (status_code, payload)
    status, payload = asyncio.run(list_view.get(request))
    assert status == 200 and payload["result"] == {"morphs": []}
    history_view = habitat_module.MorphHabitatHistoryView()
    history_view.json = lambda payload, status_code=200: (status_code, payload)
    status, payload = asyncio.run(history_view.get(request, "dustdevil"))
    assert status == 200 and payload["result"] == {"events": []}
    assert obj.store.writes == 0
    assert obj.ledger.reconciliations == 0


def test_mutation_still_reconciles_and_persists():
    obj = manager()
    result = asyncio.run(obj.handle("prepare", {"transfer_id": "t2"}))
    assert result["state"] == "PREPARED"
    assert obj.store.writes == 1
    assert obj.ledger.reconciliations == 1
    assert obj.ledger.data["expired"] is True

