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

	const is_enabled = () => Boolean(frappe.boot.ai_writer?.enabled);

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
		const menu_button = make_button("ai-writer-menu-btn", caret_icon(), __("AI correction options"));
		menu_button.setAttribute("aria-haspopup", "menu");
		menu_button.setAttribute("aria-expanded", "false");

		const menu = document.createElement("div");
		menu.className = "ai-writer-menu";
		menu.setAttribute("role", "menu");
		menu.hidden = true;

		const close_menu = () => {
			menu.hidden = true;
			menu_button.setAttribute("aria-expanded", "false");
			document.removeEventListener("mousedown", on_outside_click, true);
			document.removeEventListener("keydown", on_escape, true);
		};
		const on_outside_click = (event) => {
			if (!group.contains(event.target)) close_menu();
		};
		const on_escape = (event) => {
			if (event.key === "Escape") close_menu();
		};

		for (const { mode, label } of MODES) {
			const item = make_button("ai-writer-menu-item", document.createTextNode(label()));
			item.setAttribute("role", "menuitem");
			item.addEventListener("click", () => {
				close_menu();
				correct(adapter, group, mode);
			});
			menu.append(item);
		}

		const divider = document.createElement("div");
		divider.className = "ai-writer-menu-divider";
		divider.setAttribute("role", "separator");
		const help_label = document.createDocumentFragment();
		help_label.append(help_icon(), document.createTextNode(__("Help")));
		const help_item = make_button("ai-writer-menu-item ai-writer-menu-help", help_label);
		help_item.setAttribute("role", "menuitem");
		help_item.addEventListener("click", () => {
			close_menu();
			show_help();
		});
		menu.append(divider, help_item);

		main_button.addEventListener("click", () => correct(adapter, group, "correct"));
		menu_button.addEventListener("click", () => {
			if (!menu.hidden) return close_menu();
			menu.hidden = false;
			menu_button.setAttribute("aria-expanded", "true");
			// Listeners live only while the menu is open, so closed editors leave nothing behind.
			document.addEventListener("mousedown", on_outside_click, true);
			document.addEventListener("keydown", on_escape, true);
		});

		group.append(main_button, menu_button, menu);
		return group;
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

		const notes = make_element("ul", "ai-writer-help-notes");
		for (const note of [
			__("Cmd+Z / Ctrl+Z undoes a change."),
			__("The answer is written in the language of the text."),
			__("The text is processed by Anthropic's Claude; AI Writer does not store it."),
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

	async function correct(adapter, group, mode) {
		if (group.classList.contains("ai-writer-busy") || adapter.is_disabled()) return;

		const request = adapter.read();
		if (!request) {
			frappe.show_alert({ message: __("Nothing to correct."), indicator: "orange" });
			return;
		}

		let result;
		set_busy(adapter, group, true);
		try {
			result = await frappe.xcall(METHOD, {
				text: request.text,
				mode,
				as_html: request.as_html,
				field_context: adapter.context,
			});
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
