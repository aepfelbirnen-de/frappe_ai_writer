# Frappe AI Writer

**English** · [Deutsch](#deutsch)

AI proofreading, write-out and translation for Frappe and ERPNext text fields. Works with Anthropic, OpenAI, local models via Ollama and other OpenAI-compatible services.

A sparkle button appears in every desk text field. One click corrects spelling, grammar and punctuation, either of the selected text or of the whole field, without leaving the form.

![AI correction menu in the email composer](docs/screenshots/en-email-menu.png)

## Features

- Works in **Text Editor** fields, the **email composer**, the **comment box** and plain **Small Text / Text / Long Text** fields
- Modes: **Correct**, **Write out**, **Shorten**, **Plain language**, **More formal**, **More casual**
- Turns bullet-point notes into detailed, complete text that explains terms and background, automatically or via **Write out**, without inventing specific facts
- **Translate** button (文A) with target languages chosen by a manager in AI Writer Settings
- Text between `/"` and `"/` is never corrected or translated, e.g. `/"Müller & Söhne GmbH"/`; it does not reach the AI service
- **Reply drafts** in the email composer: writes a reply from the incoming message (without quoted history) and its document, steered by optional notes
- **Cover letters for quotations** (ERPNext): writes the letter text of a draft quotation from customer, contact and line items, never from prices, as a letter or structured with headings
- A **Help** entry in the menu explains all functions
- Corrects the selection or, without a selection, the whole field; rich-text formatting is preserved
- A preview highlights the changes before they replace the text (Apply, Regenerate, Discard); one undo step (Cmd+Z / Ctrl+Z) reverts an applied correction
- Detects the language of the text and answers in the same language
- Configurable model, effort and system prompt
- Role-based access; translations for English, German, Spanish, French, Ukrainian and Danish

| After one click | Plain text fields | Comment box |
|---|---|---|
| ![Corrected email](docs/screenshots/en-email-corrected.png) | ![Button in a text field](docs/screenshots/en-text-field.png) | ![Button in the comment box](docs/screenshots/en-comment.png) |

## Requirements

- Frappe Framework v15 or v16 (ERPNext is optional)
- One AI service: an Anthropic or OpenAI API key, a local [Ollama](https://ollama.com/) server, or any other OpenAI-compatible API

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/aepfelbirnen-de/frappe_ai_writer
bench --site your-site install-app frappe_ai_writer
bench --site your-site migrate
```

## Configuration

1. Open **AI Writer Settings** (from the **AI Writer** workspace or the apps screen).
2. Choose the **Provider** and enter the **API Key** if the service needs one:

   | Provider | Base URL | Example model |
   |---|---|---|
   | Anthropic | (built in) | `claude-haiku-5-5` (default) |
   | OpenAI | `https://api.openai.com/v1` (default) | a model from your OpenAI account |
   | Ollama | `http://localhost:11434/v1` (default) | `llama3.2` |
   | OpenAI-compatible | the service's API address, e.g. Mistral, Google Gemini, OpenRouter, Groq, DeepSeek, LM Studio, vLLM | a model of that service |

3. Optionally adjust:
   - **Model**: the model name at the provider
   - **Effort** (Anthropic only): how much the model reasons before answering; `low` is fastest
   - **System Prompt**: the instructions sent with every request; leave empty to restore the default
   - **Write-out Prompt**: the instructions for writing out notes; leave empty to restore the default
   - **Minimum / Maximum Expansion Factor**: roughly how many times longer than the notes the written-out text gets (default 4 to 10)
   - **Cover Letter Field** (ERPNext): the Quotation text field that holds the cover letter in your print format, e.g. a custom field; leave empty to hide the button. **Cover Letter Format** sets the default (Letter or Structured), **Cover Letter Prompt** the shared rules
   - **Preview Before Replacing**: for long texts (default, from 300 characters), always or never
   - **Translation Languages**: the target languages of the translate button; leave empty to hide it
   - **Usage**: token usage today, this month and in total, with estimated costs based on the configured prices; **Track Usage per User** (off by default) adds a per-user table
4. Give users the **AI Writer User** role. Users without it do not see the button.

| Role | Can use the button | Can edit the settings |
|---|---|---|
| AI Writer User | yes | no |
| AI Writer Manager | yes | yes |
| System Manager | only with one of the roles above | yes |

## Privacy

The text being corrected is sent to the AI service you configure: Anthropic, OpenAI, another OpenAI-compatible provider, or your own Ollama server, where it never leaves your network. The app does not store the text or the response. It records token counts per day and mode (no text) so managers can see usage and costs. Per-user counts are only recorded when **Track Usage per User** is enabled; check the law that applies in your country before enabling it, for example on data protection and employee co-determination. Review the provider's data processing and retention terms before using the app with personal or confidential data.

## Security

- The correction endpoint accepts POST only, checks the user's role and is rate limited.
- HTML returned by the model is sanitized before it is inserted into an editor.
- The API key is stored encrypted in a Password field and never sent to the browser.
- The base URL accepts plain http(s) addresses only, without credentials; redirects are not followed and error logs contain only the HTTP status, never response bodies.

## Development

```bash
ruff check frappe_ai_writer/
ruff format --check frappe_ai_writer/
bench --site your-site run-tests --app frappe_ai_writer
```

## License

MIT, see [license.txt](license.txt).

---

<a id="deutsch"></a>

# Frappe AI Writer (Deutsch)

[English](#frappe-ai-writer) · **Deutsch**

KI-Korrekturlesen, Ausformulieren und Übersetzen für Textfelder in Frappe und ERPNext. Funktioniert mit Anthropic, OpenAI, lokalen Modellen über Ollama und weiteren OpenAI-kompatiblen Diensten.

In jedem Textfeld des Desks erscheint ein Funkel-Button. Ein Klick korrigiert Rechtschreibung, Grammatik und Zeichensetzung, wahlweise im markierten Text oder im ganzen Feld, ohne das Formular zu verlassen.

![KI-Korrekturmenü im E-Mail-Dialog](docs/screenshots/de-email-menu.png)

## Funktionen

- Funktioniert in **Text-Editor**-Feldern, im **E-Mail-Dialog**, im **Kommentarfeld** und in einfachen **Small-Text-, Text- und Long-Text**-Feldern
- Modi: **Korrigieren**, **Ausformulieren**, **Kürzen**, **Einfache Sprache**, **Formeller**, **Lockerer**
- Formuliert Stichpunkte zu ausführlichem, vollständigem Text aus und erklärt dabei Begriffe und Hintergründe, automatisch oder über **Ausformulieren**, ohne konkrete Fakten zu erfinden
- **Übersetzen**-Button (文A) mit Zielsprachen, die ein Manager in den AI-Writer-Einstellungen festlegt
- Text zwischen `/"` und `"/` wird nie korrigiert oder übersetzt, z. B. `/"Müller & Söhne GmbH"/`; er gelangt nicht zum KI-Dienst
- **Antwortentwürfe** im E-Mail-Dialog: schreibt eine Antwort aus der eingegangenen Nachricht (ohne zitierten Verlauf) und ihrem Dokument, gesteuert durch optionale Stichpunkte
- **Anschreiben für Angebote** (ERPNext): schreibt den Brieftext eines Angebotsentwurfs aus Kunde, Ansprechpartner und Positionen, nie aus Preisen, als Brief oder gegliedert mit Überschriften
- Ein Eintrag **Hilfe** im Menü erklärt alle Funktionen
- Korrigiert die Markierung oder ohne Markierung das ganze Feld; Formatierungen bleiben erhalten
- Eine Vorschau hebt die Änderungen hervor, bevor sie den Text ersetzen (Übernehmen, Neu erzeugen, Verwerfen); ein Rückgängig-Schritt (Cmd+Z / Strg+Z) nimmt eine übernommene Korrektur zurück
- Erkennt die Sprache des Textes und antwortet in derselben Sprache
- Modell, Denkaufwand und System-Prompt sind einstellbar
- Zugriff über Rollen; Übersetzungen für Englisch, Deutsch, Spanisch, Französisch, Ukrainisch und Dänisch

| Nach einem Klick | Einfache Textfelder | Kommentarfeld |
|---|---|---|
| ![Korrigierte E-Mail](docs/screenshots/de-email-corrected.png) | ![Button in einem Textfeld](docs/screenshots/de-text-field.png) | ![Button im Kommentarfeld](docs/screenshots/de-comment.png) |

## Voraussetzungen

- Frappe Framework v15 oder v16 (ERPNext ist optional)
- Ein KI-Dienst: ein API-Schlüssel von Anthropic oder OpenAI, ein lokaler [Ollama](https://ollama.com/)-Server oder eine andere OpenAI-kompatible API

## Installation

```bash
cd ~/frappe-bench
bench get-app https://github.com/aepfelbirnen-de/frappe_ai_writer
bench --site ihre-site install-app frappe_ai_writer
bench --site ihre-site migrate
```

## Einrichtung

1. **AI-Writer-Einstellungen** öffnen (über den Arbeitsbereich **AI Writer** oder die App-Übersicht).
2. Den **Anbieter** wählen und, falls der Dienst einen braucht, den **API-Schlüssel** eintragen:

   | Anbieter | Basis-URL | Beispielmodell |
   |---|---|---|
   | Anthropic | (eingebaut) | `claude-haiku-5-5` (Standard) |
   | OpenAI | `https://api.openai.com/v1` (Standard) | ein Modell aus Ihrem OpenAI-Konto |
   | Ollama | `http://localhost:11434/v1` (Standard) | `llama3.2` |
   | OpenAI-kompatibel | die API-Adresse des Dienstes, z. B. Mistral, Google Gemini, OpenRouter, Groq, DeepSeek, LM Studio, vLLM | ein Modell dieses Dienstes |

3. Optional anpassen:
   - **Modell**: der Modellname beim Anbieter
   - **Denkaufwand** (nur Anthropic): wie gründlich das Modell vor der Antwort nachdenkt; `low` ist am schnellsten
   - **System-Prompt**: die Anweisungen, die bei jeder Anfrage mitgehen; leer lassen stellt den Standard wieder her
   - **Ausformulier-Prompt**: die Anweisungen fürs Ausformulieren von Notizen; leer lassen stellt den Standard wieder her
   - **Minimaler / maximaler Erweiterungsfaktor**: wie viel länger als die Notizen der ausformulierte Text ungefähr wird (standardmäßig 4 bis 10)
   - **Anschreiben-Feld** (ERPNext): das Textfeld im Angebot, das im Druckformat das Anschreiben enthält, z. B. ein eigenes Feld; leer lassen blendet den Button aus. **Anschreiben-Format** legt den Standard fest (Brief oder Gegliedert), **Anschreiben-Prompt** die gemeinsamen Regeln
   - **Vorschau vor dem Ersetzen**: bei langen Texten (Standard, ab 300 Zeichen), immer oder nie
   - **Übersetzungssprachen**: die Zielsprachen des Übersetzen-Buttons; leer lassen blendet ihn aus
   - **Verbrauch**: Token-Verbrauch heute, im laufenden Monat und gesamt, mit geschätzten Kosten anhand der eingestellten Preise; **Verbrauch pro Benutzer erfassen** (standardmäßig aus) ergänzt eine Tabelle pro Benutzer
4. Benutzern die Rolle **AI Writer User** geben. Ohne diese Rolle ist der Button nicht sichtbar.

| Rolle | Darf den Button nutzen | Darf die Einstellungen ändern |
|---|---|---|
| AI Writer User | ja | nein |
| AI Writer Manager | ja | ja |
| System Manager | nur mit einer der Rollen oben | ja |

## Datenschutz

Der zu korrigierende Text wird an den KI-Dienst gesendet, den Sie einstellen: Anthropic, OpenAI, einen anderen OpenAI-kompatiblen Anbieter oder Ihren eigenen Ollama-Server, bei dem er Ihr Netzwerk nicht verlässt. Die App speichert weder den Text noch die Antwort. Sie erfasst die Token-Anzahl pro Tag und Modus (ohne Text), damit Manager Verbrauch und Kosten sehen. Pro Benutzer wird nur gezählt, wenn **Verbrauch pro Benutzer erfassen** aktiviert ist; prüfen Sie vor dem Einschalten das in Ihrem Land geltende Recht, etwa zu Datenschutz und Mitbestimmung. Prüfen Sie die Bedingungen des Anbieters zu Datenverarbeitung und -aufbewahrung, bevor Sie die App mit personenbezogenen oder vertraulichen Daten nutzen.

## Sicherheit

- Der Korrektur-Endpunkt akzeptiert nur POST, prüft die Rolle des Benutzers und ist ratenbegrenzt.
- Vom Modell zurückgegebenes HTML wird bereinigt, bevor es in einen Editor eingefügt wird.
- Der API-Schlüssel liegt verschlüsselt in einem Passwortfeld und wird nie an den Browser gesendet.
- Die Basis-URL akzeptiert nur einfache http(s)-Adressen ohne Zugangsdaten; Weiterleitungen werden nicht verfolgt, und Fehlerprotokolle enthalten nur den HTTP-Status, nie den Inhalt der Antwort.

## Entwicklung

```bash
ruff check frappe_ai_writer/
ruff format --check frappe_ai_writer/
bench --site ihre-site run-tests --app frappe_ai_writer
```

## Lizenz

MIT, siehe [license.txt](license.txt).
