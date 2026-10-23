from __future__ import annotations

import frappe

AI_WRITER_ROLES = ("AI Writer Manager", "AI Writer User")
APP_SCREEN_ROLES = ("System Manager", "AI Writer Manager")


def has_ai_writer_access(user: str | None = None) -> bool:
    """Return True if the user may call the AI correction endpoint."""
    user = user or frappe.session.user
    if user == "Guest":
        return False
    return not set(AI_WRITER_ROLES).isdisjoint(frappe.get_roles(user))


def has_app_screen_access() -> bool:
    """Return True if the app tile on /apps should be shown; only managers have anything to open there."""
    return not set(APP_SCREEN_ROLES).isdisjoint(frappe.get_roles())
