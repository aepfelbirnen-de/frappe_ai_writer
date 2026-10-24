// Adds an AI correction button to desk text fields:
// - Quill editors (Text Editor fields, email composer): in the toolbar
// - the comment box (Quill bubble theme): at the end of the field
// - plain textareas (Small Text, Text, Long Text): at the bottom right of the field
//
// Hooks into the controls instead of observing the DOM: the button is attached when the
// field is built, with direct access to its editor, so no global MutationObserver is needed.
(function () {
	const PATCHED = Symbol.for("frappe_ai_writer.patched");
	const METHOD = "frappe_ai_writer.api.correction.correct_text";
	const COVER_LETTER_METHOD = "frappe_ai_writer.api.cover_letter.write_cover_letter";
	const MODES = [
		{
			mode: "correct",
			label: () => __("Correct"),
			help: () =>
				__(
					"Fixes spelling, grammar and punctuation. Bullet-point notes are written out as complete text."
				),
		},
		{
			mode: "expand",
			label: () => __("Write out"),
			help: () => __("Turns notes and bullet points into complete, detailed text and explains terms and background, without inventing specific facts."),
		},
		{
			mode: "formal",
			label: () => __("More formal"),
			help: () => __("Corrects the text and makes the tone more formal and business-like."),
		},
		{
			mode: "casual",
			label: () => __("More casual"),
			help: () => __("Corrects the text and makes the tone friendlier and less formal."),
		},
	];

	const LOGO_URL = "/assets/frappe_ai_writer/images/frappe_ai_writer-logo.svg";

	const is_enabled = () => Boolean(frappe.boot.ai_writer?.enabled);

	localize_change_log();
	setup_cover_letter();
	$(document).one("app_ready", () => setTimeout(show_change_log_to_writers, 1000));

	patch(frappe.ui.form.ControlTextEditor, "make_quill_editor", function () {
		if (this.quill) attach_to_quill(this.quill, field_context(this));
	});

	// ControlCode (Ace) and ControlTextEditor also extend ControlText but override make_input
	// without calling it, so only real textareas reach this hook.
	patch(frappe.ui.form.ControlText, "make_input", function () {
		if (this.only_input || this.in_grid?.()) return;
		const textarea = this.$input?.[0];
		if (textarea?.tagName === "TEXTAREA") {
			attach_to_textarea(textarea, $(this.input_area)[0], field_context(this));
		}
	});

	// Tells the model what the text is for (e.g. "Description · Task"), so written-out notes fit the field.
	function field_context(control) {
		const label = control.df?.label || control.df?.fieldtype;
		const doctype = control.frm?.doctype || control.doctype;
		return [label, doctype].filter(Boolean).join(" · ");
	}

	// Frappe shows the update dialog from frappe.boot.change_log shortly after load and never translates
	// it; this swaps in the user's language for this app's entries before the dialog opens.
	function localize_change_log() {
		const translated = frappe.boot.ai_writer_change_log;
		if (!translated || !Array.isArray(frappe.boot.change_log)) return;
		for (const entry of frappe.boot.change_log) {
			if (entry.title !== translated.title || !Array.isArray(entry.change_log)) continue;
			entry.change_log = entry.change_log.map(([version, markdown]) => [
				version,
				translated.versions[version] || markdown,
			]);
		}
	}

	// Quotation cover letters: the server reads the quotation itself (without prices); the current field
	// content is sent along as notes for the letter.
	function setup_cover_letter() {
		const fieldname = frappe.boot.ai_writer?.cover_letter_field;
		if (!fieldname) return;
		frappe.ui.form.on("Quotation", {
			refresh(frm) {
				const field = frm.fields_dict[fieldname];
				field?.$wrapper[0].querySelector(".ai-writer-cover-letter-btn")?.remove();
				if (!is_enabled() || frm.doc.docstatus !== 0 || !field) return;
				frm.add_custom_button(__("Write Cover Letter"), () => write_cover_letter(frm, fieldname), __("Actions"));

				// A second button right at the field, where people look for it.
				const label = field.$wrapper[0].querySelector(".control-label");
				if (!label) return;
				const content = document.createDocumentFragment();
				content.append(sparkle_icon(), document.createTextNode(__("Write Cover Letter")));
				const button = make_button("btn btn-xs btn-default ai-writer-cover-letter-btn", content);
				button.addEventListener("click", () => write_cover_letter(frm, fieldname));
				label.after(button);
			},
		});
	}

	async function write_cover_letter(frm, fieldname) {
		try {
			// The server reads the saved quotation, so unsaved items would be missing.
			if (frm.is_dirty() || frm.is_new()) await frm.save();
		} catch (error) {
			// frm.save already shows the reason to the user.
			console.error(error);
			return;
		}

		let style = frappe.boot.ai_writer?.cover_letter_style || "Letter";
		const letter = await generate_cover_letter(frm, fieldname, style);
		if (letter === null) return;

		const regenerate = async () => {
			const html = await generate_cover_letter(frm, fieldname, style);
			if (html !== null) dialog.set_value("letter", html);
		};
		const dialog = new frappe.ui.Dialog({
			title: __("Cover Letter"),
			size: "large",
			fields: [
				{
					fieldtype: "Select",
					fieldname: "style",
					label: __("Format"),
					options: [
						{ value: "Letter", label: __("Letter") },
						{ value: "Structured", label: __("Structured") },
					],
					default: style,
					onchange() {
						const value = dialog.get_value("style");
						if (!value || value === style) return;
						style = value;
						regenerate();
					},
				},
				{ fieldtype: "Text Editor", fieldname: "letter", label: __("Preview"), default: letter },
			],
			primary_action_label: __("Apply"),
			primary_action(values) {
				frm.set_value(fieldname, values.letter);
				dialog.hide();
				frappe.show_alert({ message: __("Cover letter applied. Save the quotation to keep it."), indicator: "green" });
			},
			secondary_action_label: __("Regenerate"),
			secondary_action: regenerate,
		});
		dialog.show();
	}

	// Returns the sanitized letter HTML, or null if the request failed (the server message is already shown).
	async function generate_cover_letter(frm, fieldname, style) {
		frappe.dom.freeze(__("Writing cover letter…"));
		try {
			return await frappe.xcall(COVER_LETTER_METHOD, {
				quotation: frm.doc.name,
				notes: frm.doc[fieldname] || "",
				style,
			});
		} catch (error) {
			console.error(error);
			return null;
		} finally {
			frappe.dom.unfreeze();
		}
	}

	// Frappe opens the update dialog only for System Managers (v16: also Workspace Managers). Other
	// AI Writer users get this app's part of it, with the same opt-outs and once per update: closing
	// it records the seen versions just like Frappe's dialog does.
	function show_change_log_to_writers() {
		const title = frappe.boot.ai_writer_change_log?.title;
		if (!frappe.boot.ai_writer || !title || frappe_shows_change_log()) return;
		if (window.Cypress || navigator.webdriver || frappe.defaults.is_enabled("disable_change_log_notification")) {
			return;
		}

		const change_log = (frappe.boot.change_log || []).filter((entry) => entry.title === title);
		if (!change_log.length) return;

		const dialog = frappe.msgprint({
			message: frappe.render_template("change_log", { change_log }),
			title: __("Updated To A New Version 🎉"),
			wide: true,
		});
		dialog.keep_open = true;
		dialog.custom_onhide = () => frappe.call({ method: "frappe.utils.change_log.update_last_known_versions" });
	}

	function frappe_shows_change_log() {
		const roles = frappe.user_roles || [];
		const frappe_major = parseInt(frappe.boot.versions?.frappe, 10) || 15;
		return roles.includes("System Manager") || (frappe_major >= 16 && roles.includes("Workspace Manager"));
	}

	function patch(Control, method, after) {
		// Own-property check: ControlTextEditor inherits from ControlText, so an inherited flag
		// would make the second patch skip itself.
		if (!Control || Object.prototype.hasOwnProperty.call(Control.prototype, PATCHED)) return;
		Control.prototype[PATCHED] = true;
		const original = Control.prototype[method];
		Control.prototype[method] = function (...args) {
			const result = original.apply(this, args);
			if (is_enabled()) after.call(this);
			return result;
		};
	}

	function attach_to_quill(quill, context) {
		// Bubble-theme editors (the comment box) only show a toolbar while text is selected,
		// so the button sits permanently at the end of the field instead.
		const inline = quill.container.classList.contains("ql-bubble");
		const host = inline ? quill.container : quill.getModule("toolbar")?.container;
		if (!host || host.querySelector(".ai-writer-group")) return;

		const class_name = inline ? "ai-writer-group ai-writer-inline" : "ql-formats ai-writer-group";
		host.append(make_group(class_name, quill_adapter(quill, context)));
		if (inline) quill.container.classList.add("ai-writer-has-inline");
	}

	function attach_to_textarea(textarea, host, context) {
		if (!host || host.querySelector(".ai-writer-group")) return;
		host.append(
			make_group("ai-writer-group ai-writer-inline ai-writer-textarea", textarea_adapter(textarea, context))
		);
		host.classList.add("ai-writer-has-textarea");
	}

	// An adapter reads the text to correct and writes the result back for one kind of editor:
	// read() returns { text, as_html, apply(result) } or null when there is nothing to correct.
	function quill_adapter(quill, context) {
		return {
			context,
			is_disabled: () => quill.container.classList.contains("ql-disabled"),
			// Edits during the request would shift the range the result is written back to.
			lock: (locked) => quill.enable(!locked),
			read() {
				const range = quill.getSelection(true);
				if (range?.length) {
					const text = quill.getText(range.index, range.length);
					if (!text.trim()) return null;
					return { text, as_html: 0, apply: (result) => replace_quill_range(quill, range, text, result) };
				}
				if (!quill.getText().trim()) return null;
				// The whole document goes as HTML so formatting survives. Reading innerHTML is safe;
				// the server sanitizes the HTML before it comes back.
				return {
					text: quill.root.innerHTML,
					as_html: 1,
					apply: (result) => quill.clipboard.dangerouslyPasteHTML(result, "user"),
				};
			},
		};
	}

	function textarea_adapter(textarea, context) {
		return {
			context,
			is_disabled: () => textarea.disabled || textarea.readOnly,
			lock: (locked) => (textarea.readOnly = locked),
			read() {
				const { selectionStart: start, selectionEnd: end, value } = textarea;
				const has_selection = end > start;
				const text = has_selection ? value.slice(start, end) : value;
				if (!text.trim()) return null;
				const [from, to] = has_selection ? [start, end] : [0, value.length];
				return { text, as_html: 0, apply: (result) => replace_textarea_range(textarea, from, to, text, result) };
			},
		};
	}

	function make_group(class_name, adapter) {
		const group = document.createElement("span");
		group.className = class_name;

		const main_button = make_button("ai-writer-btn", sparkle_icon(), __("AI correction"));
		main_button.addEventListener("click", () => correct(adapter, group, "correct"));

		const menu_button = make_button("ai-writer-menu-btn", caret_icon(), __("AI correction options"));
		const mode_items = MODES.map(({ mode, label }) => ({
			label: label(),
			action: () => correct(adapter, group, mode),
		}));
		mode_items.push(
			{ divider: true },
			{ label: __("Help"), icon: help_icon(), class_name: "ai-writer-menu-help", action: show_help }
		);
		group.append(main_button, menu_button, make_menu(group, menu_button, mode_items));

		const languages = frappe.boot.ai_writer?.languages || [];
		if (languages.length) {
			const translate_button = make_button("ai-writer-translate-btn", translate_icon(), __("Translate"));
			const language_items = languages.map(({ code, name }) => ({
				label: name,
				action: () => correct(adapter, group, "translate", code),
			}));
			group.append(translate_button, make_menu(group, translate_button, language_items));
		}
		return group;
	}

	// A dropdown opened by its trigger button. Listeners live only while it is open, so closed
	// editors leave nothing behind; clicking another trigger in the group closes it.
	function make_menu(group, trigger, items) {
		const menu = make_element("div", "ai-writer-menu");
		menu.setAttribute("role", "menu");
		menu.hidden = true;
		trigger.setAttribute("aria-haspopup", "menu");
		trigger.setAttribute("aria-expanded", "false");

		const close = () => {
			menu.hidden = true;
			trigger.setAttribute("aria-expanded", "false");
			document.removeEventListener("mousedown", on_outside_click, true);
			document.removeEventListener("keydown", on_escape, true);
		};
		const on_outside_click = (event) => {
			if (!menu.contains(event.target) && !trigger.contains(event.target)) close();
		};
		const on_escape = (event) => {
			if (event.key === "Escape") close();
		};

		for (const item of items) {
			if (item.divider) {
				const divider = make_element("div", "ai-writer-menu-divider");
				divider.setAttribute("role", "separator");
				menu.append(divider);
				continue;
			}
			const content = document.createDocumentFragment();
			if (item.icon) content.append(item.icon);
			content.append(document.createTextNode(item.label));
			const button = make_button(["ai-writer-menu-item", item.class_name].filter(Boolean).join(" "), content);
			button.setAttribute("role", "menuitem");
			button.addEventListener("click", () => {
				close();
				item.action();
			});
			menu.append(button);
		}

		trigger.addEventListener("click", () => {
			if (!menu.hidden) return close();
			// Toolbar menus open under their own trigger; inline menus stay right-aligned via CSS.
			if (!group.classList.contains("ai-writer-inline")) menu.style.left = `${trigger.offsetLeft}px`;
			menu.hidden = false;
			trigger.setAttribute("aria-expanded", "true");
			document.addEventListener("mousedown", on_outside_click, true);
			document.addEventListener("keydown", on_escape, true);
		});
		return menu;
	}

	// Quill-style 18x18 icons in currentColor, so they follow the surrounding button's color.
	// The third star is invisible until the busy animation lets it twinkle.
	function sparkle_icon() {
		return make_svg([
			["path", "ql-fill", "M8 1.5C8.6 5.6 9.9 6.9 14 7.5C9.9 8.1 8.6 9.4 8 13.5C7.4 9.4 6.1 8.1 2 7.5C6.1 6.9 7.4 5.6 8 1.5Z"],
			["path", "ql-fill", "M14 11C14.3 12.8 14.7 13.2 16.5 13.5C14.7 13.8 14.3 14.2 14 16C13.7 14.2 13.3 13.8 11.5 13.5C13.3 13.2 13.7 12.8 14 11Z"],
			["path", "ql-fill ai-writer-spark", "M3.5 12.5C3.7 13.86 4.14 14.3 5.5 14.5C4.14 14.7 3.7 15.14 3.5 16.5C3.3 15.14 2.86 14.7 1.5 14.5C2.86 14.3 3.3 13.86 3.5 12.5Z"],
		]);
	}

	function caret_icon() {
		return make_svg([["path", "ql-stroke", "M6 7.5L9 10.5L12 7.5"]]);
	}

	// The "文A" language symbol, as used for language selection on Wikipedia.
	function translate_icon() {
		return make_svg([
			["path", "ql-stroke", "M1.5 3.5H8.5"],
			["path", "ql-stroke", "M5 1.5V3.5"],
			["path", "ql-stroke", "M7.5 3.5C6.9 6.6 4.9 8.9 1.8 10.2"],
			["path", "ql-stroke", "M3.3 5.6C4.2 7.6 5.8 9.1 8 10"],
			["path", "ql-stroke", "M9.5 16.5L12.75 8L16 16.5"],
			["path", "ql-stroke", "M10.7 13.5H14.8"],
		]);
	}

	function help_icon() {
		return make_svg([
			["path", "ql-stroke", "M9 2A7 7 0 1 1 9 16A7 7 0 1 1 9 2Z"],
			["path", "ql-stroke", "M7 7.2A2 2 0 1 1 9.9 8.9C9.3 9.3 9 9.7 9 10.4V10.8"],
			["path", "ql-fill", "M9 12.4A0.8 0.8 0 1 1 9 14A0.8 0.8 0 1 1 9 12.4Z"],
		]);
	}

	// One dialog per page, built lazily on first use.
	let help_dialog;
	function show_help() {
		if (!help_dialog) {
			help_dialog = new frappe.ui.Dialog({ title: __("How AI Writer works"), size: "small" });
			const logo = make_element("img", "ai-writer-help-logo");
			logo.src = LOGO_URL;
			logo.alt = "";
			help_dialog.$wrapper.find(".modal-title").prepend(logo);
			help_dialog.$body.append(make_help_content());
		}
		help_dialog.show();
	}

	function make_help_content() {
		const root = make_element("div", "ai-writer-help");
		root.append(
			make_element(
				"p",
				null,
				__(
					"Click ✦ to correct the text right away, or open the arrow menu to choose a mode. Without a selection the whole field is used; with a selection only the selected part."
				)
			)
		);

		const modes = make_element("dl");
		for (const { label, help } of MODES) {
			modes.append(make_element("dt", null, label()), make_element("dd", null, help()));
		}
		modes.append(
			make_element("dt", null, __("Translate")),
			make_element(
				"dd",
				null,
				__(
					"The language button (文A) translates the text into one of the languages a manager has enabled in AI Writer Settings."
				)
			)
		);

		if (frappe.boot.ai_writer?.cover_letter_field) {
			modes.append(
				make_element("dt", null, __("Write Cover Letter")),
				make_element(
					"dd",
					null,
					__(
						"In a draft quotation, Actions → Write Cover Letter writes the letter text from the customer, contact and line items, as a letter or with headings (Format in the preview). Prices and totals are never sent. Notes already in the field are worked into the letter."
					)
				)
			);
		}

		const notes = make_element("ul", "ai-writer-help-notes");
		for (const note of [
			__('Text between /" and "/ is never corrected or translated, for example /"Müller & Söhne GmbH"/.'),
			__("Depending on AI Writer Settings, results are shown in a preview first, where you can apply, regenerate or discard them."),
			__("Cmd+Z / Ctrl+Z undoes a change."),
			__("The answer is written in the language of the text."),
			__("The text is processed by the AI service set in AI Writer Settings; AI Writer does not store it."),
		]) {
			notes.append(make_element("li", null, note));
		}

		root.append(modes, notes);
		return root;
	}

	function make_element(tag, class_name, text) {
		const element = document.createElement(tag);
		if (class_name) element.className = class_name;
		if (text) element.textContent = text;
		return element;
	}

	function make_svg(shapes) {
		const ns = "http://www.w3.org/2000/svg";
		const svg = document.createElementNS(ns, "svg");
		svg.setAttribute("viewBox", "0 0 18 18");
		svg.setAttribute("aria-hidden", "true");
		for (const [tag, class_name, d] of shapes) {
			const shape = document.createElementNS(ns, tag);
			shape.setAttribute("class", class_name);
			shape.setAttribute("d", d);
			svg.append(shape);
		}
		return svg;
	}

	function make_button(class_name, content, title) {
		const button = document.createElement("button");
		button.type = "button";
		button.className = class_name;
		button.append(content);
		if (title) {
			button.title = title;
			button.setAttribute("aria-label", title);
		}
		// Keeps focus and selection inside the editor while clicking.
		button.addEventListener("mousedown", (event) => event.preventDefault());
		return button;
	}

	async function correct(adapter, group, mode, target_language) {
		if (group.classList.contains("ai-writer-busy") || adapter.is_disabled()) return;

		const request = adapter.read();
		if (!request) {
			frappe.show_alert({ message: __("Nothing to correct."), indicator: "orange" });
			return;
		}

		let result;
		// The field stays locked while the preview is open, so the range written back cannot shift.
		set_busy(adapter, group, true);
		try {
			for (;;) {
				result = await frappe.xcall(METHOD, {
					text: request.text,
					mode,
					as_html: request.as_html,
					field_context: adapter.context,
					target_language,
				});
				if (!needs_preview(request, result)) break;
				group.classList.remove("ai-writer-busy");
				const decision = await show_preview(request, result);
				if (decision === "discard") return;
				if (decision === "apply") break;
				group.classList.add("ai-writer-busy");
			}
		} catch (error) {
			// frappe.xcall already shows the server message to the user.
			console.error(error);
			return;
		} finally {
			// Must run before writing back: a disabled Quill drops changes with source "user".
			set_busy(adapter, group, false);
		}

		request.apply(result);
		frappe.show_alert({ message: __("Text updated"), indicator: "green" });
	}

	function needs_preview(request, result) {
		const { mode, min_chars } = frappe.boot.ai_writer?.preview || {};
		if (mode === "Never") return false;
		if (mode === "Always") return true;
		const longest = Math.max(visible_text(request.text, request.as_html).length, visible_text(result, request.as_html).length);
		return longest >= (min_chars ?? 300);
	}

	// Resolves to "apply", "regenerate" or "discard"; closing the dialog counts as discard.
	function show_preview(request, result) {
		return new Promise((resolve) => {
			let decided = false;
			const decide = (decision) => {
				if (decided) return;
				decided = true;
				resolve(decision);
				dialog.hide();
			};
			const dialog = new frappe.ui.Dialog({
				title: __("Preview"),
				size: "large",
				fields: [{ fieldtype: "HTML", fieldname: "changes" }],
				primary_action_label: __("Apply"),
				primary_action: () => decide("apply"),
				secondary_action_label: __("Regenerate"),
				secondary_action: () => decide("regenerate"),
			});
			dialog.onhide = () => decide("discard");
			dialog.fields_dict.changes.$wrapper[0].replaceChildren(
				render_changes(visible_text(request.text, request.as_html), visible_text(result, request.as_html))
			);
			dialog.show();
		});
	}

	// Visible text only: DOMParser builds an inert document, so nothing from the HTML is executed or inserted.
	function visible_text(text, as_html) {
		if (!as_html) return text;
		const doc = new DOMParser().parseFromString(text, "text/html");
		doc.querySelectorAll("p, li, h1, h2, h3, h4, h5, h6, br, div, tr").forEach((node) => node.after("\n"));
		return doc.body.textContent.replace(/\n{3,}/g, "\n\n").trim();
	}

	function render_changes(before, after) {
		const root = make_element("div", "ai-writer-preview");
		const before_words = before.match(/\S+\s*/g) || [];
		const after_words = after.match(/\S+\s*/g) || [];
		// The word-level LCS needs len(before) x len(after) cells; very long texts are shown side by side instead.
		if (before_words.length * after_words.length > 2_500_000) {
			root.append(
				make_element("h6", null, __("Before")),
				make_element("div", "ai-writer-preview-text", before),
				make_element("h6", "mt-3", __("After")),
				make_element("div", "ai-writer-preview-text", after)
			);
			return root;
		}
		root.append(make_element("p", "text-muted small", __("Removed text is struck through, added text is highlighted.")));
		const text = make_element("div", "ai-writer-preview-text");
		for (const [type, words] of diff_words(before_words, after_words)) {
			text.append(type === "same" ? document.createTextNode(words) : make_element(type === "added" ? "ins" : "del", null, words));
		}
		root.append(text);
		return root;
	}

	// Returns [["same" | "added" | "removed", text], ...] from a longest-common-subsequence table over words.
	function diff_words(before, after) {
		const n = before.length;
		const m = after.length;
		const key = (word) => word.trim();
		const table = new Uint32Array((n + 1) * (m + 1));
		for (let i = n - 1; i >= 0; i--) {
			for (let j = m - 1; j >= 0; j--) {
				table[i * (m + 1) + j] =
					key(before[i]) === key(after[j])
						? table[(i + 1) * (m + 1) + j + 1] + 1
						: Math.max(table[(i + 1) * (m + 1) + j], table[i * (m + 1) + j + 1]);
			}
		}
		const parts = [];
		const push = (type, word) => {
			const last = parts[parts.length - 1];
			if (last && last[0] === type) last[1] += word;
			else parts.push([type, word]);
		};
		let i = 0;
		let j = 0;
		while (i < n && j < m) {
			if (key(before[i]) === key(after[j])) {
				push("same", after[j]);
				i++;
				j++;
			} else if (table[(i + 1) * (m + 1) + j] >= table[i * (m + 1) + j + 1]) {
				push("removed", before[i++]);
			} else {
				push("added", after[j++]);
			}
		}
		while (i < n) push("removed", before[i++]);
		while (j < m) push("added", after[j++]);
		return parts;
	}

	function with_original_whitespace(original, result) {
		// The model trims surrounding whitespace; restore it so words don't run together.
		return original.match(/^\s*/)[0] + result.trim() + original.match(/\s*$/)[0];
	}

	function replace_quill_range(quill, range, original, result) {
		const replacement = with_original_whitespace(original, result);
		const format = quill.getFormat(range.index, range.length);
		const Delta = quill.constructor.import("delta");

		// One delta keeps the replacement a single undo step.
		quill.updateContents(
			new Delta().retain(range.index).delete(range.length).insert(replacement, format),
			"user"
		);
		quill.setSelection(range.index, replacement.length, "silent");
	}

	function replace_textarea_range(textarea, from, to, original, result) {
		const replacement = with_original_whitespace(original, result);
		textarea.focus();
		textarea.setSelectionRange(from, to);
		// execCommand keeps the browser's native undo history (Cmd+Z); setRangeText is the fallback.
		if (!document.execCommand("insertText", false, replacement)) {
			textarea.setRangeText(replacement, from, to, "end");
		}
		textarea.setSelectionRange(from, from + replacement.length);
		// Frappe writes textarea values to the model on "change".
		textarea.dispatchEvent(new Event("change", { bubbles: true }));
	}

	function set_busy(adapter, group, busy) {
		group.classList.toggle("ai-writer-busy", busy);
		group.querySelectorAll("button").forEach((button) => (button.disabled = busy));
		adapter.lock(busy);
	}
})();
