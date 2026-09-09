import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "morph_domain"


def test_hacs_layout_and_manifest():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert manifest["domain"] == "morph_domain"
    assert manifest["config_flow"] is True
    assert manifest["version"] == "1.17.0"
    assert manifest["documentation"].startswith("https://github.com/")
    assert manifest["issue_tracker"].startswith("https://github.com/")
    assert manifest["codeowners"]
    assert hacs["name"] == "MorphDomain"


def test_two_active_engines_are_denied():
    setup = (COMPONENT / "__init__.py").read_text()
    flow = (COMPONENT / "config_flow.py").read_text()
    migration = (COMPONENT / "migration.py").read_text()
    assert "legacy_engine_enabled" in setup
    assert "legacy_engine_enabled" in flow
    assert 'async_entries("serein_gateway")' in migration
    assert "entry.disabled_by is None" in migration
    assert 'reason="legacy_engine_active"' in flow


def test_migration_is_copy_only():
    source = (COMPONENT / "_vendor/morph_sdk/transfer.py").read_text()
    adapter = (COMPONENT / "morph_transfer.py").read_text()
    assert 'STORE_KEY = "morph_domain.transfer"' in source
    assert 'LEGACY_STORE_KEY = "serein_gateway.morph_transfer"' in source
    assert "deepcopy(legacy_data)" in adapter
    assert "legacy_store.async_remove" not in source + adapter


def test_routes_are_public_versioned_morphdomain_routes():
    text = (COMPONENT / "morph_transfer.py").read_text()
    text += (COMPONENT / "morph_habitat.py").read_text()
    assert 'url = "/api/morph-domain/v1/transfer/{action}"' in text
    assert 'url = "/api/morph-domain/v1/habitat/{action}"' in text
    assert 'url = "/api/morph-domain/v1/sern/validate"' in text
    assert 'action == "register-axis"' in text
    assert 'action == "advance-axis"' in text
    assert 'url = "/api/serein/' not in text


def test_gender_is_presentation_not_dna():
    readme = (ROOT / "README.md").read_text().lower()
    core = (COMPONENT / "_vendor/morph_sdk/morph_core.py").read_text().lower()
    assert "gender is mutable presentation state" in readme
    assert "gender" not in core


def test_morph_first_operator_panel_is_packaged():
    setup = (COMPONENT / "__init__.py").read_text(encoding="utf-8")
    panel = (COMPONENT / "frontend/morph-domain-panel.js").read_text(encoding="utf-8")
    assert 'frontend_url_path=PANEL_PATH' in setup
    assert 'require_admin=True' in setup
    assert 'this._hass.callApi("POST","morph-domain/v1/habitat/list",{})' in panel
    assert 'this._hass.callApi("POST","morph-domain/v1/habitat/starter-status",{})' in panel
    assert 'data-starter=' in panel
    assert 'gen1-preview' in panel
    assert 'data-confirm' in panel
    assert 'Serein or another AI is not required.' in panel
    assert 'PLACES=["VOID","NURSERY","SEREIN_GARDENS","HORIZON","CODE_HAVEN"]' in panel
    assert 'class="locations"' in panel
    assert 'class="morph-stage"' in panel



def test_dnav1_lineage_lifecycle_contract_is_packaged():
    source = (COMPONENT / "_vendor/morph_sdk/dna_v1.py").read_text()
    contract = (ROOT / "docs/DNA-V1-LIFECYCLE.md").read_text()
    assert 'LINEAGE_SCHEMA = "serein.morph-lineage-capsule.v1"' in source
    assert 'LIFECYCLE = ("SEALED", "HATCHING", "JUVENILE", "MATURE", "AWAKENED")' in source
    assert 'SOCIAL_STATES = ("UNFAMILIAR", "AWARE", "FAMILIAR", "BONDED", "RESONANT")' in source
    assert "Installation alone has no Morph-state effect" in contract


def test_morph_engine_nine_core_and_repair_reflex_are_packaged():
    engine = (COMPONENT / "_vendor/morph_engine/world_engine.py").read_text()
    core_contract = (COMPONENT / "_vendor/morph_engine/core_contract.py").read_text()
    reflex = (COMPONENT / "_vendor/morph_sdk/repair_reflex.py").read_text()
    contract = (ROOT / "docs/MORPH-ENGINE-NINE-CORE.md").read_text()
    assert 'ENGINE_SCHEMA' in engine
    assert '"platform", "root", "memory", "knowledge", "ui"' in core_contract
    assert '"audio", "personality", "modular", "cloud"' in core_contract
    assert 'world_contract": "MorphDomain"' in engine
    assert 'LEDGER_SCHEMA = "serein.morph-repair-reflex-ledger.v1"' in reflex
    assert "MorphDomain remains the five-place world" in contract
    assert "does not\nrename, replace, or fork MorphDomain" in contract


def test_dashboard_reads_do_not_own_life_advancement_or_unconditional_writes():
    adapter = (COMPONENT / "morph_transfer.py").read_text()
    policy = (COMPONENT / "http_policy.py").read_text()
    assert 'if not action_is_read("habitat", action):' in adapter
    assert 'durable_write_required("transfer", action, maintenance_changed)' in adapter
    assert "The periodic scheduler is the only owner of elapsed-life advancement." in adapter
    assert "reads persist only real maintenance changes" in policy


def test_scheduler_awaits_tick_on_home_assistant_event_loop():
    habitat = (COMPONENT / "morph_habitat.py").read_text()
    assert "async def async_tick_habitats" in habitat
    assert "await hass.data[DATA_KEY].tick_habitats()" in habitat
    assert "lambda _: hass.async_create_task" not in habitat

