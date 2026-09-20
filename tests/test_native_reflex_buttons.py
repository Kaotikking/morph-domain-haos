"""Static and pure-state gates for native Morph reflex buttons."""

import ast
from pathlib import Path


ROOT = Path(__file__).parents[1]
BUTTON = ROOT / "custom_components/morph_domain/button.py"
INIT = ROOT / "custom_components/morph_domain/__init__.py"


def test_native_button_module_compiles_and_platform_is_loaded():
    ast.parse(BUTTON.read_text(encoding="utf-8"))
    init = INIT.read_text(encoding="utf-8")
    assert "Platform.BUTTON" in init
    assert '"version": "1.25.1"' in (ROOT / "custom_components/morph_domain/manifest.json").read_text(encoding="utf-8")


def test_buttons_delegate_to_proven_services_without_transfer_reimplementation():
    source = BUTTON.read_text(encoding="utf-8")
    for service in (
        "morph_place", "morph_care", "return_to_birth_frame", "recall_to_horizon",
        "code_haven_admit", "code_haven_discharge", "void_enter", "void_withdraw",
    ):
        assert service in source
    assert "return_to_frame(" not in source
    assert "recall_from_frame(" not in source
    assert "ledger" not in source
    assert "hass.services.async_call" in source


def test_button_set_is_device_bound_and_parameter_free():
    source = BUTTON.read_text(encoding="utf-8")
    assert "identifiers={(DOMAIN, self.morph_id)}" in source
    assert "Send to Birth Frame" in source
    assert "Recall to Horizon" in source
    assert "Move to Horizon" in source
    assert "Move to Gardens" in source
    assert "Feed" in source

