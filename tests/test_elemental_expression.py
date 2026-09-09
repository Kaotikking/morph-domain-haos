from copy import deepcopy
import sys
from pathlib import Path
import unittest

SDK_PATH = Path(__file__).resolve().parents[1] / "custom_components" / "morph_domain" / "_vendor" / "morph_sdk"
sys.path.insert(0, str(SDK_PATH))

import elemental_expression as e


def sample(generation=0):
    parents = [] if generation == 0 else ["parent:a", "parent:b"]
    return parents, {
        "schema": e.EXPRESSION_SCHEMA,
        "dominant_primitive": "AIR",
        "secondary_primitive": None,
        "recessive_potentials": ["ELECTRICITY"],
        "parent_locus_contributions": {} if generation == 0 else {p: 5 for p in parents},
        "expression_level": 2,
        "compound_family": None,
        "visual_expression": "wind-trail",
        "environment_selector": "weather.sunny",
        "body_mode": "floating",
        "body_mode_lock": {"locked_mode": None, "replacement_mode": None, "reason": None},
        "origin_binding_digest": "a" * 64,
    }


class ElementalExpressionTests(unittest.TestCase):
    def test_generation_zero_and_descendant_50_50(self):
        parents, value = sample()
        self.assertEqual(e.validate_expression(value, generation=0, parent_ids=parents), value)
        parents, value = sample(1)
        self.assertEqual(e.validate_expression(value, generation=1, parent_ids=parents), value)

    def test_air_water_storm_only_at_compound_tier(self):
        self.assertIsNone(e.resolve_compound(["AIR", "WATER"], 3))
        self.assertEqual(e.resolve_compound(["AIR", "WATER"], 4), "STORM")

    def test_all_six_unordered_primitive_pairs_are_admitted(self):
        expected = {
            frozenset(("FIRE", "AIR")): "PLASMA",
            frozenset(("FIRE", "EARTH")): "MAGMA",
            frozenset(("FIRE", "WATER")): "STEAM",
            frozenset(("AIR", "EARTH")): "DUST",
            frozenset(("AIR", "WATER")): "STORM",
            frozenset(("EARTH", "WATER")): "VERDURE",
        }
        self.assertEqual(e.COMPOUNDS, expected)
        for pair, family in expected.items():
            self.assertEqual(e.resolve_compound(list(pair), 4), family)

    def test_lineage_and_expression_cannot_regress(self):
        parents, old = sample()
        new = deepcopy(old)
        new["expression_level"] = 1
        with self.assertRaises(e.ElementalExpressionError) as raised:
            e.verify_expression_successor(old, new, generation=0, parent_ids=parents)
        self.assertEqual(raised.exception.code, "EXPRESSION_REGRESSION")


if __name__ == "__main__":
    unittest.main()

