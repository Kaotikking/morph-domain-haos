"""Static compatibility gates for the HAOS-native entity layer.

These tests deliberately avoid importing Home Assistant so the public package can
prove its registry contract in the same lightweight suite as the Morph engine.
"""

from pathlib import Path


SOURCE = (
    Path(__file__).parents[1]
    / "custom_components"
    / "morph_domain"
    / "native_entities.py"
).read_text(encoding="utf-8")


def test_devices_are_config_entry_scoped() -> None:
    assert "config_entry_id=self.entry.entry_id" in SOURCE
    assert "async_get_device_by_identifier(" in SOURCE
    assert "(DOMAIN, morph_id), self.entry.entry_id" in SOURCE
    assert "async_get_device(identifiers=" not in SOURCE


def test_device_is_registered_before_dynamic_entities_are_added() -> None:
    register = SOURCE.index("device_registry.async_get_or_create(")
    add_entities = SOURCE.index("self.add(new_entities, True)")
    assert register < add_entities


def test_canonical_places_use_the_public_area_registry_contract() -> None:
    assert "area_registry.async_get_or_create(name)" in SOURCE
    assert "PLACE_AREAS.values()" in SOURCE


def test_all_nine_cores_are_projected_under_each_virtual_device() -> None:
    assert "for core in CORE_ORDER" in SOURCE
    assert 'f"core_{core_name}"' in SOURCE

