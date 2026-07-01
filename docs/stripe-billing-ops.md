# Stripe billing — production operations

## Live webhook setup

1. Stripe Dashboard → **Developers** → **Webhooks** → switch to **Live mode**
2. Add endpoint: `https://<your-railway-api-host>/api/stripe/webhook`
3. Subscribe to events:
   - `checkout.session.completed`
   - `invoice.paid`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
4. Copy the **Signing secret** (`whsec_...`) to Railway → `STRIPE_WEBHOOK_SECRET`
5. Ensure `STRIPE_SECRET_KEY` is the matching **live** secret key (`sk_live_...`)
6. Redeploy Railway, then **Send test webhook** from Stripe → expect HTTP 200 and `[Stripe] Received event` in logs

## Stripe Basil / Acacia API — billing period fields

On Stripe API `2025-02-24.acacia` and newer Basil versions, `current_period_start` / `current_period_end` are **no longer on the Subscription object** — they live on subscription items (`items.data[0].current_period_*`) or on invoice line items (`lines.data[0].period`).

Fulfillment resolves period bounds in this order:

1. Subscription item `current_period_start` / `current_period_end`
2. Legacy subscription-level fields (older API shapes)
3. Invoice line item `period.start` / `period.end`
4. Invoice top-level `period_start` / `period_end`

Metadata (`plan_id`, `supabase_user_id`) is resolved from subscription metadata, then `invoice.parent.subscription_details.metadata`, then line-item metadata.

If webhooks return **500**, check Railway logs for a traceback (fulfillment errors are logged before Stripe retries).

## Replay a missed subscription (existing customer)

If checkout succeeded in Stripe but the app still shows **Free**:

### Option A — Stripe event replay (preferred)

1. Stripe Dashboard → **Developers** → **Webhooks** → your live endpoint → **Event deliveries**
2. Find failed deliveries for `invoice.paid` and `checkout.session.completed`
3. **Resend** each event (expect HTTP **200** and `[Stripe] Fulfilled ... credits` in Railway logs)
4. Alternatively: Stripe → subscription → **Events** tab → resend `invoice.paid` for the first invoice

### Option B — User returns to success URL

Visit `/checkout/success?session_id=cs_live_...` while logged in. The app calls `POST /api/billing/confirm` to fulfill from the session.

### Option C — Manual replay for demo1 (example)

Subscription: `sub_1TnyCdE2TXkp05Uo3rFgb9mu`  
Metadata: `plan_id`, `supabase_user_id` on the Stripe subscription object.

After deploying the fulfillment fix, replay `invoice.paid` or have the user open their checkout success URL with the `cs_live_...` session id.
