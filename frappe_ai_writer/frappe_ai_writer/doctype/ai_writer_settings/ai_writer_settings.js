// Copyright (c) 2026, aepfel+birnen IT GmbH and contributors
// For license information, please see license.txt

// Wrapped so the helpers below do not leak into the global scope Frappe evaluates form scripts in.
(() => {
	frappe.ui.form.on("AI Writer Settings", {
		refresh(frm) {
			const needs_key = !frm.doc.provider || ["Anthropic", "OpenAI"].includes(frm.doc.provider);
			if (needs_key && !frm.doc.api_key) {
				frm.set_intro(__("Enter an API key to use AI correction."), "yellow");
			}
			render_usage(frm);
		},
	});

	async function render_usage(frm) {
		const wrapper = frm.fields_dict.usage_summary?.$wrapper?.[0];
		if (!wrapper) return;
		wrapper.replaceChildren(element("p", "text-muted", __("Loading…")));

		let summary;
		try {
			const response = await frappe.call({
				method: "frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_usage.ai_writer_usage.get_usage_summary",
				type: "GET",
			});
			summary = response.message;
		} catch (error) {
			wrapper.replaceChildren(element("p", "text-muted", __("Usage could not be loaded.")));
			return;
		}

		const number = (value) => format_number(value, null, 0);
		const cost = (value) => format_currency(value, summary.currency, 4);
		const columns = [__("Requests"), __("Input Tokens"), __("Output Tokens"), __("Estimated Cost")];
		const values = (row) => [number(row.requests), number(row.input_tokens), number(row.output_tokens), cost(row.cost)];

		const periods = table(
			["", ...columns],
			[
				[__("Today"), ...values(summary.periods.today)],
				[__("This Month"), ...values(summary.periods.month)],
				[__("Total"), ...values(summary.periods.total)],
			]
		);

		let per_user;
		if (!summary.per_user_enabled) {
			per_user = element(
				"p",
				"text-muted",
				__("Usage per user is not recorded. Enable Track Usage per User above to record it.")
			);
		} else if (summary.per_user.length) {
			per_user = table(
				[__("User"), ...columns],
				summary.per_user.map((row) => [row.full_name, ...values(row)]),
				// Users at their monthly limit are refused until next month.
				(index) => summary.user_limit > 0 && summary.per_user[index].cost >= summary.user_limit
			);
		} else {
			per_user = element("p", "text-muted", __("No usage recorded this month."));
		}

		const open_log = element("button", "btn btn-default btn-xs", __("Open Usage Log"));
		open_log.addEventListener("click", () => frappe.set_route("List", "AI Writer Usage"));

		wrapper.replaceChildren(
			...(summary.budget ? [budget_bar(summary.budget, summary.currency)] : []),
			periods,
			element("h6", "mt-4", __("Per User This Month")),
			per_user,
			open_log
		);
	}

	function budget_bar(budget, currency) {
		const result = element("div", "mb-4");
		const label = element(
			"div",
			"mb-1",
			__("Monthly budget: {0} of {1} used ({2} %)", [
				format_currency(budget.used, currency, 2),
				format_currency(budget.budget, currency, 2),
				format_number(budget.percent, null, 1),
			])
		);
		const progress = element("div", "progress");
		const level =
			budget.percent >= 100
				? "bg-danger"
				: budget.threshold && budget.percent >= budget.threshold
				? "bg-warning"
				: "bg-success";
		const bar = element("div", `progress-bar ${level}`);
		bar.setAttribute("role", "progressbar");
		bar.setAttribute("aria-valuenow", String(budget.percent));
		bar.setAttribute("aria-valuemin", "0");
		bar.setAttribute("aria-valuemax", "100");
		bar.style.width = `${Math.min(budget.percent, 100)}%`;
		progress.append(bar);
		result.append(label, progress);
		if (budget.percent >= 100) {
			result.append(
				element(
					"p",
					"text-muted small mt-1",
					budget.block
						? __("New requests are refused until next month or until the budget is raised.")
						: __("Requests are still processed because Block When Exceeded is off.")
				)
			);
		}
		return result;
	}

	function table(headers, rows, is_highlighted) {
		const result = element("table", "table table-bordered table-sm");
		const head = result.createTHead().insertRow();
		headers.forEach((text, index) => {
			const cell = element("th", index ? "text-right" : "", text);
			head.append(cell);
		});
		const body = result.createTBody();
		rows.forEach((row, row_index) => {
			const line = body.insertRow();
			if (is_highlighted?.(row_index)) line.className = "text-danger";
			row.forEach((text, index) => line.append(element("td", index ? "text-right" : "", text)));
		});
		return result;
	}

	function element(tag, class_name, text) {
		const node = document.createElement(tag);
		if (class_name) node.className = class_name;
		if (text) node.textContent = text;
		return node;
	}
})();
