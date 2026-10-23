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

MODEL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9.\-]*$")


class AIWriterSettings(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        api_key: DF.Password | None
        effort: DF.Literal["", "low", "medium", "high"]
        enabled: DF.Check
        model: DF.Data | None
        system_prompt: DF.SmallText | None
    # end: auto-generated types

    def validate(self) -> None:
        self.model = (self.model or "").strip() or DEFAULT_MODEL
        if not MODEL_NAME_PATTERN.match(self.model):
            frappe.throw(_("Invalid model name: {0}").format(self.model))

        if not (self.system_prompt or "").strip():
            self.system_prompt = DEFAULT_SYSTEM_PROMPT
