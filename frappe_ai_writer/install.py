from __future__ import annotations

import frappe

from frappe_ai_writer.permissions import AI_WRITER_ROLES


def before_install() -> None:
    # DocType permissions reference these roles, so they must exist before the DocTypes sync.
    ensure_roles()


def after_install() -> None:
    ensure_roles()
    # Saving runs the controller's validate(), which fills in model and system prompt defaults.
    frappe.get_single("AI Writer Settings").save()


def after_migrate() -> None:
    ensure_roles()


def ensure_roles() -> None:
    for role in AI_WRITER_ROLES:
        if not frappe.db.exists("Role", role):
            frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert()
