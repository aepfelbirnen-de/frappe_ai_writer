from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import frappe
import requests
from frappe.tests.utils import FrappeTestCase

from frappe_ai_writer.api.correction import correct_text


def _http_response(status: int = 200, content: str = "Ein Fehler.", finish_reason: str = "stop", usage=None):
    body = {
        "choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish_reason}],
        "usage": usage or {"prompt_tokens": 12, "completion_tokens": 4},
    }
    return SimpleNamespace(status_code=status, json=lambda: body, content=b"x" * 10)


class TestOpenAICompatibleProviders(FrappeTestCase):
    def setUp(self) -> None:
        frappe.set_user("Administrator")
        self._settings(provider="Ollama", base_url="", model="llama3.2", api_key="", track_usage_per_user=1)

    def tearDown(self) -> None:
        self._settings(provider="Anthropic", base_url="", model="claude-haiku-5-5", api_key="sk-ant-test")

    def _settings(self, **values) -> None:
        settings = frappe.get_single("AI Writer Settings")
        settings.update(values)
        settings.save()

    def _correct(self, response=None, side_effect=None, **kwargs):
        with patch("frappe_ai_writer.providers.requests.post") as post, patch("frappe_ai_writer.providers.time.sleep"):
            post.return_value = response or _http_response()
            post.side_effect = side_effect
            result = correct_text(**{"text": "Ein Fehlr.", **kwargs})
            return result, post

    def test_ollama_uses_the_default_url_without_a_key(self) -> None:
        result, post = self._correct()
        self.assertEqual(result, "Ein Fehler.")
        self.assertEqual(post.call_args.args[0], "http://localhost:11434/v1/chat/completions")
        self.assertNotIn("Authorization", post.call_args.kwargs["headers"])
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["model"], "llama3.2")
        self.assertEqual(body["messages"][0]["role"], "system")
        self.assertIn("max_tokens", body)
        self.assertFalse(post.call_args.kwargs["allow_redirects"])

    def test_openai_sends_the_key_and_max_completion_tokens(self) -> None:
        self._settings(provider="OpenAI", model="gpt-test", api_key="sk-test")
        _, post = self._correct()
        self.assertEqual(post.call_args.args[0], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer sk-test")
        self.assertIn("max_completion_tokens", post.call_args.kwargs["json"])

    def test_reasoning_in_think_tags_is_removed(self) -> None:
        result, _ = self._correct(response=_http_response(content="<think>hmm</think>\nEin Fehler."))
        self.assertEqual(result, "Ein Fehler.")

    def test_errors_and_limits_become_user_messages(self) -> None:
        for response in (
            _http_response(status=401),
            _http_response(status=500),
            _http_response(finish_reason="length"),
        ):
            with self.subTest(status=response.status_code):
                self.assertRaises(frappe.ValidationError, self._correct, response=response)
        self.assertRaises(frappe.ValidationError, self._correct, side_effect=requests.ConnectionError())

    def test_tokens_are_recorded(self) -> None:
        frappe.db.delete("AI Writer Usage")
        self._correct(response=_http_response(usage={"prompt_tokens": 30, "completion_tokens": 7}))
        row = frappe.get_all("AI Writer Usage", fields=["model", "input_tokens", "output_tokens"])[0]
        self.assertEqual((row.model, row.input_tokens, row.output_tokens), ("llama3.2", 30, 7))

    def test_settings_validate_model_and_base_url(self) -> None:
        settings = frappe.get_single("AI Writer Settings")
        for values in (
            {"provider": "OpenAI", "model": "claude-haiku-5-5"},
            {"provider": "OpenAI-compatible", "model": "x", "base_url": "ftp://example.com"},
            {"provider": "OpenAI-compatible", "model": "x", "base_url": "https://user:secret@example.com/v1"},
        ):
            with self.subTest(values=values):
                settings.reload()
                settings.update(values)
                self.assertRaises(frappe.ValidationError, settings.save)
