from __future__ import annotations

import frappe

from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_settings.ai_writer_settings import (
    DEFAULT_COVER_LETTER_PROMPT,
    QUOTATION_COVER_LETTER_PROMPT,
)


def execute() -> None:
    settings = frappe.get_single("AI Writer Settings")
    # The old Quotation field becomes the first row of the new table; the hidden field is then emptied.
    fieldname = (settings.cover_letter_field or "").strip()
    if (
        fieldname
        and not settings.cover_letter_doctypes
        and frappe.db.exists("DocType", "Quotation")
        and frappe.get_meta("Quotation").has_field(fieldname)
    ):
        settings.append("cover_letter_doctypes", {"document_type": "Quotation", "target_field": fieldname})
    settings.cover_letter_field = None

    # The old default spoke of quotations only; it is replaced only if nobody edited it.
    if (settings.cover_letter_prompt or "").strip() == QUOTATION_COVER_LETTER_PROMPT.strip():
        settings.cover_letter_prompt = DEFAULT_COVER_LETTER_PROMPT
    settings.save()
