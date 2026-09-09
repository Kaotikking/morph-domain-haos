import importlib.util
from pathlib import Path
import sys
import unittest

MODULE = Path(__file__).parents[1] / "custom_components" / "morph_domain" / "sern.py"
SPEC = importlib.util.spec_from_file_location("morph_sern", MODULE)
sern = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = sern
SPEC.loader.exec_module(sern)


def packet():
    return {
        "schema": "sern.morph_domain.v1", "message_id": "evt-1",
        "message_type": "STATE", "morph_id": "breeze", "generation": 4,
        "cores": {name: {} for name in sern.NINE_CORES},
    }


class SernTests(unittest.TestCase):
    def test_exact_nine_core_projection(self):
        result = sern.validate_envelope(packet())
        self.assertEqual(tuple(result.cores), sern.NINE_CORES)
        self.assertEqual(len(result.digest), 64)

    def test_missing_core_fails_closed(self):
        value = packet()
        value["cores"].pop("transport")
        with self.assertRaisesRegex(sern.SernEnvelopeError, "nine ordered cores"):
            sern.validate_envelope(value)

    def test_extra_envelope_field_fails_closed(self):
        value = packet(); value["secret"] = "no"
        with self.assertRaisesRegex(sern.SernEnvelopeError, "not exact"):
            sern.validate_envelope(value)

    def test_open_transport_is_signal_only(self):
        value = packet(); value["message_type"] = "OPEN_TRANSPORT"
        self.assertEqual(sern.validate_envelope(value).message_type, "OPEN_TRANSPORT")




    def test_nonfinite_oversize_and_identity_drift_fail_closed(self):
        value = packet()
        value["cores"]["life"] = {"bad": float("inf")}
        with self.assertRaises(sern.SernEnvelopeError):
            sern.validate_envelope(value)

        value = packet()
        value["cores"]["memory"] = {"blob": "x" * sern.MAX_ENVELOPE_BYTES}
        with self.assertRaisesRegex(sern.SernEnvelopeError, "exceeds"):
            sern.validate_envelope(value)

        value = packet()
        value["cores"]["identity"] = {"morph_id": "other", "generation": 4}
        with self.assertRaisesRegex(sern.SernEnvelopeError, "does not bind"):
            sern.validate_envelope(value)

    def test_snapshot_payload_is_prohibited(self):
        value = packet()
        value["cores"]["transport"] = {"payload": {"private": "state"}}
        with self.assertRaisesRegex(sern.SernEnvelopeError, "never carry"):
            sern.validate_envelope(value)

if __name__ == "__main__":
    unittest.main()
