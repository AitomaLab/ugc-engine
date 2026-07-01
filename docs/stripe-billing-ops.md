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

## Credit top-up packages

Top-up price IDs live in Supabase (`credit_topup_packages.stripe_price_id`) — same pattern as `subscription_plans`, not Railway env vars.

### Initial setup

1. Run migration [`ugc_db/migrations/065_credit_topup_packages.sql`](ugc_db/migrations/065_credit_topup_packages.sql) in Supabase SQL editor (creates table + seeds four packages).

2. Stripe Dashboard (Live mode) → **Products** → create four **one-time** prices:

| Package slug (`id`) | Credits | Price |
|---------------------|---------|-------|
| `small` | 250 | $9 |
| `medium` | 700 | $24 |
| `large` | 2,000 | $59 |
| `xl` | 5,000 | $139 |

3. Copy each live `price_...` ID and run in Supabase:

```sql
UPDATE credit_topup_packages SET stripe_price_id = 'price_...' WHERE id = 'small';
UPDATE credit_topup_packages SET stripe_price_id = 'price_...' WHERE id = 'medium';
UPDATE credit_topup_packages SET stripe_price_id = 'price_...' WHERE id = 'large';
UPDATE credit_topup_packages SET stripe_price_id = 'price_...' WHERE id = 'xl';
```

4. Redeploy Railway only if you changed backend code — no new env vars needed.

### Verify top-up checkout

1. `/manage` → **Top Up Credits** → **Buy Now** on any pack → Stripe Checkout opens (not "Invalid top-up package").
2. After payment, webhook `checkout.session.completed` (`mode=payment`) adds credits.
3. Railway log: `[Stripe] Added N credits to user ... (top-up: small)`.

If checkout returns **"Top-up package not configured"**, the package row exists but `stripe_price_id` is still NULL — run the UPDATEs above.

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
