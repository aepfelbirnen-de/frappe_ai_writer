// Copyright (c) 2026, aepfel+birnen IT GmbH and contributors
// For license information, please see license.txt

frappe.ui.form.on("AI Writer Settings", {
	refresh(frm) {
		if (!frm.doc.api_key) {
			frm.set_intro(__("Enter an Anthropic API key to use AI correction."), "yellow");
		}
	},
});
