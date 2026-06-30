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

## Replay a missed subscription (existing customer)

If checkout succeeded in Stripe but the app still shows **Free**:

### Option A — Stripe event replay (preferred)

1. Stripe → subscription → **Events** tab
2. Find `invoice.paid` for the first invoice
3. **Resend** / **Replay** to your live webhook endpoint

### Option B — User returns to success URL

Visit `/checkout/success?session_id=cs_live_...` while logged in. The app calls `POST /api/billing/confirm` to fulfill from the session.

### Option C — Manual replay for demo1 (example)

Subscription: `sub_1TnyCdE2TXkp05Uo3rFgb9mu`  
Metadata: `plan_id`, `supabase_user_id` on the Stripe subscription object.

After deploying the fulfillment fix, replay `invoice.paid` or have the user open their checkout success URL with the `cs_live_...` session id.
