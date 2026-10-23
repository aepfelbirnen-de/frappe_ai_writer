from __future__ import annotations

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.boot import APP_NAME, boot_session, get_translated_change_logs

TEST_USER = "ai-writer-boot-test@example.com"


class TestBootSession(FrappeTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        if not frappe.db.exists("User", TEST_USER):
            frappe.get_doc(
                {"doctype": "User", "email": TEST_USER, "first_name": "AI Writer Boot Test", "send_welcome_email": 0}
            ).insert()

    def setUp(self) -> None:
        frappe.set_user("Administrator")
        frappe.get_doc("User", TEST_USER).remove_roles(*frappe.get_roles(TEST_USER))

    def tearDown(self) -> None:
        frappe.set_user("Administrator")

    def _boot_as_test_user(self) -> frappe._dict:
        frappe.set_user(TEST_USER)
        bootinfo = frappe._dict()
        boot_session(bootinfo)
        return bootinfo

    def test_ai_writer_user_gets_button_flag_and_change_log_title(self) -> None:
        frappe.get_doc("User", TEST_USER).add_roles("AI Writer User")
        bootinfo = self._boot_as_test_user()
        self.assertIn("enabled", bootinfo.ai_writer)
        self.assertIsInstance(bootinfo.ai_writer["languages"], list)
        self.assertEqual(bootinfo.ai_writer_change_log["title"], frappe.get_hooks("app_title", app_name=APP_NAME)[0])

    def test_user_without_access_gets_nothing(self) -> None:
        bootinfo = self._boot_as_test_user()
        self.assertNotIn("ai_writer", bootinfo)
        self.assertNotIn("ai_writer_change_log", bootinfo)


class TestTranslatedChangeLogs(FrappeTestCase):
    def test_german_change_logs_are_keyed_by_version(self) -> None:
        versions = get_translated_change_logs("de")
        self.assertIn("0.5.1", versions)
        self.assertTrue(versions["0.5.1"].startswith("### "))

    def test_regional_language_falls_back_to_base_language(self) -> None:
        self.assertEqual(get_translated_change_logs("de-CH"), get_translated_change_logs("de"))

    def test_unknown_or_unsafe_language_returns_nothing(self) -> None:
        for lang in ("xx", "", None, "../de", "de/../../etc"):
            with self.subTest(lang=lang):
                self.assertEqual(get_translated_change_logs(lang), {})

    def test_every_change_log_has_a_german_translation(self) -> None:
        english = {path.name for path in Path(frappe.get_app_path(APP_NAME, "change_log")).glob("v*/v*.md")}
        german = {path.name for path in Path(frappe.get_app_path(APP_NAME, "change_log_i18n", "de")).glob("v*/v*.md")}
        self.assertEqual(english - german, set())
