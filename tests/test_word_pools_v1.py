import importlib.util
from pathlib import Path

PATH = Path(__file__).parents[1] / "custom_components/morph_domain/_vendor/morph_sdk/word_pools_v1.py"
spec = importlib.util.spec_from_file_location("word_pools_v1_test", PATH)
words = importlib.util.module_from_spec(spec)
spec.loader.exec_module(words)


def test_four_elements_have_exactly_three_populated_append_only_pools():
    assert set(words.WORD_POOLS) == {"FIRE", "AIR", "EARTH", "WATER"}
    for element, pools in words.WORD_POOLS.items():
        assert set(pools) == {"A", "B", "C"}
        assert len(pools["A"]) == 20
        assert len(pools["B"]) == 10
        assert len(pools["C"]) == 10
        for family, values in pools.items():
            assert len(values) == len(set(values)), (element, family)
            assert all(value and value.isprintable() for value in values)


def test_hatch_name_is_stable_and_element_bound():
    first = words.hatch_name(morph_id="morph-1", genome_sha256="a" * 64, element="WATER")
    assert first == words.hatch_name(morph_id="morph-1", genome_sha256="a" * 64, element="WATER")
    assert first in words.pool("WATER", "A")
    assert words.hatch_name(morph_id="morph-1", genome_sha256="a" * 64, element="FIRE") in words.pool("FIRE", "A")

