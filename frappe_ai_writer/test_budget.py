from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.api.correction import correct_text
from frappe_ai_writer.budget import EXCEEDED, WARNING, clear_month_cache, month_cost
from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_usage.ai_writer_usage import (
    get_usage_summary,
    record_usage,
)

MANAGER = "ai-writer-budget-manager@example.com"
WRITER = "ai-writer-budget-user@example.com"


class TestBudget(FrappeTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        for email, role in ((MANAGER, "AI Writer Manager"), (WRITER, "AI Writer User")):
            if not frappe.db.exists("User", email):
                frappe.get_doc(
                    {"doctype": "User", "email": email, "first_name": "AI Writer Budget", "send_welcome_email": 0}
                ).insert()
            frappe.get_doc("User", email).add_roles(role)

    def setUp(self) -> None:
        frappe.set_user("Administrator")
        frappe.db.delete("AI Writer Usage")
        frappe.db.delete("Notification Log", {"for_user": MANAGER, "document_type": "AI Writer Settings"})
        frappe.db.set_single_value("AI Writer Settings", "budget_notice", "")
        clear_month_cache(WRITER)
        # One USD per million tokens keeps the arithmetic readable.
        self._update_settings(
            enabled=1,
            api_key="sk-ant-test",
            provider="Anthropic",
            model="claude-haiku-5-5",
            input_price_per_million=1,
            output_price_per_million=1,
            monthly_budget=1,
            budget_warning_threshold=80,
            block_when_exceeded=0,
            user_monthly_budget=0,
            track_usage_per_user=0,
            glossary=[],
            house_style="",
        )

    def tearDown(self) -> None:
        frappe.set_user("Administrator")
        self._update_settings(monthly_budget=0, block_when_exceeded=0, user_monthly_budget=0)

    def _update_settings(self, **values) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.update(values)
        settings.save()

    def _notices(self) -> list[str]:
        return frappe.get_all(
            "Notification Log",
            filters={"for_user": MANAGER, "document_type": "AI Writer Settings"},
            pluck="subject",
            order_by="creation asc",
        )

    def _correct(self) -> SimpleNamespace:
        with patch("frappe_ai_writer.providers.anthropic.Anthropic") as client_cls:
            create = client_cls.return_value.messages.create
            create.return_value = SimpleNamespace(
                stop_reason="end_turn", content=[SimpleNamespace(type="text", text="Ein Fehler.")], usage=None
            )
            correct_text(text="Ein Fehlr.")
            return create

    def test_month_cost_uses_the_configured_prices(self) -> None:
        record_usage(None, "correct", "claude-haiku-5-5", 200_000, 300_000)
        self.assertAlmostEqual(month_cost(frappe.get_cached_doc("AI Writer Settings"), cached=False), 0.5)

    def test_warning_and_exceeded_notices_are_sent_once_per_month(self) -> None:
        record_usage(None, "correct", "claude-haiku-5-5", 0, 700_000)
        self.assertEqual(self._notices(), [])

        record_usage(None, "correct", "claude-haiku-5-5", 0, 100_000)
        record_usage(None, "correct", "claude-haiku-5-5", 0, 10_000)
        self.assertEqual(len(self._notices()), 1)
        self.assertIn("80 %", self._notices()[0])

        record_usage(None, "correct", "claude-haiku-5-5", 0, 200_000)
        record_usage(None, "correct", "claude-haiku-5-5", 0, 10_000)
        self.assertEqual(len(self._notices()), 2)
        notice = frappe.parse_json(frappe.db.get_single_value("AI Writer Settings", "budget_notice"))
        self.assertEqual(sorted(notice["levels"]), sorted([WARNING, EXCEEDED]))

    def test_jumping_past_the_budget_sends_only_the_exceeded_notice(self) -> None:
        record_usage(None, "correct", "claude-haiku-5-5", 0, 2_000_000)
        notices = self._notices()
        self.assertEqual(len(notices), 1)
        self.assertNotIn("%", notices[0])

    def test_a_changed_budget_can_warn_again(self) -> None:
        record_usage(None, "correct", "claude-haiku-5-5", 0, 850_000)
        self._update_settings(monthly_budget=1.05)
        record_usage(None, "correct", "claude-haiku-5-5", 0, 10_000)
        self.assertEqual(len(self._notices()), 2)

    def test_saving_the_form_keeps_the_notice_state(self) -> None:
        frappe.db.set_single_value("AI Writer Settings", "budget_notice", '{"month": "2026-10"}')
        settings = frappe.get_single("AI Writer Settings")
        settings.budget_notice = ""
        settings.save()
        self.assertEqual(frappe.db.get_single_value("AI Writer Settings", "budget_notice"), '{"month": "2026-10"}')

    def test_invalid_warning_threshold_is_rejected(self) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.budget_warning_threshold = 120
        self.assertRaises(frappe.ValidationError, settings.save)

    def test_hard_limit_refuses_requests_before_calling_the_service(self) -> None:
        self._update_settings(block_when_exceeded=1)
        record_usage(None, "correct", "claude-haiku-5-5", 0, 1_000_000)
        with patch("frappe_ai_writer.providers.anthropic.Anthropic") as client_cls:
            self.assertRaises(frappe.ValidationError, correct_text, text="Ein Fehlr.")
            client_cls.return_value.messages.create.assert_not_called()

        # Raising the budget takes effect right away.
        self._update_settings(monthly_budget=2)
        self._correct().assert_called_once()

    def test_without_hard_limit_requests_continue(self) -> None:
        record_usage(None, "correct", "claude-haiku-5-5", 0, 1_000_000)
        self._correct().assert_called_once()

    def test_user_limit_needs_per_user_tracking(self) -> None:
        self._update_settings(monthly_budget=0, user_monthly_budget=0.5)
        record_usage(WRITER, "correct", "claude-haiku-5-5", 0, 600_000)
        frappe.set_user(WRITER)
        self._correct().assert_called_once()

        frappe.set_user("Administrator")
        self._update_settings(track_usage_per_user=1)
        frappe.set_user(WRITER)
        self.assertRaises(frappe.ValidationError, self._correct)

    def test_usage_summary_contains_the_budget(self) -> None:
        record_usage(None, "correct", "claude-haiku-5-5", 0, 250_000)
        budget = get_usage_summary()["budget"]
        self.assertEqual((budget["budget"], budget["percent"], budget["threshold"]), (1, 25, 80))
        self._update_settings(monthly_budget=0)
        self.assertIsNone(get_usage_summary()["budget"])
