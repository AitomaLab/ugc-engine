-- Populate yearly Stripe Price IDs (30% discount baked into each Price).
-- Starter $243/yr, Creator $747/yr, Business $1419/yr (see 062_pricing_tiers.sql)

UPDATE subscription_plans SET stripe_price_id_yearly = 'price_1Tn7AtE2TXkp05UoM8cFbifk' WHERE name = 'Starter';
UPDATE subscription_plans SET stripe_price_id_yearly = 'price_1Tn7CQE2TXkp05UoruLM2o1A' WHERE name = 'Creator';
UPDATE subscription_plans SET stripe_price_id_yearly = 'price_1Tn7CxE2TXkp05UoF3holwO8' WHERE name = 'Business';
