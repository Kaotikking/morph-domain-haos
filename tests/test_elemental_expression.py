from copy import deepcopy
import elemental_expression as e


def sample(generation=0):
    parents = [] if generation == 0 else ["parent:a", "parent:b"]
    return parents, {"schema": e.EXPRESSION_SCHEMA, "dominant_primitive": "AIR",
        "secondary_primitive": None, "recessive_potentials": ["ELECTRICITY"],
        "parent_locus_contributions": {} if generation == 0 else {p: 5 for p in parents},
        "expression_level": 2, "compound_family": None, "visual_expression": "wind-trail",
        "environment_selector": "weather.sunny", "body_mode": "floating",
        "body_mode_lock": {"locked_mode": None, "replacement_mode": None, "reason": None},
        "origin_binding_digest": "a" * 64}


def test_generation_zero_and_descendant_50_50():
    p, v = sample(); assert e.validate_expression(v, generation=0, parent_ids=p) == v
    p, v = sample(1); assert e.validate_expression(v, generation=1, parent_ids=p) == v


def test_air_water_storm_only_at_compound_tier():
    assert e.resolve_compound(["AIR", "WATER"], 3) is None
    assert e.resolve_compound(["AIR", "WATER"], 4) == "STORM"


def test_unknown_pairing_fails_closed():
    try: e.resolve_compound(["FIRE", "EARTH"], 4)
    except e.ElementalExpressionError as ex: assert ex.code == "UNADMITTED_COMPOUND"
    else: raise AssertionError("unadmitted compound accepted")


def test_lineage_and_expression_cannot_regress():
    p, old = sample(); new = deepcopy(old); new["expression_level"] = 1
    try: e.verify_expression_successor(old, new, generation=0, parent_ids=p)
    except e.ElementalExpressionError as ex: assert ex.code == "EXPRESSION_REGRESSION"
    else: raise AssertionError("regression accepted")

