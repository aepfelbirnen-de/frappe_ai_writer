from __future__ import annotations

import frappe


def execute() -> None:
    # validate() fills the cover letter prompt with its default.
    frappe.get_single("AI Writer Settings").save()
