-- ==========================================================================
-- Stripe Integration Migration
-- Adds Stripe-specific columns to existing tables for payment processing.
--
-- Safe to run multiple times (all operations use IF NOT EXISTS / IF EXISTS).
-- Existing rows are preserved -- all new columns are nullable.
-- ==========================================================================

-- 1. Add stripe_customer_id to profiles
--    Only populated when user upgrades from Free (lazy creation).
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS stripe_customer_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_profiles_stripe_cust
    ON profiles(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;

-- 2. Add stripe_subscription_id to subscriptions
--    Links local subscription row to Stripe Subscription object.
ALTER TABLE subscriptions ADD COLUMN IF NOT EXISTS stripe_subscription_id TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_subs_stripe_id
    ON subscriptions(stripe_subscription_id) WHERE stripe_subscription_id IS NOT NULL;

-- 3. Add stripe_price_id to subscription_plans
--    Maps each plan to the Stripe Price object for Checkout sessions.
ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS stripe_price_id TEXT;

-- 4. Idempotency key on credit_transactions
--    Prevents double-credit from webhook retries.
ALTER TABLE credit_transactions ADD COLUMN IF NOT EXISTS stripe_idempotency_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS idx_credit_tx_idempotency
    ON credit_transactions(stripe_idempotency_key) WHERE stripe_idempotency_key IS NOT NULL;

-- 5. Populate stripe_price_id values for plans that use Stripe Checkout
--    (Agency plan uses "Contact Sales" — no Stripe price needed)
UPDATE subscription_plans SET stripe_price_id = 'price_1TGdN9E2TXkp05Uo2eJHqKdg' WHERE name = 'Starter';
UPDATE subscription_plans SET stripe_price_id = 'price_1TGdTaE2TXkp05UoAC8IVgn7' WHERE name = 'Creator';
UPDATE subscription_plans SET stripe_price_id = 'price_1TGdUAE2TXkp05UoajlfCd6f' WHERE name = 'Business';
