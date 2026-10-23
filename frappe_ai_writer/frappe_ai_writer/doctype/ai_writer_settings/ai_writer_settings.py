# Copyright (c) 2026, aepfel+birnen IT GmbH and contributors
# For license information, please see license.txt

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

DEFAULT_MODEL = "claude-haiku-5-5"
DEFAULT_SYSTEM_PROMPT = """You are a copy editor. Correct the text you receive:
- spelling and grammar
- punctuation
- style, only where an improvement is obvious

Keep the formatting, paragraphs and line breaks.
Detect the language of the text and answer in that same language.
Answer only with the corrected text, without any explanation."""
# Writing out notes conflicts with the correction prompt ("keep the formatting"), so it has its own prompt.
DEFAULT_EXPAND_PROMPT = """You turn notes into well-written, detailed text.

The input consists of notes, keywords or bullet points. Write them out as coherent prose in the language of the notes:
- complete sentences, connected into one or more paragraphs
- related points merged into flowing sentences instead of one sentence per bullet
- one paragraph per topic; no bullet list in the answer

Elaborate so that a reader without background knowledge understands the text: explain what technical terms and abbreviations mean, why a step matters and what it usually involves.

Keep every specific detail from the notes, such as product names, versions, numbers and names, for example "Server 2025" stays "Server 2025"; you may complete an obvious product name such as "Windows Server 2025".

Add general, factual background only, and phrase it as background, not as part of the plan: write "is often based on" or "typically includes", and never state that a particular standard, tool, method or step will be used unless the notes say so. Do not invent specifics about the situation: no names, dates, deadlines, figures, customers, decisions, commitments or case-specific reasons that the notes do not contain, and no greeting or sign-off that the notes do not contain.
Answer only with the written text, without any explanation.

Example notes:
- migrate mailboxes to M365
- MFA for all users

Example answer:
The existing mailboxes will be migrated to Microsoft 365, so that email, calendars and contacts are available in the cloud and no longer depend on the local mail server. In addition, multi-factor authentication (MFA) will be enabled for all users: besides their password, they confirm each sign-in with a second factor such as an authenticator app, which considerably reduces the risk of compromised accounts."""
DEFAULT_EXPANSION_FACTORS = (4, 10)
MAX_EXPANSION_FACTOR = 50
DEFAULT_TRANSLATION_LANGUAGES = ("de", "en")
# USD per million input and output tokens for the default model.
DEFAULT_PRICES = (0.10, 0.50)

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
        expand_prompt: DF.SmallText | None
        expansion_factor_max: DF.Int
        expansion_factor_min: DF.Int
        input_price_per_million: DF.Float
        output_price_per_million: DF.Float
        model: DF.Data | None
        system_prompt: DF.SmallText | None
        track_usage_per_user: DF.Check
        translation_languages: DF.TableMultiSelect[AIWriterTranslationLanguage]
    # end: auto-generated types

    def validate(self) -> None:
        self.model = (self.model or "").strip() or DEFAULT_MODEL
        if not MODEL_NAME_PATTERN.match(self.model):
            frappe.throw(_("Invalid model name: {0}").format(self.model))

        if not (self.system_prompt or "").strip():
            self.system_prompt = DEFAULT_SYSTEM_PROMPT
        if not (self.expand_prompt or "").strip():
            self.expand_prompt = DEFAULT_EXPAND_PROMPT

        self.expansion_factor_min = cint(self.expansion_factor_min) or DEFAULT_EXPANSION_FACTORS[0]
        self.expansion_factor_max = cint(self.expansion_factor_max) or DEFAULT_EXPANSION_FACTORS[1]
        if (
            not 1 <= self.expansion_factor_min <= MAX_EXPANSION_FACTOR
            or not 1 <= self.expansion_factor_max <= MAX_EXPANSION_FACTOR
        ):
            frappe.throw(_("Expansion factors must be between 1 and {0}.").format(MAX_EXPANSION_FACTOR))
        if self.expansion_factor_max < self.expansion_factor_min:
            frappe.throw(_("The maximum expansion factor must be at least the minimum."))

        if self.input_price_per_million is None:
            self.input_price_per_million = DEFAULT_PRICES[0]
        if self.output_price_per_million is None:
            self.output_price_per_million = DEFAULT_PRICES[1]

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


def get_expansion_factors(settings: Document) -> tuple[int, int]:
    """Return (minimum, maximum) expansion factor, falling back to the defaults for unset values."""
    low = cint(settings.expansion_factor_min) or DEFAULT_EXPANSION_FACTORS[0]
    high = cint(settings.expansion_factor_max) or DEFAULT_EXPANSION_FACTORS[1]
    return low, max(low, high)
