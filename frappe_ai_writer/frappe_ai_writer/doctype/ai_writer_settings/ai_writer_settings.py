# Copyright (c) 2026, aepfel+birnen IT GmbH and contributors
# For license information, please see license.txt

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from frappe_ai_writer import providers

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
# The format (letter or structured) is added by api/cover_letter.py, so this prompt only holds the shared rules.
DEFAULT_COVER_LETTER_PROMPT = """You write the cover letter of a quotation. It appears in the PDF above the line items and is addressed to the customer.

- Base the content on the line items: summarize what the quotation covers and what the customer gains from it. Group related items instead of listing every item, and do not repeat quantities or item codes unless they matter.
- Never mention prices, totals, discounts or payment amounts.
- Use only the facts in the quotation data and the notes. Do not invent dates, deadlines, names, services or commitments.
- If notes are given, follow them and work their points into the letter.
- Do not add a sign-off with a name; the print format adds it.
Answer only with the letter text."""
# Default prompt of versions 0.10.x; the v0_11 patch replaces it if it was never edited.
PREVIOUS_COVER_LETTER_PROMPT = """You write the cover letter of a quotation. It appears in the PDF above the line items and is addressed to the customer.

- Start with a salutation to the contact person if one is given (e.g. "Dear Ms Miller," or "Sehr geehrte Frau Müller,"), otherwise a neutral salutation.
- Thank the customer briefly, then summarize in two to four sentences what the quotation covers and what the customer gains from it, based on the line items. Group related items instead of listing every item, and do not repeat quantities or item codes unless they matter.
- End with one sentence offering to answer questions. Do not add a sign-off with a name; the print format adds it.
- Never mention prices, totals, discounts or payment amounts.
- Use only the facts in the quotation data and the notes. Do not invent dates, deadlines, names, services or commitments.
- If notes are given, follow them and work their points into the letter.
- Keep it to roughly 80 to 180 words.
Answer only with the letter text."""
COVER_LETTER_STYLES = ("Letter", "Structured")
PREVIEW_MODES = ("Long texts", "Always", "Never")
DEFAULT_PREVIEW_MIN_CHARS = 300
DEFAULT_REPLY_PROMPT = """You write a reply to an email on behalf of the user.

- Answer the questions and requests of the incoming message in a friendly, professional tone.
- Write in the language of the incoming message.
- Use only facts from the incoming message, the document data and the notes. Do not promise dates, prices, deliveries or other commitments that are not in the notes.
- If information is missing to answer a question, say that you will check it and get back, instead of guessing.
- Start with a suitable salutation. Do not add a sign-off with a name; the signature is added separately.
- If notes are given, follow them; they take priority over everything else.
Answer only with the reply text."""
DEFAULT_SUMMARY_PROMPT = """You summarize the emails and comments of a business document for a colleague who takes it over.

Cover, as far as the conversation says anything about it:
- what the request is about
- what has been done or agreed so far
- what is still open, and who is waiting for whom

Use only facts from the conversation. Do not invent names, dates, amounts or commitments, and list open points only if the conversation shows them. If something is unclear or contradictory, say so briefly.
Refer to people by the names used in the messages. No greeting, no sign-off and no introduction such as "Here is the summary".
Answer only with the summary."""
DEFAULT_SUMMARY_DOCTYPES = ("Issue", "Opportunity", "Lead", "Quotation")
SUMMARY_STYLES = ("Bullet List", "Prose")
DEFAULT_SUMMARY_MAX_WORDS = 200
SUMMARY_WORD_RANGE = (50, 500)
DEFAULT_EXPANSION_FACTORS = (4, 10)
COVER_LETTER_FIELD_TYPES = ("Text Editor", "Small Text", "Text", "Long Text", "HTML Editor")
MAX_EXPANSION_FACTOR = 50
DEFAULT_TRANSLATION_LANGUAGES = ("de", "en")
# USD per million input and output tokens for the default model.
DEFAULT_PRICES = (0.10, 0.50)
DEFAULT_BUDGET_WARNING_THRESHOLD = 80

GLOSSARY_TRANSLATION_LINE = re.compile(r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})?\s*:\s*\S")
# Also covers Ollama tags such as "llama3.2:3b" and router names such as "mistralai/mistral-small".
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/\-]*$")


class AIWriterSettings(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_glossary_term.ai_writer_glossary_term import (
            AIWriterGlossaryTerm,
        )
        from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_summary_doctype.ai_writer_summary_doctype import (
            AIWriterSummaryDocType,
        )
        from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_translation_language.ai_writer_translation_language import (
            AIWriterTranslationLanguage,
        )

        api_key: DF.Password | None
        block_when_exceeded: DF.Check
        budget_notice: DF.SmallText | None
        budget_warning_threshold: DF.Percent
        cover_letter_field: DF.Data | None
        cover_letter_prompt: DF.SmallText | None
        cover_letter_style: DF.Literal["Letter", "Structured"]
        base_url: DF.Data | None
        effort: DF.Literal["", "low", "medium", "high"]
        enabled: DF.Check
        expand_prompt: DF.SmallText | None
        glossary: DF.Table[AIWriterGlossaryTerm]
        house_style: DF.SmallText | None
        expansion_factor_max: DF.Int
        expansion_factor_min: DF.Int
        input_price_per_million: DF.Float
        output_price_per_million: DF.Float
        preview_min_chars: DF.Int
        preview_mode: DF.Literal["Long texts", "Always", "Never"]
        provider: DF.Literal["Anthropic", "OpenAI", "Ollama", "OpenAI-compatible"]
        reply_prompt: DF.SmallText | None
        model: DF.Data | None
        monthly_budget: DF.Float
        summary_doctypes: DF.TableMultiSelect[AIWriterSummaryDocType]
        summary_max_words: DF.Int
        summary_prompt: DF.SmallText | None
        summary_style: DF.Literal["Bullet List", "Prose"]
        system_prompt: DF.SmallText | None
        track_usage_per_user: DF.Check
        user_monthly_budget: DF.Float
        translation_languages: DF.TableMultiSelect[AIWriterTranslationLanguage]
    # end: auto-generated types

    def validate(self) -> None:
        self.provider = providers.normalize_provider(self.provider)
        if self.provider == providers.ANTHROPIC:
            self.base_url = None
            self.model = (self.model or "").strip() or DEFAULT_MODEL
        else:
            self.base_url = providers.validate_base_url(
                self.base_url or providers.DEFAULT_BASE_URLS.get(self.provider, "")
            )
            self.model = (self.model or "").strip()
            if not self.model or self.model == DEFAULT_MODEL:
                frappe.throw(_("Enter the name of a model offered by {0}.").format(self.provider))
            # Effort is an Anthropic parameter.
            self.effort = ""
        if not MODEL_NAME_PATTERN.match(self.model):
            frappe.throw(_("Invalid model name: {0}").format(self.model))

        if not (self.system_prompt or "").strip():
            self.system_prompt = DEFAULT_SYSTEM_PROMPT
        if not (self.expand_prompt or "").strip():
            self.expand_prompt = DEFAULT_EXPAND_PROMPT
        if not (self.reply_prompt or "").strip():
            self.reply_prompt = DEFAULT_REPLY_PROMPT
        if not (self.cover_letter_prompt or "").strip():
            self.cover_letter_prompt = DEFAULT_COVER_LETTER_PROMPT
        if self.cover_letter_style not in COVER_LETTER_STYLES:
            self.cover_letter_style = COVER_LETTER_STYLES[0]
        self.validate_cover_letter_field()
        if self.preview_mode not in PREVIEW_MODES:
            self.preview_mode = PREVIEW_MODES[0]
        if self.preview_min_chars is None:
            self.preview_min_chars = DEFAULT_PREVIEW_MIN_CHARS

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

        if self.budget_warning_threshold is None:
            self.budget_warning_threshold = DEFAULT_BUDGET_WARNING_THRESHOLD
        if not 0 <= flt(self.budget_warning_threshold) <= 100:
            frappe.throw(_("The warning threshold must be between 0 and 100 %."))
        # Written by the budget check only; a stale value from an open form must not reset it.
        self.budget_notice = frappe.db.get_single_value(self.doctype, "budget_notice")

        self.validate_glossary()
        self.validate_summary()

        seen = set()
        for row in list(self.translation_languages):
            if row.language in seen:
                self.remove(row)
            seen.add(row.language)

    def validate_glossary(self) -> None:
        seen = set()
        for row in list(self.glossary):
            row.term = (row.term or "").strip()
            if not row.term or row.term in seen:
                self.remove(row)
                continue
            seen.add(row.term)
            for line in (row.translations or "").splitlines():
                if line.strip() and not GLOSSARY_TRANSLATION_LINE.match(line.strip()):
                    frappe.throw(
                        _("Row {0}: write translations as one line per language, e.g. en: quotation.").format(row.idx)
                    )

    def validate_summary(self) -> None:
        if not (self.summary_prompt or "").strip():
            self.summary_prompt = DEFAULT_SUMMARY_PROMPT
        if self.summary_style not in SUMMARY_STYLES:
            self.summary_style = SUMMARY_STYLES[0]
        self.summary_max_words = cint(self.summary_max_words) or DEFAULT_SUMMARY_MAX_WORDS
        if not SUMMARY_WORD_RANGE[0] <= self.summary_max_words <= SUMMARY_WORD_RANGE[1]:
            frappe.throw(_("Maximum Words must be between {0} and {1}.").format(*SUMMARY_WORD_RANGE))
        seen = set()
        for row in list(self.summary_doctypes):
            if row.document_type in seen:
                self.remove(row)
                continue
            seen.add(row.document_type)
            # Summaries need a form with a timeline.
            if frappe.get_meta(row.document_type).issingle or frappe.get_meta(row.document_type).istable:
                frappe.throw(_("{0} has no timeline to summarize.").format(_(row.document_type)))

    def set_default_summary_doctypes(self) -> None:
        """Fill the summary document types with Issue, Opportunity, Lead and Quotation where they exist."""
        for doctype in DEFAULT_SUMMARY_DOCTYPES:
            if frappe.db.exists("DocType", doctype):
                self.append("summary_doctypes", {"document_type": doctype})

    def validate_cover_letter_field(self) -> None:
        self.cover_letter_field = (self.cover_letter_field or "").strip()
        if not self.cover_letter_field:
            return
        if not frappe.db.exists("DocType", "Quotation"):
            frappe.throw(_("Cover letters need ERPNext."))
        field = frappe.get_meta("Quotation").get_field(self.cover_letter_field)
        if not field or field.fieldtype not in COVER_LETTER_FIELD_TYPES:
            frappe.throw(
                _("Field {0} does not exist on Quotation or is not a text field.").format(self.cover_letter_field)
            )

    def on_update(self) -> None:
        # The enabled flag and the translation languages are part of every user's cached boot info.
        frappe.cache.delete_key("bootinfo")

    def set_default_translation_languages(self) -> None:
        """Fill the translation languages with German and English where those Language records exist."""
        for code in DEFAULT_TRANSLATION_LANGUAGES:
            if frappe.db.exists("Language", code):
                self.append("translation_languages", {"language": code})


def get_summary_doctypes() -> list[str]:
    """Return the document types whose forms offer a conversation summary."""
    return [row.document_type for row in frappe.get_cached_doc("AI Writer Settings").summary_doctypes]


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


def get_cover_letter_field() -> str | None:
    """Return the configured Quotation cover letter field, or None when unset or ERPNext is missing."""
    fieldname = frappe.get_cached_doc("AI Writer Settings").cover_letter_field
    return fieldname if fieldname and frappe.db.exists("DocType", "Quotation") else None


def get_preview_settings() -> dict:
    """Return the preview mode and threshold for the desk client, with defaults for unset values."""
    settings = frappe.get_cached_doc("AI Writer Settings")
    mode = settings.preview_mode if settings.preview_mode in PREVIEW_MODES else PREVIEW_MODES[0]
    min_chars = DEFAULT_PREVIEW_MIN_CHARS if settings.preview_min_chars is None else cint(settings.preview_min_chars)
    return {"mode": mode, "min_chars": min_chars}
