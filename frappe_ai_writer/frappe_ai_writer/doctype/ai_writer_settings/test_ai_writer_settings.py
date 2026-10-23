# Copyright (c) 2026, aepfel+birnen IT GmbH and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_settings.ai_writer_settings import (
    DEFAULT_EXPAND_PROMPT,
    DEFAULT_MODEL,
    DEFAULT_SYSTEM_PROMPT,
    get_translation_languages,
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

    def test_write_out_defaults_are_filled(self) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.update({"expand_prompt": "", "expansion_factor_min": 0, "expansion_factor_max": 0})
        settings.save()
        self.assertEqual(settings.expand_prompt, DEFAULT_EXPAND_PROMPT)
        self.assertEqual((settings.expansion_factor_min, settings.expansion_factor_max), (4, 10))

    def test_invalid_expansion_factors_are_rejected(self) -> None:
        for low, high in ((5, 3), (1, 51)):
            with self.subTest(low=low, high=high):
                settings = frappe.get_single("AI Writer Settings")
                settings.update({"expansion_factor_min": low, "expansion_factor_max": high})
                self.assertRaises(frappe.ValidationError, settings.save)

    def test_invalid_model_name_is_rejected(self) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.model = "../../etc/passwd"
        self.assertRaises(frappe.ValidationError, settings.save)

    def test_duplicate_translation_languages_are_removed(self) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.set("translation_languages", [{"language": "de"}, {"language": "en"}, {"language": "de"}])
        settings.save()
        self.assertEqual([row.language for row in settings.translation_languages], ["de", "en"])

    def test_translation_languages_come_with_native_names(self) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.set("translation_languages", [{"language": "de"}])
        settings.save()
        languages = get_translation_languages()
        self.assertEqual(languages[0]["code"], "de")
        self.assertEqual(languages[0]["name"], frappe.db.get_value("Language", "de", "language_name"))

    def test_ai_writer_user_cannot_read_settings(self) -> None:
        # Settings hold the API key, so only managers may open them.
        frappe.get_doc("User", TEST_USER).add_roles("AI Writer User")
        self.assertFalse(frappe.has_permission("AI Writer Settings", "read", user=TEST_USER))

    def test_ai_writer_manager_can_edit_settings(self) -> None:
        frappe.get_doc("User", TEST_USER).add_roles("AI Writer Manager")
        self.assertTrue(frappe.has_permission("AI Writer Settings", "write", user=TEST_USER))
