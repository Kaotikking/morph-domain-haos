import json
from pathlib import Path
import pytest

from package_registry_v1 import *


def envelope(kind, suffix, payload):
    package = {
        "schema": "serein.morph-package.v1",
        "package_id": f"PKG-{kind}-{suffix}@1.0.0",
        "kind": kind,
        "compatibility": {"engine_major": 1},
        "payload": payload,
        "fallback": "SEREIN-CANONICAL-FALLBACK",
        "fixtures": ["fixture-1"],
    }
    package["content_digest"] = package_content_digest(package)
    return package


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
    registry = json.loads((Path(__file__).parents[1] / "fixtures" / "gen1-package-registry-v1.json").read_text())
    assert [row["founder_id"] for row in registry["founders"]] == ["F-01", "F-02", "F-03", "F-04"]
    assert all(row["public_lineage_id"][2:] == row["founder_id"][2:] == row["starter_id"][3:] for row in registry["founders"])


def test_new_founder_is_drop_in_after_element_registration(monkeypatch):
    monkeypatch.setitem(ELEMENTS, "05", "GRAVITY")
    assert validate_package(founder("05", "Orbit"))["payload"]["founder_id"] == "F-05"
    future = evolution("FORM-05-NATURAL-A")
    future["payload"]["lineages"] = ["E-05", "F-05", "L1-05"]
    future["content_digest"] = package_content_digest(future)
    assert validate_package(future)["payload"]["form_id"] == "FORM-05-NATURAL-A"


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


def test_package_content_digest_is_required_and_tamper_evident():
    package = founder()
    assert validate_package(package) == package
    package["payload"]["name"] = "Changed"
    with pytest.raises(ValueError, match="digest mismatch"):
        validate_package(package)


def test_all_public_schemas_are_valid_json_and_fail_closed():
    for kind in ("founder", "evolution", "presentation"):
        schema = json.loads((Path(__file__).parents[1] / "schemas" / f"{kind}-package-v1.schema.json").read_text())
        assert schema["additionalProperties"] is False
        assert schema["properties"]["kind"]["const"] == kind.upper()
        assert schema["properties"]["fixtures"]["minItems"] == 1
        assert "content_digest" in schema["required"]
        assert schema["properties"]["compatibility"]["additionalProperties"] is False
        payload = schema["properties"]["payload"]
        assert set(payload["properties"]) == set(payload["required"])


def test_all_gen1_builtins_are_admitted_and_branch_each_element():
    raw = json.loads((Path(__file__).parents[1] / "fixtures" / "gen1-built-in-packages-v1.json").read_text())
    admitted = admit_packages(raw["packages"])
    assert len([p for p in admitted.values() if p["kind"] == "FOUNDER"]) == 4
    assert len([p for p in admitted.values() if p["kind"] == "EVOLUTION"]) == 16
    for element in ELEMENTS:
        classes = {p["payload"]["class"] for p in admitted.values()
                   if p["kind"] == "EVOLUTION" and p["payload"]["form_id"].startswith(f"FORM-{element}-")}
        assert classes == set(EVOLUTION_CLASSES)


def test_cross_platform_fixture_preserves_truth_and_allows_presentation_difference():
    raw = json.loads((Path(__file__).parents[1] / "fixtures" / "gen1-built-in-packages-v1.json").read_text())
    fixture = json.loads((Path(__file__).parents[1] / "fixtures" / "gen1-cross-platform-v1.json").read_text())
    admitted = admit_packages(raw["packages"])
    snapshot = fixture["snapshot"]
    forms = eligible_forms(lineage_ids=set(snapshot["lineage_ids"]), evidence=snapshot["evidence"],
                           catalysts=set(snapshot["catalysts"]), packages=admitted)
    assert list(forms) == fixture["expected"]["eligible_forms"]
    assert fixture["expected"]["active_owner_count"] == 1
    low = select_presentation(form_id=forms[0], frame_profile="SERN-LOW", packages=admitted)
    rich = select_presentation(form_id=forms[0], frame_profile="ANDROID", packages=admitted)
    assert low["presentation_id"] == rich["presentation_id"]
    assert low["frame_profile"] != rich["frame_profile"]


def test_all_evolutions_bind_an_admitted_presentation():
    raw = json.loads((Path(__file__).parents[1] / "fixtures" / "gen1-built-in-packages-v1.json").read_text())
    assert len(admit_packages(raw["packages"])) == len(raw["packages"])


def test_nine_core_lore_projection_is_complete_and_one_to_one():
    assert set(MORPH_CORE_LORE_FACETS) == set(MORPH_CORES)
    assert set(MORPH_CORE_LORE_FACETS.values()) == {
        "identity", "lineage", "life", "expression", "capability",
        "relationship", "memory", "presentation", "authority",
    }


def test_state_transition_requires_trinity_ump_receipt_envelope():
    valid = {
        "who": "HAOS_ADMIN", "what": "PACKAGE_ADOPTION", "when": "2026-09-09T21:00:00Z",
        "where": "CODE_HAVEN", "how": "MORPH_DOMAIN_API", "authority_ref": "OPERATOR_BOUND",
        "predecessor_digest": "a" * 64, "rollback": "RESTORE_PREDECESSOR",
        "receipt_id": "receipt-1",
    }
    assert validate_transition_envelope(valid) == valid
    for missing in valid:
        broken = dict(valid)
        broken.pop(missing)
        with pytest.raises(ValueError):
            validate_transition_envelope(broken)


