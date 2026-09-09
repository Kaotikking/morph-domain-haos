import json
from pathlib import Path
import pytest

from package_registry_v1 import *


def envelope(kind, suffix, payload):
    return {
        "schema": "serein.morph-package.v1",
        "package_id": f"PKG-{kind}-{suffix}@1.0.0",
        "kind": kind,
        "compatibility": {"engine_major": 1},
        "payload": payload,
        "fallback": "SEREIN-CANONICAL-FALLBACK",
        "fixtures": ["fixture-1"],
    }


def founder(element="04", name="Pulse"):
    return envelope("FOUNDER", f"{element}-{name.upper()}", {
        "element_id": element, "founder_id": f"F-{element}",
        "public_lineage_id": f"E-{element}", "starter_id": f"L1-{element}",
        "name": name, "primary": ELEMENTS[element], "recessive": "SOUND",
        "signature": "ORIGIN_FRAGMENT", "word_pools": ["A", "B", "C"],
        "palette": "PAL-04", "catalysts": ["CARE", "WEATHER"],
    })


def evolution(form="FORM-04-SONIC_CURRENT", required=None, catalysts=None):
    return envelope("EVOLUTION", form, {
        "form_id": form, "class": "RESONANCE", "lineages": ["E-04", "F-04", "L1-04"],
        "evidence": required or {"RELATIONSHIP": 4, "FRAME": 4},
        "catalysts": catalysts or ["VOICE_RESONANCE"], "capabilities": ["PROJECTION"],
        "stability": "CONDITIONAL", "reversion": "CONTEXT_END",
        "presentation_id": "PRES-04-SONIC_CURRENT", "exclusions": ["BATTLE"],
    })


def presentation(form="FORM-04-SONIC_CURRENT"):
    return envelope("PRESENTATION", "04-SONIC_CURRENT", {
        "presentation_id": "PRES-04-SONIC_CURRENT", "forms": [form],
        "capability_tiers": [1, 2, 3, 4, 5], "silhouette": "WAVE",
        "palette": ["WATER", "SOUND"], "effects": ["RIPPLE"], "animations": ["CALL"],
        "voice": ["RESONANCE"], "localization": {"en": "Sonic Current"},
        "accessibility": {"reduced_motion": True}, "frame_profiles": {"SERN-LOW": "PIXEL", "ANDROID": "VECTOR"},
    })


def test_existing_founders_share_element_ids_without_duplicate_lineages():
    registry = json.loads((Path(__file__).parent / "gen1-package-registry-v1.json").read_text())
    assert [row["founder_id"] for row in registry["founders"]] == ["F-01", "F-02", "F-03", "F-04"]
    assert all(row["public_lineage_id"][2:] == row["founder_id"][2:] == row["starter_id"][3:] for row in registry["founders"])


def test_new_founder_is_drop_in_after_element_registration(monkeypatch):
    monkeypatch.setitem(ELEMENTS, "05", "GRAVITY")
    assert validate_package(founder("05", "Orbit"))["payload"]["founder_id"] == "F-05"


def test_evolution_is_graph_eligibility_not_a_linear_rank():
    packages = admit_packages([evolution()])
    assert eligible_forms(lineage_ids={"E-04"}, evidence={"RELATIONSHIP": 4, "FRAME": 4},
                          catalysts={"VOICE_RESONANCE"}, packages=packages) == ("FORM-04-SONIC_CURRENT",)
    assert eligible_forms(lineage_ids={"E-04"}, evidence={"RELATIONSHIP": 3, "FRAME": 5},
                          catalysts={"VOICE_RESONANCE"}, packages=packages) == ()


def test_expression_is_not_used_as_evolution_evidence():
    with pytest.raises(ValueError):
        eligible_forms(lineage_ids={"E-04"}, evidence={"EXPRESSION": 5},
                       catalysts=set(), packages=admit_packages([evolution(catalysts=[])]))


def test_presentation_is_drop_in_and_degrades_to_sern_low():
    packages = admit_packages([presentation()])
    assert select_presentation(form_id="FORM-04-SONIC_CURRENT", frame_profile="GPU", packages=packages) == {
        "presentation_id": "PRES-04-SONIC_CURRENT", "frame_profile": "SERN-LOW"}


def test_future_evolution_classes_are_reserved_but_inactive():
    package = evolution()
    package["payload"]["class"] = "FRAME_ARMOR"
    with pytest.raises(ValueError): validate_package(package)


def test_invalid_or_duplicate_packages_fail_closed():
    package = founder()
    with pytest.raises(ValueError): admit_packages([package, package])
    broken = founder(); broken["payload"]["founder_id"] = "F-99"
    with pytest.raises(ValueError): validate_package(broken)


def test_package_digest_is_order_independent():
    package = founder()
    assert canonical_digest(package) == canonical_digest(dict(reversed(list(package.items()))))


def test_all_public_schemas_are_valid_json_and_fail_closed():
    for kind in ("founder", "evolution", "presentation"):
        schema = json.loads((Path(__file__).parent / f"{kind}-package-v1.schema.json").read_text())
        assert schema["additionalProperties"] is False
        assert schema["properties"]["kind"]["const"] == kind.upper()
        assert schema["properties"]["fixtures"]["minItems"] == 1

