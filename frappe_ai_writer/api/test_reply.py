from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.api.reply import build_document_context, draft_reply, strip_quoted_history


def _message(**overrides) -> SimpleNamespace:
    message = SimpleNamespace(
        name="COMM-TEST",
        sender="anna@example.com",
        sender_full_name="Anna Miller",
        subject="Delivery date",
        content="<p>Hello,</p><p>when will the server arrive?</p><p>On Mon, Oct 19, 2026 Bob wrote:</p><p>old text</p>",
        reference_doctype=None,
        reference_name=None,
    )
    message.__dict__.update(overrides)
    message.check_permission = lambda permtype: None
    return message


class TestReplyDraft(FrappeTestCase):
    def setUp(self) -> None:
        frappe.set_user("Administrator")
        settings = frappe.get_single("AI Writer Settings")
        settings.update(
            {
                "enabled": 1,
                "api_key": "sk-ant-test",
                "provider": "Anthropic",
                "model": "claude-haiku-5-5",
                "reply_prompt": "",
            }
        )
        settings.save()

    def test_quoted_history_is_removed(self) -> None:
        self.assertEqual(
            strip_quoted_history("<p>Neu</p><p>Am 23.10.2026 schrieb Max &lt;m@x.de&gt;:</p><p>alt</p>"), "Neu"
        )
        self.assertEqual(strip_quoted_history("<p>Bitte Rückruf.</p><blockquote>Zitat</blockquote>"), "Bitte Rückruf.")

    def test_document_context_needs_read_permission(self) -> None:
        message = _message(reference_doctype="ToDo", reference_name="does-not-exist")
        self.assertEqual(build_document_context(message), "")

    def test_request_contains_message_without_quote_and_keeps_protected_notes(self) -> None:
        with (
            patch("frappe_ai_writer.api.reply.frappe.get_doc", return_value=_message()),
            patch("frappe_ai_writer.providers.anthropic.Anthropic") as client_cls,
        ):
            client_cls.return_value.messages.create.return_value = SimpleNamespace(
                stop_reason="end_turn",
                content=[SimpleNamespace(type="text", text="<p>Dear Ms Miller, ⟦P1⟧</p>")],
                usage=None,
            )
            result = draft_reply("COMM-TEST", notes='Delivery /"KW 46"/ confirmed')
            request = client_cls.return_value.messages.create.call_args.kwargs
        message = request["messages"][0]["content"]
        self.assertIn("when will the server arrive?", message)
        self.assertNotIn("old text", message)
        self.assertNotIn("KW 46", message)
        self.assertIn("Do not promise dates", request["system"])
        self.assertIn('/"KW 46"/', result)
