from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "custom_components/morph_domain"))

from http_policy import action_requires_admin, admin_authorized


@dataclass
class User:
    is_admin: bool


def test_exact_authenticated_read_actions_do_not_require_admin():
    for action in ("status", "evidence"):
        assert action_requires_admin("transfer", action) is False
        assert admin_authorized("transfer", action, User(False)) is True
    for action in ("list", "status", "history"):
        assert action_requires_admin("habitat", action) is False
        assert admin_authorized("habitat", action, User(False)) is True


def test_every_known_mutation_requires_an_actual_admin():
    transfer = ("prepare", "migrate", "inward-bloom", "repair-element", "commit", "prepare-return", "commit-return")
    habitat = ("place", "care", "call", "presentation", "register-axis", "advance-axis")
    for surface, actions in (("transfer", transfer), ("habitat", habitat)):
        for action in actions:
            assert action_requires_admin(surface, action) is True
            assert admin_authorized(surface, action, User(False)) is False
            assert admin_authorized(surface, action, None) is False
            assert admin_authorized(surface, action, User(True)) is True


def test_unknown_surface_action_and_case_drift_fail_closed():
    for surface, action in (("transfer", "STATUS"), ("habitat", "unknown"), ("unknown", "status")):
        assert action_requires_admin(surface, action) is True
        assert admin_authorized(surface, action, User(False)) is False


def test_truthy_non_boolean_admin_claim_is_rejected():
    class ForgedUser:
        is_admin = 1

    assert admin_authorized("habitat", "care", ForgedUser()) is False
