"""Monthly budget: estimated costs per calendar month, warnings for managers and optional limits."""

from __future__ import annotations

import contextlib
import json

import frappe
from frappe import _
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification
from frappe.model.document import Document
from frappe.query_builder.functions import Sum
from frappe.utils import escape_html, flt, fmt_money, get_first_day, today
from frappe.utils.synchronization import filelock

CACHE_SECONDS = 60
WARNING = "warning"
EXCEEDED = "exceeded"


def check_budget(settings: Document, usage_user: str | None) -> None:
    """Refuse a request before it reaches the AI service when the monthly budget or the user's limit is used up."""
    budget = flt(settings.monthly_budget)
    if budget > 0 and settings.block_when_exceeded and month_cost(settings) >= budget:
        frappe.throw(_("The monthly AI budget is used up. Please contact your AI Writer manager."))

    # Per-user rows only exist while per-user tracking is on, so the limit depends on it.
    user_limit = flt(settings.user_monthly_budget)
    if (
        user_limit > 0
        and settings.track_usage_per_user
        and usage_user
        and month_cost(settings, usage_user) >= user_limit
    ):
        frappe.throw(_("Your monthly AI budget is used up. Please contact your AI Writer manager."))


def month_cost(settings: Document, user: str | None = None, cached: bool = True) -> float:
    """Estimated USD costs of the current calendar month, in total or for one user."""
    from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_usage.ai_writer_usage import get_prices

    input_tokens, output_tokens = _month_tokens(user, cached)
    input_price, output_price = get_prices(settings)
    return (input_tokens * input_price + output_tokens * output_price) / 1_000_000


def _month_tokens(user: str | None, cached: bool) -> tuple[int, int]:
    key = _cache_key(user)
    tokens = frappe.cache().get_value(key) if cached else None
    if tokens is None:
        usage = frappe.qb.DocType("AI Writer Usage")
        query = (
            frappe.qb.from_(usage)
            .select(Sum(usage.input_tokens), Sum(usage.output_tokens))
            .where(usage.date >= get_first_day(today()))
        )
        if user:
            query = query.where(usage.user == user)
        row = query.run()[0]
        tokens = [int(row[0] or 0), int(row[1] or 0)]
        frappe.cache().set_value(key, tokens, expires_in_sec=CACHE_SECONDS)
    return tokens[0], tokens[1]


def _cache_key(user: str | None) -> str:
    return f"ai_writer_month_tokens|{today()[:7]}|{user or ''}"


def clear_month_cache(user: str | None) -> None:
    keys = [_cache_key(None)]
    if user:
        keys.append(_cache_key(user))
    frappe.cache().delete_value(keys)


def notify_budget() -> None:
    """Notify managers once per month and budget when the warning threshold or the budget is reached."""
    settings = frappe.get_cached_doc("AI Writer Settings")
    budget = flt(settings.monthly_budget)
    if budget <= 0:
        return
    cost = month_cost(settings, cached=False)
    threshold = flt(settings.budget_warning_threshold)
    reached = [EXCEEDED] if cost >= budget else []
    if threshold and cost >= budget * threshold / 100:
        reached.append(WARNING)
    if not reached:
        return

    month = today()[:7]
    # Usage is recorded by parallel background jobs; the lock keeps them from sending the same notice twice.
    with filelock("ai_writer_budget_notice", timeout=10):
        notice = _load_notice()
        if notice.get("month") != month or flt(notice.get("budget")) != budget:
            notice = {"month": month, "budget": budget, "levels": []}
        new = [level for level in reached if level not in notice["levels"]]
        if not new:
            return
        notice["levels"].extend(new)
        frappe.db.set_single_value("AI Writer Settings", "budget_notice", json.dumps(notice))
        if not frappe.flags.in_test:
            frappe.db.commit()

    # Reaching the budget includes the warning, so only the most severe notice is sent.
    _send_notice(EXCEEDED if EXCEEDED in new else WARNING, cost, budget, settings)


def _load_notice() -> dict:
    try:
        notice = json.loads(frappe.db.get_single_value("AI Writer Settings", "budget_notice") or "{}")
    except ValueError:
        return {}
    return notice if isinstance(notice, dict) and isinstance(notice.get("levels"), list) else {}


def _send_notice(level: str, cost: float, budget: float, settings: Document) -> None:
    recipients = manager_emails()
    if not recipients:
        return
    used, total = fmt_money(cost, currency="USD"), fmt_money(budget, currency="USD")
    if level == EXCEEDED:
        subject = _("The monthly AI Writer budget is used up: {0} of {1}.").format(used, total)
        detail = (
            _("New requests are refused until next month or until the budget is raised in AI Writer Settings.")
            if settings.block_when_exceeded
            else _("Requests are still processed because Block When Exceeded is off in AI Writer Settings.")
        )
    else:
        subject = _("AI Writer has used {0} % of the monthly budget: {1} of {2}.").format(
            int(cost / budget * 100), used, total
        )
        detail = _("The usage per month and user is shown in AI Writer Settings.")

    enqueue_create_notification(
        recipients,
        {
            "type": "Alert",
            "document_type": "AI Writer Settings",
            "document_name": "AI Writer Settings",
            "subject": escape_html(subject),
            "email_content": escape_html(detail),
        },
    )
    # Alert notifications do not send emails themselves; without an outgoing account the desk notification remains.
    with contextlib.suppress(frappe.OutgoingEmailError):
        frappe.sendmail(
            recipients=recipients,
            subject=subject,
            message=f"<p>{escape_html(subject)}</p><p>{escape_html(detail)}</p>",
        )


def manager_emails() -> list[str]:
    """Emails of enabled AI Writer managers, or of System Managers if there is no AI Writer manager."""
    for role in ("AI Writer Manager", "System Manager"):
        users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent", distinct=True)
        emails = frappe.get_all(
            "User",
            filters={"name": ["in", users or [""]], "enabled": 1, "user_type": "System User", "email": ["is", "set"]},
            pluck="email",
        )
        if emails:
            return sorted(set(emails))
    return []


def budget_status(settings: Document) -> dict | None:
    """Current month's budget usage for the usage summary, or None without a budget."""
    budget = flt(settings.monthly_budget)
    if budget <= 0:
        return None
    used = month_cost(settings, cached=False)
    return {
        "budget": budget,
        "used": round(used, 4),
        "percent": round(used / budget * 100, 1),
        "threshold": flt(settings.budget_warning_threshold),
        "block": bool(settings.block_when_exceeded),
    }
