from __future__ import annotations

from pathlib import Path

import frappe
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.boot import APP_NAME, get_translated_change_logs


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
