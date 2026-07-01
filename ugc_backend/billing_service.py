"""Stripe subscription fulfillment — shared by webhooks and checkout confirm."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import stripe

from ugc_db.db_manager import (
    add_credits,
    get_plan_by_id,
    get_user_id_by_stripe_customer,
    upsert_subscription,
)


def _to_dict(obj: Any) -> dict[str, Any]:
    """Normalize Stripe SDK objects to plain dicts for safe key access."""
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    try:
        return dict(obj)
    except (TypeError, ValueError):
        return {}


def resolve_invoice_subscription_id(invoice: dict[str, Any]) -> str | None:
    """Extract subscription ID from a Stripe Invoice (supports legacy + newer shapes)."""
    sub_id = invoice.get("subscription")
    if sub_id:
        return sub_id if isinstance(sub_id, str) else getattr(sub_id, "id", None) or sub_id.get("id")

    parent = invoice.get("parent") or {}
    sub_details = parent.get("subscription_details") or {}
    nested = sub_details.get("subscription")
    if nested:
        return nested if isinstance(nested, str) else getattr(nested, "id", None) or nested.get("id")
    return None


def resolve_subscription_metadata(
    sub: dict[str, Any],
    invoice: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve plan_id / supabase_user_id from subscription or invoice payloads."""
    sub_meta = _to_dict(sub.get("metadata"))
    if sub_meta.get("plan_id") and sub_meta.get("supabase_user_id"):
        return sub_meta

    if invoice:
        parent = invoice.get("parent") or {}
        parent_meta = _to_dict((parent.get("subscription_details") or {}).get("metadata"))
        if parent_meta.get("plan_id") and parent_meta.get("supabase_user_id"):
            return parent_meta

        inv_sub_meta = _to_dict((invoice.get("subscription_details") or {}).get("metadata"))
        if inv_sub_meta.get("plan_id") and inv_sub_meta.get("supabase_user_id"):
            return inv_sub_meta

        lines = (invoice.get("lines") or {}).get("data") or []
        if lines:
            line_meta = _to_dict(lines[0].get("metadata"))
            if line_meta.get("plan_id") and line_meta.get("supabase_user_id"):
                return line_meta

    return sub_meta


def _extract_period_timestamps(
    sub: dict[str, Any],
    invoice: dict[str, Any] | None = None,
) -> tuple[int, int]:
    """Return Unix timestamps for billing period start/end (Basil + legacy + invoice fallbacks)."""
    items = (sub.get("items") or {}).get("data") or []
    if items:
        item = items[0]
        start = item.get("current_period_start")
        end = item.get("current_period_end")
        if start and end:
            return int(start), int(end)

    start = sub.get("current_period_start")
    end = sub.get("current_period_end")
    if start and end:
        return int(start), int(end)

    if invoice:
        lines = (invoice.get("lines") or {}).get("data") or []
        if lines:
            period = lines[0].get("period") or {}
            line_start = period.get("start")
            line_end = period.get("end")
            if line_start and line_end:
                return int(line_start), int(line_end)

        inv_start = invoice.get("period_start")
        inv_end = invoice.get("period_end")
        if inv_start and inv_end:
            return int(inv_start), int(inv_end)

    raise KeyError(
        "Could not resolve billing period from subscription or invoice "
        f"(sub={sub.get('id')!r}, invoice={invoice.get('id') if invoice else None!r})"
    )


def period_bounds(
    sub: dict[str, Any],
    invoice: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """ISO period bounds for DB storage — shared by webhooks and subscription updates."""
    start_ts, end_ts = _extract_period_timestamps(sub, invoice)
    period_start = datetime.fromtimestamp(start_ts, tz=timezone.utc).isoformat()
    period_end = datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat()
    return period_start, period_end


def _subscription_interval(sub: dict[str, Any]) -> str:
    items = (sub.get("items") or {}).get("data") or []
    if items:
        return items[0].get("price", {}).get("recurring", {}).get("interval", "month")
    return "month"


def fulfill_subscription(
    user_id: str,
    plan_id: str,
    subscription_id: str,
    *,
    invoice_id: str | None = None,
    session_id: str | None = None,
    sub: Any = None,
    invoice: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Upsert DB subscription and grant plan credits. Idempotent per invoice or session."""
    plan = get_plan_by_id(plan_id)
    if not plan:
        print(f"[Stripe] fulfill_subscription skipped: unknown plan_id={plan_id!r}")
        return None

    if sub is None:
        sub = stripe.Subscription.retrieve(subscription_id)
    sub_dict = _to_dict(sub)

    period_start, period_end = period_bounds(sub_dict, invoice)

    upsert_subscription(
        user_id=user_id,
        plan_id=plan_id,
        stripe_subscription_id=subscription_id,
        status="active",
        period_start=period_start,
        period_end=period_end,
    )

    interval = _subscription_interval(sub_dict)
    credit_multiplier = 12 if interval == "year" else 1
    credit_amount = plan["credits_monthly"] * credit_multiplier

    if interval == "year":
        desc = (
            f"{plan['name']} annual plan: {credit_amount} credits "
            f"({plan['credits_monthly']}/mo × 12)"
        )
    else:
        desc = f"{plan['name']} plan: {plan['credits_monthly']} monthly credits"

    metadata: dict[str, Any] = {
        "stripe_subscription_id": subscription_id,
        "period_start": period_start,
        "period_end": period_end,
        "billing_interval": interval,
        "stripe_allotment_key": f"{subscription_id}:{period_start}",
    }
    if invoice_id:
        metadata["stripe_invoice_id"] = invoice_id
    if session_id:
        metadata["stripe_session_id"] = session_id

    add_credits(
        user_id=user_id,
        amount=credit_amount,
        tx_type="monthly_allotment",
        description=desc,
        metadata=metadata,
    )
    print(
        f"[Stripe] Fulfilled {credit_amount} credits for user {user_id} "
        f"({plan['name']}, {interval}, sub={subscription_id})"
    )
    return {
        "plan_name": plan["name"],
        "credits_added": credit_amount,
        "subscription_id": subscription_id,
    }


def fulfill_from_checkout_session(session: Any) -> dict[str, Any] | None:
    """Fulfill a paid subscription checkout session."""
    session_dict = _to_dict(session)
    metadata = session_dict.get("metadata") or {}
    user_id = metadata.get("supabase_user_id")
    plan_id = metadata.get("plan_id")
    subscription_id = session_dict.get("subscription")
    if subscription_id and not isinstance(subscription_id, str):
        subscription_id = getattr(subscription_id, "id", None) or subscription_id.get("id")

    if not user_id or not plan_id or not subscription_id:
        print(
            "[Stripe] checkout.session.completed subscription skipped: "
            f"user_id={user_id!r} plan_id={plan_id!r} subscription_id={subscription_id!r}"
        )
        return None

    if session_dict.get("payment_status") not in ("paid", "no_payment_required"):
        print(
            "[Stripe] checkout.session.completed subscription skipped: "
            f"payment_status={session_dict.get('payment_status')!r}"
        )
        return None

    return fulfill_subscription(
        user_id,
        plan_id,
        subscription_id,
        session_id=session_dict.get("id"),
    )


def fulfill_from_invoice_paid(invoice: Any) -> dict[str, Any] | None:
    """Fulfill subscription renewal or first invoice."""
    invoice_dict = _to_dict(invoice)
    subscription_id = resolve_invoice_subscription_id(invoice_dict)
    customer_id = invoice_dict.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")

    if not subscription_id:
        print(
            "[Stripe] invoice.paid skipped: no subscription on invoice "
            f"(invoice={invoice_dict.get('id')!r})"
        )
        return None

    sub = stripe.Subscription.retrieve(subscription_id)
    sub_dict = _to_dict(sub)
    meta = resolve_subscription_metadata(sub_dict, invoice_dict)
    user_id = meta.get("supabase_user_id")
    plan_id = meta.get("plan_id")

    if not user_id and customer_id:
        user_id = get_user_id_by_stripe_customer(customer_id)

    if not user_id or not plan_id:
        print(
            "[Stripe] invoice.paid skipped: "
            f"subscription_id={subscription_id!r} user_id={user_id!r} plan_id={plan_id!r}"
        )
        return None

    return fulfill_subscription(
        user_id,
        plan_id,
        subscription_id,
        invoice_id=invoice_dict.get("id"),
        sub=sub_dict,
        invoice=invoice_dict,
    )
