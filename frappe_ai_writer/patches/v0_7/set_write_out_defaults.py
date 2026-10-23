from __future__ import annotations

import frappe


def execute() -> None:
    # validate() fills the write-out prompt and the expansion factors with their defaults.
    frappe.get_single("AI Writer Settings").save()
