from __future__ import annotations

import frappe


def execute() -> None:
    # validate() fills the token prices with their defaults.
    frappe.get_single("AI Writer Settings").save()
