# Copyright (c) 2026, aepfel+birnen IT GmbH and contributors
# For license information, please see license.txt

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document

DEFAULT_MODEL = "claude-haiku-5-5"
DEFAULT_SYSTEM_PROMPT = """You are a copy editor. Correct the text you receive:
- spelling and grammar
- punctuation
- style, only where an improvement is obvious

Keep the formatting, paragraphs and line breaks.
Detect the language of the text and answer in that same language.
Answer only with the corrected text, without any explanation."""
DEFAULT_TRANSLATION_LANGUAGES = ("de", "en")

MODEL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.\-]*$")


class AIWriterSettings(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_translation_language.ai_writer_translation_language import (
            AIWriterTranslationLanguage,
        )

        api_key: DF.Password | None
        effort: DF.Literal["", "low", "medium", "high"]
        enabled: DF.Check
        model: DF.Data | None
        system_prompt: DF.SmallText | None
        translation_languages: DF.TableMultiSelect[AIWriterTranslationLanguage]
    # end: auto-generated types

    def validate(self) -> None:
        self.model = (self.model or "").strip() or DEFAULT_MODEL
        if not MODEL_NAME_PATTERN.match(self.model):
            frappe.throw(_("Invalid model name: {0}").format(self.model))

        if not (self.system_prompt or "").strip():
            self.system_prompt = DEFAULT_SYSTEM_PROMPT

        seen = set()
        for row in list(self.translation_languages):
            if row.language in seen:
                self.remove(row)
            seen.add(row.language)

    def on_update(self) -> None:
        # The enabled flag and the translation languages are part of every user's cached boot info.
        frappe.cache.delete_key("bootinfo")

    def set_default_translation_languages(self) -> None:
        """Fill the translation languages with German and English where those Language records exist."""
        for code in DEFAULT_TRANSLATION_LANGUAGES:
            if frappe.db.exists("Language", code):
                self.append("translation_languages", {"language": code})


def get_translation_languages() -> list[dict[str, str]]:
    """Return the configured target languages as [{"code": "de", "name": "Deutsch"}, ...]."""
    settings = frappe.get_cached_doc("AI Writer Settings")
    codes = [row.language for row in settings.translation_languages]
    if not codes:
        return []
    names = dict(
        frappe.get_all("Language", filters={"name": ["in", codes]}, fields=["name", "language_name"], as_list=True)
    )
    return [{"code": code, "name": names.get(code) or code} for code in codes]
