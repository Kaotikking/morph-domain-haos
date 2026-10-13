"""Synthetic source/runtime guard tests; not installation admission."""
import ast
import json
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock


SOURCE = Path(__file__).resolve().parents[1] / "custom_components" / "morph_domain" / "migration.py"


def load_guard(modules):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    tree.body = [n for n in tree.body if not isinstance(n, (ast.Import, ast.ImportFrom))]
    ns = {"sys": SimpleNamespace(modules=modules), "HomeAssistant": object}
    exec(compile(tree, str(SOURCE), "exec"), ns)
    return ns["legacy_engine_enabled"], ns["LEGACY_RUNTIME_KEYS"]


class GuardCandidateTests(unittest.TestCase):
    def hass(self, enabled=True, data=None):
        return SimpleNamespace(data={} if data is None else data,
            config_entries=SimpleNamespace(async_entries=lambda domain: [
                SimpleNamespace(disabled_by=None if enabled else "user")]))

    def test_known_engine_free_gateway_can_coexist(self):
        guard, _ = load_guard({"custom_components.serein_gateway":
                              SimpleNamespace(LEGACY_MORPH_ENGINE=False)})
        self.assertFalse(guard(self.hass()))

    def test_absent_old_active_or_malformed_source_denied(self):
        for module in (None, SimpleNamespace(),
                       SimpleNamespace(LEGACY_MORPH_ENGINE=True),
                       SimpleNamespace(LEGACY_MORPH_ENGINE=0),
                       SimpleNamespace(LEGACY_MORPH_ENGINE="false")):
            guard, _ = load_guard({"custom_components.serein_gateway": module})
            self.assertTrue(guard(self.hass()))

    def test_resident_engine_denied_even_when_entry_disabled(self):
        guard, keys = load_guard({"custom_components.serein_gateway":
                                 SimpleNamespace(LEGACY_MORPH_ENGINE=False)})
        for key in keys:
            for enabled in (True, False):
                # Presence, even a false-like value, remains conflicting evidence.
                data = {key: None}
                self.assertTrue(guard(self.hass(enabled, data)))
                self.assertEqual(data, {key: None})

    def test_disabled_entry_without_resident_engine_preserves_prior_behavior(self):
        guard, _ = load_guard({})
        self.assertFalse(guard(self.hass(False)))


if __name__ == "__main__":
    unittest.main()
