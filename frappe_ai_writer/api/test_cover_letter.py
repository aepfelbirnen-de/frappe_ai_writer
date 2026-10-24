from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.api.cover_letter import build_context, write_cover_letter

PRICE_MARKERS = ("4711.33", "4.711,33", "9999.99", "9.999,99")


def _quotation(**overrides) -> frappe._dict:
    doc = frappe._dict(
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
        currency="EUR",
        grand_total=9999.99,
        items=[
            frappe._dict(
                item_name="Windows Server 2025",
                description="<p>Setup with Active Directory</p>",
                qty=1.0,
                uom="Nos",
                amount=4711.33,
            ),
            frappe._dict(
                item_name="FSLogix profile containers",
                description="FSLogix profile containers",
                qty=25.0,
                uom="User",
                amount=312.5,
            ),
        ],
    )
    doc.update(overrides)
    doc.check_permission = lambda permtype: None
    return doc


def _dunning(**overrides) -> frappe._dict:
    doc = frappe._dict(
        name="DUNN-TEST-0001",
        docstatus=0,
        company="Example Ltd",
        customer="CUST-0001",
        customer_name="Müller & Söhne GmbH",
        contact_person=None,
        posting_date="2026-10-24",
        dunning_type="First reminder",
        language="de",
        currency="EUR",
        total_outstanding=4711.33,
        dunning_fee=5.0,
        grand_total=4716.33,
        overdue_payments=[
            frappe._dict(
                sales_invoice="ACC-SINV-2026-00042", due_date="2026-09-30", overdue_days="24", outstanding=4711.33
            )
        ],
    )
    doc.update(overrides)
    doc.check_permission = lambda permtype: None
    return doc


def _config(document_type: str = "Quotation", send_amounts: int = 0, prompt: str = "") -> frappe._dict:
    return frappe._dict(
        document_type=document_type, target_field="custom_letter", send_amounts=send_amounts, prompt=prompt
    )


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
                "cover_letter_style": "Letter",
                "monthly_budget": 0,
                "glossary": [],
                "house_style": "",
            }
        )
        settings.save()

    def _request(self, doc=None, config=None, **kwargs) -> tuple[str, dict]:
        doc = doc or _quotation()
        config = config or _config()
        with (
            patch("frappe_ai_writer.api.cover_letter.get_cover_letter_config", return_value=config),
            patch("frappe_ai_writer.api.cover_letter.frappe.get_doc", return_value=doc),
            patch("frappe_ai_writer.providers.anthropic.Anthropic") as client_cls,
        ):
            client_cls.return_value.messages.create.return_value = _response(kwargs.pop("answer", "<p>Text</p>"))
            result = write_cover_letter(config.document_type, doc.name, **kwargs)
            return result, client_cls.return_value.messages.create.call_args.kwargs

    def test_context_contains_items_but_no_prices(self) -> None:
        context = build_context(_quotation(), "Quotation")
        self.assertIn("Windows Server 2025 (1 Nos)", context)
        self.assertIn("Setup with Active Directory", context)
        self.assertIn("Müller & Söhne GmbH", context)
        for marker in (*PRICE_MARKERS, "312.5", "312,5"):
            self.assertNotIn(marker, context)
        # A description that only repeats the item name is left out.
        self.assertEqual(context.count("FSLogix profile containers"), 1)

    def test_context_contains_amounts_only_when_allowed(self) -> None:
        context = build_context(_quotation(), "Quotation", send_amounts=True)
        self.assertIn("Grand total:", context)
        self.assertIn("amount", context)

    def test_context_builders_per_document_type(self) -> None:
        order = build_context(
            _quotation(delivery_date="2026-11-30", po_no="PO-77", po_date="2026-10-20"), "Sales Order"
        )
        self.assertIn("Document type: Sales Order", order)
        self.assertIn("Planned delivery date:", order)
        self.assertIn("Customer's purchase order: PO-77", order)
        self.assertNotIn("Valid until", order)

        delivery = build_context(_quotation(posting_date="2026-10-24", transporter_name="DHL"), "Delivery Note")
        self.assertIn("Delivery date:", delivery)
        self.assertIn("Carrier: DHL", delivery)

        invoice = build_context(
            _quotation(posting_date="2026-10-24", due_date="2026-11-07", outstanding_amount=9999.99), "Sales Invoice"
        )
        self.assertIn("Due date:", invoice)
        self.assertNotIn("Outstanding amount", invoice)
        self.assertIn("Outstanding amount", build_context(_quotation(outstanding_amount=1.0), "Sales Invoice", True))

    def test_dunning_context_lists_overdue_invoices(self) -> None:
        context = build_context(_dunning(), "Dunning")
        self.assertIn("Invoice ACC-SINV-2026-00042", context)
        self.assertIn("24 days overdue", context)
        self.assertIn("Dunning level: First reminder", context)
        for marker in PRICE_MARKERS:
            self.assertNotIn(marker, context)
        with_amounts = build_context(_dunning(), "Dunning", send_amounts=True)
        self.assertIn("outstanding", with_amounts)
        self.assertIn("Dunning fee:", with_amounts)

    def test_requires_a_configured_document_type(self) -> None:
        with patch("frappe_ai_writer.api.cover_letter.get_cover_letter_config", return_value=None):
            self.assertRaises(frappe.ValidationError, write_cover_letter, "Quotation", "QTN-TEST-0001")

    def test_only_drafts(self) -> None:
        self.assertRaises(frappe.ValidationError, self._request, doc=_quotation(docstatus=1))

    def test_old_clients_send_only_the_quotation(self) -> None:
        with (
            patch("frappe_ai_writer.api.cover_letter.get_cover_letter_config", return_value=_config()) as config,
            patch("frappe_ai_writer.api.cover_letter.frappe.get_doc", return_value=_quotation()),
            patch("frappe_ai_writer.providers.anthropic.Anthropic") as client_cls,
        ):
            client_cls.return_value.messages.create.return_value = _response("<p>Text</p>")
            write_cover_letter(quotation="QTN-TEST-0001")
        config.assert_called_once_with("Quotation")

    def test_request_has_no_prices_and_keeps_protected_notes(self) -> None:
        result, request = self._request(
            notes='<p>Rahmenvertrag /"RV-2026-17"/ erwähnen</p>',
            answer="<p>Sehr geehrte Damen und Herren, ⟦P1⟧.</p>",
        )
        message = request["messages"][0]["content"]
        for marker in PRICE_MARKERS:
            self.assertNotIn(marker, message)
        self.assertNotIn("RV-2026-17", message)
        self.assertIn("Deutsch (de)", request["system"])
        self.assertIn("never mention any", request["system"])
        self.assertIn('/"RV-2026-17"/', result)

    def test_amounts_are_sent_where_allowed(self) -> None:
        _, request = self._request(config=_config(send_amounts=1))
        self.assertIn("Grand total:", request["messages"][0]["content"])
        self.assertNotIn("never mention any", request["system"])

    def test_purpose_defaults_per_document_type_and_can_be_overridden(self) -> None:
        _, request = self._request(config=_config("Sales Order"))
        self.assertIn("order confirmation", request["system"])
        _, request = self._request(config=_config("Sales Order", prompt="Mention our new service hotline."))
        self.assertIn("new service hotline", request["system"])
        self.assertNotIn("order confirmation", request["system"])

    def test_format_letter_is_the_default(self) -> None:
        _, request = self._request()
        self.assertIn("Format: a classic letter", request["system"])
        self.assertIn("Do not invent dates", request["system"])

    def test_format_structured_asks_for_headings(self) -> None:
        _, request = self._request(style="Structured")
        self.assertIn("<h3> for the title", request["system"])
        self.assertNotIn("Format: a classic letter", request["system"])

    def test_unknown_format_falls_back_to_the_setting(self) -> None:
        _, request = self._request(style="Poem")
        self.assertIn("Format: a classic letter", request["system"])

    def test_dunning_uses_tones_instead_of_formats(self) -> None:
        _, request = self._request(doc=_dunning(), config=_config("Dunning"))
        self.assertIn("Tone: friendly", request["system"])
        self.assertIn("payment reminder", request["system"])
        _, request = self._request(doc=_dunning(), config=_config("Dunning"), style="Firm")
        self.assertIn("Tone: firm", request["system"])
        _, request = self._request(doc=_dunning(), config=_config("Dunning"), style="Structured")
        self.assertIn("Tone: friendly", request["system"])

    def test_settings_validate_cover_letter_document_types(self) -> None:
        if not frappe.db.exists("DocType", "Quotation"):
            self.skipTest("needs ERPNext")
        settings = frappe.get_single("AI Writer Settings")
        settings.set("cover_letter_doctypes", [{"document_type": "Quotation", "target_field": "does_not_exist"}])
        self.assertRaises(frappe.ValidationError, settings.save)
        # Item tables are not text fields.
        settings.set("cover_letter_doctypes", [{"document_type": "Quotation", "target_field": "items"}])
        self.assertRaises(frappe.ValidationError, settings.save)

    def test_patch_moves_the_old_quotation_field(self) -> None:
        if not frappe.db.exists("DocType", "Quotation"):
            self.skipTest("needs ERPNext")
        from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_settings.ai_writer_settings import (
            DEFAULT_COVER_LETTER_PROMPT,
            QUOTATION_COVER_LETTER_PROMPT,
        )
        from frappe_ai_writer.patches.v0_19.move_cover_letter_field import execute

        settings = frappe.get_single("AI Writer Settings")
        settings.set("cover_letter_doctypes", [])
        settings.save()
        frappe.db.set_single_value("AI Writer Settings", "cover_letter_field", "terms")
        frappe.db.set_single_value("AI Writer Settings", "cover_letter_prompt", QUOTATION_COVER_LETTER_PROMPT)

        execute()
        settings = frappe.get_single("AI Writer Settings")
        self.assertEqual(
            [(row.document_type, row.target_field) for row in settings.cover_letter_doctypes], [("Quotation", "terms")]
        )
        self.assertEqual(settings.cover_letter_prompt, DEFAULT_COVER_LETTER_PROMPT)
        self.assertFalse(settings.cover_letter_field)
