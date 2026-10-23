"""Chat backends: Anthropic's Messages API and OpenAI-compatible chat completions (OpenAI, Ollama and others)."""

from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlparse

import anthropic
import frappe
import requests
from frappe import _

ANTHROPIC = "Anthropic"
OPENAI = "OpenAI"
OLLAMA = "Ollama"
OPENAI_COMPATIBLE = "OpenAI-compatible"
PROVIDERS = (ANTHROPIC, OPENAI, OLLAMA, OPENAI_COMPATIBLE)

DEFAULT_BASE_URLS = {OPENAI: "https://api.openai.com/v1", OLLAMA: "http://localhost:11434/v1"}
KEY_REQUIRED = (ANTHROPIC, OPENAI)
MAX_RESPONSE_BYTES = 5_000_000


@dataclass
class Completion:
    text: str
    # "end", "length" (output limit reached) or "refusal"
    stop: str
    input_tokens: int
    output_tokens: int


def normalize_provider(provider: str | None) -> str:
    return provider if provider in PROVIDERS else ANTHROPIC


def validate_base_url(url: str) -> str:
    """Return the URL without a trailing slash; only plain http(s) URLs without credentials are accepted."""
    url = (url or "").strip().rstrip("/")
    parsed = urlparse(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        frappe.throw(_("Invalid base URL: {0}").format(url or "?"))
    return url


def complete(
    *,
    provider: str,
    api_key: str | None,
    base_url: str | None,
    model: str,
    effort: str | None,
    system_prompt: str,
    user_message: str,
    max_tokens: int,
    timeout: float,
    max_retries: int,
) -> Completion:
    """Send one system prompt and one user message; errors become user-facing messages."""
    if normalize_provider(provider) == ANTHROPIC:
        return _anthropic(api_key, model, effort, system_prompt, user_message, max_tokens, timeout, max_retries)
    return _openai_compatible(
        provider, api_key, base_url, model, system_prompt, user_message, max_tokens, timeout, max_retries
    )


def _anthropic(api_key, model, effort, system_prompt, user_message, max_tokens, timeout, max_retries) -> Completion:
    client = anthropic.Anthropic(api_key=api_key, timeout=timeout, max_retries=max_retries)
    request = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_message}],
    }
    if effort:
        request["output_config"] = {"effort": effort}

    try:
        response = client.messages.create(**request)
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError):
        _fail(_("The API key of the AI service is invalid or lacks permission."))
    except anthropic.NotFoundError:
        _fail(_("The configured AI model is not available: {0}").format(model))
    except anthropic.RateLimitError:
        _fail(_("The AI service is busy. Please try again in a moment."))
    except anthropic.APIStatusError:
        _fail(_("The AI service returned an error. Please try again later."))
    except anthropic.APIConnectionError:
        _fail(_("The AI service could not be reached. Please try again later."))

    usage = getattr(response, "usage", None)
    # Responses may start with thinking blocks, so only text blocks carry the answer.
    return Completion(
        text="".join(block.text for block in response.content if block.type == "text"),
        stop={"refusal": "refusal", "max_tokens": "length"}.get(response.stop_reason, "end"),
        input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
        output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
    )


def _openai_compatible(
    provider, api_key, base_url, model, system_prompt, user_message, max_tokens, timeout, max_retries
) -> Completion:
    url = validate_base_url(base_url or DEFAULT_BASE_URLS.get(provider, "")) + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_message}],
        # OpenAI's reasoning models reject max_tokens; most other servers only know max_tokens.
        ("max_completion_tokens" if provider == OPENAI else "max_tokens"): max_tokens,
    }

    for attempt in range(max_retries + 1):
        last_attempt = attempt == max_retries
        try:
            # Redirects are not followed, so a configured URL cannot bounce requests elsewhere.
            response = requests.post(url, json=body, headers=headers, timeout=timeout, allow_redirects=False)
        except requests.RequestException:
            if last_attempt:
                _fail(_("The AI service could not be reached. Please try again later."))
            time.sleep(1)
            continue
        if (response.status_code == 429 or response.status_code >= 500) and not last_attempt:
            time.sleep(1)
            continue
        break

    status = response.status_code
    # Only the status goes to the error log; response bodies may echo the user's text.
    detail = f"{provider} {url} -> HTTP {status}"
    if status in (401, 403):
        _fail(_("The API key of the AI service is invalid or lacks permission."), detail)
    if status == 404:
        _fail(_("The configured AI model is not available: {0}").format(model), detail)
    if status == 429:
        _fail(_("The AI service is busy. Please try again in a moment."), detail)
    if status != 200 or len(response.content) > MAX_RESPONSE_BYTES:
        _fail(_("The AI service returned an error. Please try again later."), detail)

    try:
        data = response.json()
        choice = data["choices"][0]
        message = choice.get("message") or {}
    except (ValueError, KeyError, IndexError, TypeError):
        _fail(_("The AI service returned an error. Please try again later."), f"{detail}, unexpected response format")

    finish_reason = choice.get("finish_reason")
    usage = data.get("usage") or {}
    return Completion(
        text=message.get("content") or "",
        stop="refusal"
        if message.get("refusal") or finish_reason == "content_filter"
        else ("length" if finish_reason == "length" else "end"),
        input_tokens=int(usage.get("prompt_tokens") or 0),
        output_tokens=int(usage.get("completion_tokens") or 0),
    )


def _fail(message: str, detail: str | None = None) -> None:
    # Deferred so the entry survives the rollback triggered by the frappe.throw that follows.
    frappe.log_error(title="AI Writer: AI service request failed", message=detail, defer_insert=True)
    frappe.throw(message)
