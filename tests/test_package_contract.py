import json
from pathlib import Path

ROOT = Path(__file__).parents[1]
COMPONENT = ROOT / "custom_components" / "morph_domain"


def test_hacs_layout_and_manifest():
    manifest = json.loads((COMPONENT / "manifest.json").read_text())
    hacs = json.loads((ROOT / "hacs.json").read_text())
    assert manifest["domain"] == "morph_domain"
    assert manifest["config_flow"] is True
    assert manifest["version"] == "1.6.0"
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
    assert 'hass.callApi("POST", "morph-domain/v1/habitat/list", {})' in panel
    assert 'PLACES=["VOID","NURSERY","SEREIN_GARDENS","HORIZON","CODE_HAVEN"]' in panel
    assert 'class="locations"' in panel
    assert 'class="morph-stage"' in panel

