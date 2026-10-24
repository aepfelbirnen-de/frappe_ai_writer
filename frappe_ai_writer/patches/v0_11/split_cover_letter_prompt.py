from __future__ import annotations

import frappe

from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_settings.ai_writer_settings import (
    DEFAULT_COVER_LETTER_PROMPT,
    PREVIOUS_COVER_LETTER_PROMPT,
)


def execute() -> None:
    # The old default also fixed the letter format; it is replaced only if nobody edited it.
    settings = frappe.get_single("AI Writer Settings")
    if (settings.cover_letter_prompt or "").strip() == PREVIOUS_COVER_LETTER_PROMPT.strip():
        settings.cover_letter_prompt = DEFAULT_COVER_LETTER_PROMPT
    settings.save()
