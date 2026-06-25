-- Align subscription monthly credit allotments with 70% margin pricing (Model A @ $0.03/credit).
-- Starter unchanged at 1,000 credits; Creator and Business increased for cinematic/Seedance headroom.

UPDATE subscription_plans SET credits_monthly = 1000 WHERE name = 'Starter';
UPDATE subscription_plans SET credits_monthly = 3200 WHERE name = 'Creator';
UPDATE subscription_plans SET credits_monthly = 7000 WHERE name = 'Business';
