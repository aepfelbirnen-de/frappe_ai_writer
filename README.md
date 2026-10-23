# Frappe AI Writer

AI proofreading for Frappe and ERPNext text fields, powered by Anthropic's Claude.

A sparkle button appears in every desk text field. One click corrects spelling, grammar and punctuation, either of the selected text or of the whole field, without leaving the form.

## Features

- Works in **Text Editor** fields, the **email composer**, the **comment box** and plain **Small Text / Text / Long Text** fields
- Three modes: **Correct**, **More formal**, **More casual**
- Corrects the selection or, without a selection, the whole field; rich-text formatting is preserved
- One undo step (Cmd+Z / Ctrl+Z) reverts a correction
- Detects the language of the text and answers in the same language
- Configurable model, effort and system prompt
- Role-based access; translations for English, German, Spanish, French, Ukrainian and Danish

## Requirements

- Frappe Framework v15 or v16 (ERPNext is optional)
- An [Anthropic API key](https://console.anthropic.com/)

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/aepfelbirnen-de/frappe_ai_writer
bench --site your-site install-app frappe_ai_writer
bench --site your-site migrate
```

## Configuration

1. Open **AI Writer Settings** (from the **AI Writer** workspace or the apps screen).
2. Enter your **Anthropic API Key**.
3. Optionally adjust:
   - **Model**: defaults to `claude-haiku-5-5`, fast and inexpensive for proofreading
   - **Effort**: how much the model reasons before answering; `low` is fastest
   - **System Prompt**: the instructions sent with every request; leave empty to restore the default
4. Give users the **AI Writer User** role. Users without it do not see the button.

| Role | Can use the button | Can edit the settings |
|---|---|---|
| AI Writer User | yes | no |
| AI Writer Manager | yes | yes |
| System Manager | only with one of the roles above | yes |

## Privacy

The text being corrected is sent to the Anthropic API using your API key. The app does not store the text or the response. Review Anthropic's data retention terms before using the app with personal or confidential data.

## Security

- The correction endpoint accepts POST only, checks the user's role and is rate limited.
- HTML returned by the model is sanitized before it is inserted into an editor.
- The API key is stored encrypted in a Password field and never sent to the browser.

## Development

```bash
ruff check frappe_ai_writer/
ruff format --check frappe_ai_writer/
bench --site your-site run-tests --app frappe_ai_writer
```

## License

MIT, see [license.txt](license.txt).
