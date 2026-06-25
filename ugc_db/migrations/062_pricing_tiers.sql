-- Subscription and pricing tiers (Model A @ $0.03/credit).
-- Run after creating matching Stripe Prices and updating stripe_price_id columns.

ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS price_yearly NUMERIC(10, 2);
ALTER TABLE subscription_plans ADD COLUMN IF NOT EXISTS stripe_price_id_yearly TEXT;

UPDATE subscription_plans SET
  credits_monthly = 1000,
  price_monthly = 29.00,
  price_yearly = 243.00
WHERE name = 'Starter';

UPDATE subscription_plans SET
  credits_monthly = 3000,
  price_monthly = 89.00,
  price_yearly = 747.00
WHERE name = 'Creator';

UPDATE subscription_plans SET
  credits_monthly = 6000,
  price_monthly = 169.00,
  price_yearly = 1419.00
WHERE name = 'Business';
