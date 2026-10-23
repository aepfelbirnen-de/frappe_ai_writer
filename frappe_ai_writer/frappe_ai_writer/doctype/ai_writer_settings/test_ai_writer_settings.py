# Copyright (c) 2026, aepfel+birnen IT GmbH and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_settings.ai_writer_settings import (
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
)

TEST_USER = "ai-writer-settings-test@example.com"


class TestAIWriterSettings(FrappeTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if not frappe.db.exists("User", TEST_USER):
            frappe.get_doc(
                {
                    "doctype": "User",
                    "email": TEST_USER,
                    "first_name": "AI Writer Settings Test",
                    "send_welcome_email": 0,
                }
            ).insert()

    def setUp(self) -> None:
        frappe.get_doc("User", TEST_USER).remove_roles(*frappe.get_roles(TEST_USER))

    def test_empty_values_fall_back_to_defaults(self) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.update({"model": "  ", "system_prompt": ""})
        settings.save()
        self.assertEqual(settings.model, DEFAULT_MODEL)
        self.assertEqual(settings.system_prompt, DEFAULT_SYSTEM_PROMPT)

    def test_invalid_model_name_is_rejected(self) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.model = "../../etc/passwd"
        self.assertRaises(frappe.ValidationError, settings.save)

    def test_ai_writer_user_cannot_read_settings(self) -> None:
        # Settings hold the API key, so only managers may open them.
        frappe.get_doc("User", TEST_USER).add_roles("AI Writer User")
        self.assertFalse(frappe.has_permission("AI Writer Settings", "read", user=TEST_USER))

    def test_ai_writer_manager_can_edit_settings(self) -> None:
        frappe.get_doc("User", TEST_USER).add_roles("AI Writer Manager")
        self.assertTrue(frappe.has_permission("AI Writer Settings", "write", user=TEST_USER))
