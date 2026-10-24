from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.api.cover_letter import build_quotation_context, write_cover_letter

PRICE_MARKERS = ("4711.33", "9999.99", "1234.56")


def _quotation(**overrides) -> SimpleNamespace:
    doc = SimpleNamespace(
        name="QTN-TEST-0001",
        docstatus=0,
        company="Example Ltd",
        customer_name="Müller & Söhne GmbH",
        party_name="CUST-0001",
        contact_person=None,
        title="Server migration",
        transaction_date="2026-10-24",
        valid_till="2026-11-24",
        language="de",
        grand_total=9999.99,
        net_total=1234.56,
        items=[
            SimpleNamespace(
                item_name="Windows Server 2025",
                description="<p>Setup with Active Directory</p>",
                qty=1.0,
                uom="Nos",
                rate=4711.33,
                amount=4711.33,
            ),
            SimpleNamespace(
                item_name="FSLogix profile containers",
                description="FSLogix profile containers",
                qty=25.0,
                uom="User",
                rate=12.5,
                amount=312.5,
            ),
        ],
    )
    doc.__dict__.update(overrides)
    doc.check_permission = lambda permtype: None
    return doc


def _response(text: str) -> SimpleNamespace:
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)], usage=None)


class TestCoverLetter(FrappeTestCase):
    def setUp(self) -> None:
        frappe.set_user("Administrator")
        settings = frappe.get_single("AI Writer Settings")
        settings.update(
            {
                "enabled": 1,
                "api_key": "sk-ant-test",
                "provider": "Anthropic",
                "model": "claude-haiku-5-5",
                "cover_letter_prompt": "",
            }
        )
        settings.save()

    def test_context_contains_items_but_no_prices(self) -> None:
        context = build_quotation_context(_quotation())
        self.assertIn("Windows Server 2025 (1 Nos)", context)
        self.assertIn("Setup with Active Directory", context)
        self.assertIn("Müller & Söhne GmbH", context)
        for marker in (*PRICE_MARKERS, "312.5", "12.5"):
            self.assertNotIn(marker, context)
        # A description that only repeats the item name is left out.
        self.assertEqual(context.count("FSLogix profile containers"), 1)

    def test_requires_a_configured_field(self) -> None:
        with patch("frappe_ai_writer.api.cover_letter.get_cover_letter_field", return_value=None):
            self.assertRaises(frappe.ValidationError, write_cover_letter, "QTN-TEST-0001")

    def test_only_drafts(self) -> None:
        with (
            patch("frappe_ai_writer.api.cover_letter.get_cover_letter_field", return_value="custom_letter"),
            patch("frappe_ai_writer.api.cover_letter.frappe.get_doc", return_value=_quotation(docstatus=1)),
        ):
            self.assertRaises(frappe.ValidationError, write_cover_letter, "QTN-TEST-0001")

    def test_request_has_no_prices_and_keeps_protected_notes(self) -> None:
        with (
            patch("frappe_ai_writer.api.cover_letter.get_cover_letter_field", return_value="custom_letter"),
            patch("frappe_ai_writer.api.cover_letter.frappe.get_doc", return_value=_quotation()),
            patch("frappe_ai_writer.providers.anthropic.Anthropic") as client_cls,
        ):
            client_cls.return_value.messages.create.return_value = _response(
                "<p>Sehr geehrte Damen und Herren, ⟦P1⟧.</p>"
            )
            result = write_cover_letter("QTN-TEST-0001", notes='<p>Rahmenvertrag /"RV-2026-17"/ erwähnen</p>')
            request = client_cls.return_value.messages.create.call_args.kwargs
        message = request["messages"][0]["content"]
        for marker in PRICE_MARKERS:
            self.assertNotIn(marker, message)
        self.assertNotIn("RV-2026-17", message)
        self.assertIn("Deutsch (de)", request["system"])
        self.assertIn('/"RV-2026-17"/', result)

    def _system_prompt(self, **kwargs) -> str:
        with (
            patch("frappe_ai_writer.api.cover_letter.get_cover_letter_field", return_value="custom_letter"),
            patch("frappe_ai_writer.api.cover_letter.frappe.get_doc", return_value=_quotation()),
            patch("frappe_ai_writer.providers.anthropic.Anthropic") as client_cls,
        ):
            client_cls.return_value.messages.create.return_value = _response("<p>Text</p>")
            write_cover_letter("QTN-TEST-0001", **kwargs)
            return client_cls.return_value.messages.create.call_args.kwargs["system"]

    def test_format_letter_is_the_default(self) -> None:
        system = self._system_prompt()
        self.assertIn("Format: a classic letter", system)
        self.assertIn("Never mention prices", system)

    def test_format_structured_asks_for_headings(self) -> None:
        system = self._system_prompt(style="Structured")
        self.assertIn("<h3> for the title", system)
        self.assertNotIn("Format: a classic letter", system)

    def test_unknown_format_falls_back_to_the_setting(self) -> None:
        self.assertIn("Format: a classic letter", self._system_prompt(style="Poem"))

    def test_patch_replaces_only_the_unedited_old_prompt(self) -> None:
        from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_settings.ai_writer_settings import (
            DEFAULT_COVER_LETTER_PROMPT,
            PREVIOUS_COVER_LETTER_PROMPT,
        )
        from frappe_ai_writer.patches.v0_11.split_cover_letter_prompt import execute

        frappe.db.set_single_value("AI Writer Settings", "cover_letter_prompt", PREVIOUS_COVER_LETTER_PROMPT)
        execute()
        self.assertEqual(frappe.get_single("AI Writer Settings").cover_letter_prompt, DEFAULT_COVER_LETTER_PROMPT)

        frappe.db.set_single_value("AI Writer Settings", "cover_letter_prompt", "My own rules.")
        execute()
        self.assertEqual(frappe.get_single("AI Writer Settings").cover_letter_prompt, "My own rules.")
