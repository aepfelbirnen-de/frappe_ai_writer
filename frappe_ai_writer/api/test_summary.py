from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.api import summary
from frappe_ai_writer.api.summary import collect_entries, summarize, truncate_entries

TEST_USER = "ai-writer-summary-test@example.com"


class TestSummary(FrappeTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if not frappe.db.exists("User", TEST_USER):
            frappe.get_doc(
                {"doctype": "User", "email": TEST_USER, "first_name": "AI Writer Summary", "send_welcome_email": 0}
            ).insert()

    def setUp(self) -> None:
        frappe.set_user("Administrator")
        frappe.get_doc("User", TEST_USER).remove_roles(*frappe.get_roles(TEST_USER))
        settings = frappe.get_single("AI Writer Settings")
        settings.update(
            {
                "enabled": 1,
                "api_key": "sk-ant-test",
                "provider": "Anthropic",
                "model": "claude-haiku-5-5",
                "summary_prompt": "",
                "summary_style": "Bullet List",
                "summary_max_words": 150,
                "track_usage_per_user": 0,
                "monthly_budget": 0,
                "glossary": [],
                "house_style": "",
            }
        )
        settings.set("summary_doctypes", [{"document_type": "ToDo"}])
        settings.save()

        self.todo = frappe.get_doc({"doctype": "ToDo", "description": "Server migration"}).insert()
        frappe.get_doc(
            {
                "doctype": "Communication",
                "communication_type": "Communication",
                "communication_medium": "Email",
                "sent_or_received": "Received",
                "sender": "anna@example.com",
                "sender_full_name": "Anna Miller",
                "subject": "Migration date",
                "content": "<p>Can we move the server on Friday?</p><p>On Mon, Oct 19, 2026 Bob wrote:</p><p>old</p>",
                "communication_date": "2026-01-05 09:00:00",
                "reference_doctype": "ToDo",
                "reference_name": self.todo.name,
            }
        ).insert(ignore_permissions=True)
        self.todo.add_comment("Comment", text="Friday is confirmed, Bob prepares the backup.")

    def tearDown(self) -> None:
        frappe.set_user("Administrator")

    def _summarize(self, **kwargs) -> tuple[dict, dict]:
        with patch("frappe_ai_writer.providers.anthropic.Anthropic") as client_cls:
            create = client_cls.return_value.messages.create
            create.return_value = SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text="<h4>Offen</h4><ul><li>Backup</li></ul>")],
                usage=SimpleNamespace(input_tokens=50, output_tokens=10),
            )
            result = summarize("ToDo", self.todo.name, **kwargs)
            return result, create.call_args.kwargs

    def test_entries_are_oldest_first_without_quoted_history(self) -> None:
        entries = collect_entries("ToDo", self.todo.name)
        self.assertEqual(len(entries), 2)
        self.assertIn("Email received from Anna Miller, subject: Migration date", entries[0])
        self.assertIn("Can we move the server on Friday?", entries[0])
        self.assertNotIn("old", entries[0].split("\n", 1)[1])
        self.assertIn("Comment by", entries[1])
        self.assertIn("Bob prepares the backup", entries[1])

    def test_request_contains_the_conversation_and_settings(self) -> None:
        result, request = self._summarize()
        message = request["messages"][0]["content"]
        self.assertTrue(message.startswith("<conversation>"))
        self.assertIn("Friday is confirmed", message)
        self.assertIn("at most 150 words", request["system"])
        self.assertIn("<h4>", request["system"])
        self.assertEqual(result["summary"], "<h4>Offen</h4><ul><li>Backup</li></ul>")
        self.assertEqual((result["considered"], result["total"]), (2, 2))
        self.assertIn("claude-haiku-5-5", result["footer"])

    def test_prose_format_can_be_chosen(self) -> None:
        _, request = self._summarize(style="Prose")
        self.assertIn("one <p> element per paragraph", request["system"])

    def test_long_timelines_keep_the_newest_messages_with_a_hint(self) -> None:
        with patch.object(summary, "MAX_CONVERSATION_CHARS", 60):
            result, request = self._summarize()
        self.assertEqual((result["considered"], result["total"]), (1, 2))
        self.assertIn("Only the last 1 of 2 messages are included", request["system"])
        self.assertNotIn("Anna", request["messages"][0]["content"])
        self.assertIn("<em>", result["summary"])

    def test_truncation_always_keeps_the_newest_entry(self) -> None:
        text, count = truncate_entries(["a" * 10, "b" * 10, "c" * 100])
        self.assertEqual(count, 1)
        self.assertEqual(text, "c" * 100)

    def test_usage_is_recorded_as_summary(self) -> None:
        frappe.db.delete("AI Writer Usage")
        self._summarize()
        self.assertEqual(frappe.db.get_value("AI Writer Usage", {"mode": "summary"}, "input_tokens"), 50)

    def test_documents_the_user_cannot_read_are_refused(self) -> None:
        frappe.get_doc("User", TEST_USER).add_roles("AI Writer User")
        frappe.set_user(TEST_USER)
        self.assertRaises(frappe.PermissionError, self._summarize)

    def test_users_without_role_are_refused(self) -> None:
        frappe.set_user(TEST_USER)
        self.assertRaises(frappe.PermissionError, self._summarize)

    def test_doctypes_that_are_not_enabled_are_refused(self) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.set("summary_doctypes", [])
        settings.save()
        self.assertRaises(frappe.ValidationError, self._summarize)

    def test_empty_timeline_is_reported(self) -> None:
        todo = frappe.get_doc({"doctype": "ToDo", "description": "Empty"}).insert()
        with patch("frappe_ai_writer.providers.anthropic.Anthropic") as client_cls:
            self.assertRaises(frappe.ValidationError, summarize, "ToDo", todo.name)
            client_cls.return_value.messages.create.assert_not_called()

    def test_settings_validate_summary_values(self) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.set("summary_doctypes", [{"document_type": "ToDo"}, {"document_type": "ToDo"}])
        settings.save()
        self.assertEqual([row.document_type for row in settings.summary_doctypes], ["ToDo"])
        settings.summary_max_words = 1000
        self.assertRaises(frappe.ValidationError, settings.save)
        settings.reload()
        settings.set("summary_doctypes", [{"document_type": "System Settings"}])
        self.assertRaises(frappe.ValidationError, settings.save)
