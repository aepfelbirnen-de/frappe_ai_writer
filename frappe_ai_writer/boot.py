from __future__ import annotations

import re
from pathlib import Path

import frappe
from frappe.utils import cint

from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_settings.ai_writer_settings import (
    get_cover_letter_field,
    get_translation_languages,
)
from frappe_ai_writer.permissions import has_ai_writer_access

APP_NAME = "frappe_ai_writer"
LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}(-[a-z0-9]{2,8})?$", re.IGNORECASE)


def boot_session(bootinfo: frappe._dict) -> None:
    """Tell the desk client whether to show the AI button and hand over translated change logs."""
    has_access = has_ai_writer_access()
    if has_access:
        bootinfo.ai_writer = {
            "enabled": bool(cint(frappe.db.get_single_value("AI Writer Settings", "enabled", cache=True))),
            "languages": get_translation_languages(),
            "cover_letter_field": get_cover_letter_field(),
        }

    # Frappe never translates change logs, so the client swaps in these versions before the update
    # dialog opens; AI Writer users without Frappe's dialog get the app's own (see desk bundle).
    if has_access or "System Manager" in frappe.get_roles():
        bootinfo.ai_writer_change_log = {
            "title": frappe.get_hooks("app_title", app_name=APP_NAME)[0],
            "versions": get_translated_change_logs(frappe.local.lang),
        }


def get_translated_change_logs(lang: str | None) -> dict[str, str]:
    """Return {version: markdown} from change_log_i18n/<lang>/, falling back from e.g. de-CH to de."""
    if not lang or not LANGUAGE_CODE.match(lang):
        return {}

    base = Path(frappe.get_app_path(APP_NAME, "change_log_i18n"))
    for code in dict.fromkeys([lang.lower(), lang.split("-")[0].lower()]):
        folder = base / code
        if folder.is_dir():
            # Same naming as Frappe's change_log/: v0/v0_5_1.md -> "0.5.1"
            return {
                path.stem[1:].replace("_", "."): path.read_text(encoding="utf-8") for path in folder.glob("v*/v*.md")
            }
    return {}
