"""Fail-closed HTTP authority policy for MorphDomain."""

from __future__ import annotations

from typing import Any

TRANSFER_READ_ACTIONS = frozenset({"status", "evidence"})
HABITAT_READ_ACTIONS = frozenset({"list", "status", "history"})
_READ_ACTIONS = {
    "transfer": TRANSFER_READ_ACTIONS,
    "habitat": HABITAT_READ_ACTIONS,
}


def action_requires_admin(surface: str, action: str) -> bool:
    """Return False only for exact admitted read actions."""
    return action not in _READ_ACTIONS.get(surface, frozenset())


def admin_authorized(surface: str, action: str, user: Any) -> bool:
    """Fail closed for mutations, unknown surfaces/actions, and missing users."""
    if not action_requires_admin(surface, action):
        return True
    return user is not None and getattr(user, "is_admin", False) is True
