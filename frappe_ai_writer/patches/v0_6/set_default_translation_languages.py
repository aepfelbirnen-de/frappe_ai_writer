from __future__ import annotations

import frappe


def execute() -> None:
    settings = frappe.get_single("AI Writer Settings")
    if settings.translation_languages:
        return
    settings.set_default_translation_languages()
    settings.save()
