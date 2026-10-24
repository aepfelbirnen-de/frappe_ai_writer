from __future__ import annotations

import frappe


def execute() -> None:
    # validate() fills prompt, format and length with their defaults.
    settings = frappe.get_single("AI Writer Settings")
    if not settings.summary_doctypes:
        settings.set_default_summary_doctypes()
    settings.save()
