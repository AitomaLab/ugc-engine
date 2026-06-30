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


def _subscription_interval(sub: dict[str, Any]) -> str:
    items = sub.get("items", {}).get("data", [])
    if items:
        return items[0].get("price", {}).get("recurring", {}).get("interval", "month")
    return "month"


def _period_bounds(sub: dict[str, Any]) -> tuple[str, str]:
    period_start = datetime.fromtimestamp(
        sub["current_period_start"], tz=timezone.utc
    ).isoformat()
    period_end = datetime.fromtimestamp(
        sub["current_period_end"], tz=timezone.utc
    ).isoformat()
    return period_start, period_end


def fulfill_subscription(
    user_id: str,
    plan_id: str,
    subscription_id: str,
    *,
    invoice_id: str | None = None,
    session_id: str | None = None,
    sub: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Upsert DB subscription and grant plan credits. Idempotent per invoice or session."""
    plan = get_plan_by_id(plan_id)
    if not plan:
        print(f"[Stripe] fulfill_subscription skipped: unknown plan_id={plan_id!r}")
        return None

    if sub is None:
        sub = stripe.Subscription.retrieve(subscription_id)

    period_start, period_end = _period_bounds(sub)

    upsert_subscription(
        user_id=user_id,
        plan_id=plan_id,
        stripe_subscription_id=subscription_id,
        status="active",
        period_start=period_start,
        period_end=period_end,
    )

    interval = _subscription_interval(sub)
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


def fulfill_from_checkout_session(session: dict[str, Any]) -> dict[str, Any] | None:
    """Fulfill a paid subscription checkout session."""
    metadata = session.get("metadata") or {}
    user_id = metadata.get("supabase_user_id")
    plan_id = metadata.get("plan_id")
    subscription_id = session.get("subscription")
    if subscription_id and not isinstance(subscription_id, str):
        subscription_id = getattr(subscription_id, "id", None) or subscription_id.get("id")

    if not user_id or not plan_id or not subscription_id:
        print(
            "[Stripe] checkout.session.completed subscription skipped: "
            f"user_id={user_id!r} plan_id={plan_id!r} subscription_id={subscription_id!r}"
        )
        return None

    if session.get("payment_status") not in ("paid", "no_payment_required"):
        print(
            "[Stripe] checkout.session.completed subscription skipped: "
            f"payment_status={session.get('payment_status')!r}"
        )
        return None

    return fulfill_subscription(
        user_id,
        plan_id,
        subscription_id,
        session_id=session.get("id"),
    )


def fulfill_from_invoice_paid(invoice: dict[str, Any]) -> dict[str, Any] | None:
    """Fulfill subscription renewal or first invoice."""
    subscription_id = resolve_invoice_subscription_id(invoice)
    customer_id = invoice.get("customer")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")

    if not subscription_id:
        print(
            "[Stripe] invoice.paid skipped: no subscription on invoice "
            f"(invoice={invoice.get('id')!r})"
        )
        return None

    sub = stripe.Subscription.retrieve(subscription_id)
    user_id = sub.metadata.get("supabase_user_id")
    plan_id = sub.metadata.get("plan_id")

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
        invoice_id=invoice.get("id"),
        sub=sub,
    )
