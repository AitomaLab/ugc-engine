-- One-time credit top-up packages (same pattern as subscription_plans.stripe_price_id).
-- After creating Stripe one-time Prices in Live mode, run the UPDATEs at the bottom.

CREATE TABLE IF NOT EXISTS credit_topup_packages (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  credits INTEGER NOT NULL,
  price_usd NUMERIC(10, 2) NOT NULL,
  stripe_price_id TEXT,
  is_active BOOLEAN DEFAULT true,
  sort_order INTEGER DEFAULT 0
);

INSERT INTO credit_topup_packages (id, name, credits, price_usd, sort_order) VALUES
  ('small',  'Small Top-Up',  250,  9.00,  1),
  ('medium', 'Medium Top-Up', 700,  24.00, 2),
  ('large',  'Large Top-Up',  2000, 59.00, 3),
  ('xl',     'XL Top-Up',     5000, 139.00, 4)
ON CONFLICT (id) DO NOTHING;

-- Live Stripe Price IDs — replace price_... after creating one-time prices in Dashboard:
-- UPDATE credit_topup_packages SET stripe_price_id = 'price_...' WHERE id = 'small';
-- UPDATE credit_topup_packages SET stripe_price_id = 'price_...' WHERE id = 'medium';
-- UPDATE credit_topup_packages SET stripe_price_id = 'price_...' WHERE id = 'large';
-- UPDATE credit_topup_packages SET stripe_price_id = 'price_...' WHERE id = 'xl';
