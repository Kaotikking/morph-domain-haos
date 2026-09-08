from copy import deepcopy
from datetime import UTC, datetime, timedelta
import importlib.util
from pathlib import Path


MODULE = Path(__file__).parents[1] / "custom_components/morph_domain/_vendor/morph_sdk/transfer.py"
spec = importlib.util.spec_from_file_location("morph_transfer_legacy_compat", MODULE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_reconcile_expired_preserves_legacy_operation_without_state():
    now = datetime(2026, 9, 8, tzinfo=UTC)
    legacy = {
        "operation_kind": "MORPH_CORE_MIGRATION",
        "migration_id": "legacy-migration-1",
        "morph_id": "dustdevil",
        "completion_receipt": {"authority": "HAOS"},
    }
    expired = {
        "state": "PREPARED",
        "expires_at": (now - timedelta(seconds=1)).isoformat(),
    }
    ledger = module.MorphTransferLedger({
        "schema": module.API_SCHEMA,
        "morphs": {},
        "operations": {
            "legacy-migration-1": deepcopy(legacy),
            "expired-live-transfer": expired,
        },
    })

    assert ledger.reconcile_expired(now) is True
    assert ledger.data["operations"]["legacy-migration-1"] == legacy
    assert ledger.data["operations"]["expired-live-transfer"]["state"] == "EXPIRED"
    assert ledger.data["morphs"] == {}
