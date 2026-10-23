from __future__ import annotations

import frappe
from frappe.utils import cint

from frappe_ai_writer.permissions import has_ai_writer_access


def boot_session(bootinfo: frappe._dict) -> None:
    """Tell the desk client whether to show the AI correction button."""
    if not has_ai_writer_access():
        return
    bootinfo.ai_writer = {
        "enabled": bool(cint(frappe.db.get_single_value("AI Writer Settings", "enabled", cache=True))),
    }
