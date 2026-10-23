# Copyright (c) 2026, aepfel+birnen IT GmbH and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_usage.ai_writer_usage import (
    get_usage_summary,
    record_usage,
)

TEST_USER = "ai-writer-usage-test@example.com"


class TestAIWriterUsage(FrappeTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if not frappe.db.exists("User", TEST_USER):
            frappe.get_doc(
                {"doctype": "User", "email": TEST_USER, "first_name": "AI Writer Usage Test", "send_welcome_email": 0}
            ).insert()

    def setUp(self) -> None:
        frappe.set_user("Administrator")
        frappe.db.delete("AI Writer Usage")
        settings = frappe.get_single("AI Writer Settings")
        settings.update({"input_price_per_million": 0.1, "output_price_per_million": 0.5, "track_usage_per_user": 1})
        settings.save()
        frappe.get_doc("User", TEST_USER).remove_roles(*frappe.get_roles(TEST_USER))

    def tearDown(self) -> None:
        frappe.set_user("Administrator")

    def test_requests_on_the_same_day_add_up_in_one_row(self) -> None:
        record_usage(TEST_USER, "correct", "claude-haiku-5-5", 100, 40)
        record_usage(TEST_USER, "correct", "claude-haiku-5-5", 50, 10)
        record_usage(TEST_USER, "translate", "claude-haiku-5-5", 20, 20)
        rows = frappe.get_all("AI Writer Usage", fields=["mode", "requests", "input_tokens", "output_tokens"])
        by_mode = {row.mode: row for row in rows}
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            (by_mode["correct"].requests, by_mode["correct"].input_tokens, by_mode["correct"].output_tokens),
            (2, 150, 50),
        )

    def test_summary_has_totals_per_user_and_cost(self) -> None:
        record_usage(TEST_USER, "expand", "claude-haiku-5-5", 1_000_000, 1_000_000)
        summary = get_usage_summary()
        self.assertEqual(summary["periods"]["today"]["requests"], 1)
        self.assertEqual(summary["periods"]["month"]["cost"], 0.6)
        self.assertEqual(summary["per_user"][0]["user"], TEST_USER)
        self.assertEqual(summary["per_user"][0]["full_name"], "AI Writer Usage Test")

    def test_per_user_table_is_hidden_when_tracking_is_off(self) -> None:
        record_usage(TEST_USER, "correct", "claude-haiku-5-5", 10, 10)
        frappe.db.set_single_value("AI Writer Settings", "track_usage_per_user", 0)
        frappe.clear_document_cache("AI Writer Settings", "AI Writer Settings")
        summary = get_usage_summary()
        self.assertFalse(summary["per_user_enabled"])
        self.assertEqual(summary["per_user"], [])
        self.assertEqual(summary["periods"]["today"]["requests"], 1)

    def test_rows_without_user_are_counted_in_totals(self) -> None:
        record_usage(None, "correct", "claude-haiku-5-5", 10, 10)
        record_usage(None, "correct", "claude-haiku-5-5", 5, 5)
        self.assertEqual(frappe.db.get_value("AI Writer Usage", {"user": ["is", "not set"]}, "requests"), 2)
        summary = get_usage_summary()
        self.assertEqual(summary["periods"]["total"]["input_tokens"], 15)
        self.assertEqual(summary["per_user"], [])

    def test_summary_is_manager_only(self) -> None:
        frappe.get_doc("User", TEST_USER).add_roles("AI Writer User")
        frappe.set_user(TEST_USER)
        self.assertRaises(frappe.PermissionError, get_usage_summary)
