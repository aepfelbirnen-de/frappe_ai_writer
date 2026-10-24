# Copyright (c) 2026, aepfel+birnen IT GmbH and contributors
# For license information, please see license.txt

from __future__ import annotations

import hashlib

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Order
from frappe.query_builder.functions import Sum
from frappe.utils import add_months, flt, get_first_day, getdate, now_datetime, today

from frappe_ai_writer.budget import budget_status, clear_month_cache, notify_budget
from frappe_ai_writer.frappe_ai_writer.doctype.ai_writer_settings.ai_writer_settings import DEFAULT_PRICES

MANAGER_ROLES = ("System Manager", "AI Writer Manager")


class AIWriterUsage(Document):
    # begin: auto-generated types
    # This code is auto-generated. Do not modify anything in this block.

    from typing import TYPE_CHECKING

    if TYPE_CHECKING:
        from frappe.types import DF

        date: DF.Date
        input_tokens: DF.Int
        mode: DF.Literal[
            "correct", "expand", "formal", "casual", "translate", "cover_letter", "shorten", "plain", "reply", "summary"
        ]
        model: DF.Data | None
        output_tokens: DF.Int
        requests: DF.Int
        usage_key: DF.Data | None
        user: DF.Link | None
    # end: auto-generated types

    pass


def record_usage(usage_user: str | None, mode: str, model: str, input_tokens: int, output_tokens: int) -> None:
    """Add one request and its tokens to the row for this day, user, mode and model (user may be empty)."""
    usage_user = usage_user or ""
    date = today()
    key = hashlib.sha1(f"{date}|{usage_user}|{mode}|{model}".encode()).hexdigest()
    if not frappe.db.exists("AI Writer Usage", key):
        try:
            frappe.get_doc(
                {
                    "doctype": "AI Writer Usage",
                    "usage_key": key,
                    "date": date,
                    "user": usage_user or None,
                    "mode": mode,
                    "model": model,
                    "requests": 1,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                }
            ).insert(ignore_permissions=True)  # written by the system for the requesting user, never by hand
            _after_usage(usage_user)
            return
        except frappe.DuplicateEntryError:
            pass  # a parallel request created the row first; add to it below

    usage = frappe.qb.DocType("AI Writer Usage")
    (
        frappe.qb.update(usage)
        .set(usage.requests, usage.requests + 1)
        .set(usage.input_tokens, usage.input_tokens + input_tokens)
        .set(usage.output_tokens, usage.output_tokens + output_tokens)
        .set(usage.modified, now_datetime())
        .where(usage.name == key)
    ).run()
    _after_usage(usage_user)


def _after_usage(usage_user: str) -> None:
    clear_month_cache(usage_user)
    try:
        notify_budget()
    except Exception:
        # A failed notice must not roll back the recorded usage.
        frappe.log_error(title="AI Writer: budget notice failed")


@frappe.whitelist(methods=["GET"])
def get_usage_summary() -> dict:
    """Return token totals for today, this month and all time, and per user for this month if enabled."""
    if set(MANAGER_ROLES).isdisjoint(frappe.get_roles()):
        frappe.throw(_("You are not permitted to view AI Writer usage."), frappe.PermissionError)

    settings = frappe.get_cached_doc("AI Writer Settings")
    prices = get_prices(settings)
    month_start = get_first_day(today())

    periods = {
        "today": _totals(prices, from_date=getdate(today())),
        "month": _totals(prices, from_date=month_start),
        "total": _totals(prices),
    }

    result = {"periods": periods, "budget": budget_status(settings), "currency": "USD"}
    if not settings.track_usage_per_user:
        return {**result, "per_user": [], "per_user_enabled": False, "user_limit": 0}

    usage = frappe.qb.DocType("AI Writer Usage")
    rows = (
        frappe.qb.from_(usage)
        .select(
            usage.user,
            Sum(usage.requests).as_("requests"),
            Sum(usage.input_tokens).as_("input_tokens"),
            Sum(usage.output_tokens).as_("output_tokens"),
        )
        .where(usage.date >= month_start)
        .where(usage.date < add_months(month_start, 1))
        .where(usage.user.isnotnull())
        .groupby(usage.user)
        .orderby(Sum(usage.output_tokens), order=Order.desc)
    ).run(as_dict=True)
    names = dict(
        frappe.get_all(
            "User",
            filters={"name": ["in", [row.user for row in rows] or [""]]},
            fields=["name", "full_name"],
            as_list=True,
        )
    )
    per_user = [
        {**_with_cost(row, prices), "user": row.user, "full_name": names.get(row.user) or row.user} for row in rows
    ]
    return {**result, "per_user": per_user, "per_user_enabled": True, "user_limit": flt(settings.user_monthly_budget)}


def _totals(prices: tuple[float, float], from_date=None) -> dict:
    usage = frappe.qb.DocType("AI Writer Usage")
    query = frappe.qb.from_(usage).select(
        Sum(usage.requests).as_("requests"),
        Sum(usage.input_tokens).as_("input_tokens"),
        Sum(usage.output_tokens).as_("output_tokens"),
    )
    if from_date:
        query = query.where(usage.date >= from_date)
    return _with_cost(query.run(as_dict=True)[0], prices)


def _with_cost(row: dict, prices: tuple[float, float]) -> dict:
    input_tokens, output_tokens = int(row.get("input_tokens") or 0), int(row.get("output_tokens") or 0)
    return {
        "requests": int(row.get("requests") or 0),
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": round((input_tokens * prices[0] + output_tokens * prices[1]) / 1_000_000, 4),
    }


def get_prices(settings: Document) -> tuple[float, float]:
    """Return (input, output) USD price per million tokens; unset fields fall back to the defaults."""
    values = (settings.input_price_per_million, settings.output_price_per_million)
    return tuple(DEFAULT_PRICES[i] if value is None else flt(value) for i, value in enumerate(values))
