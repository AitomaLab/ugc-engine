-- 066_beta_welcome_credits_toggle.sql
-- Temporarily disable welcome signup credits during paid-plan beta.
-- Re-enable later: set v_welcome_credits := 100 below AND WELCOME_SIGNUP_CREDITS=100 in backend env.
-- Additive / idempotent function replace. Safe to run multiple times.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_wallet_id UUID;
  -- BETA OFF (0). Re-enable welcome credits: set to 100
  v_welcome_credits INT := 0;
BEGIN
  INSERT INTO public.profiles (id, name, email)
  VALUES (NEW.id, split_part(NEW.email, '@', 1), NEW.email);

  INSERT INTO public.credit_wallets (user_id, balance)
  VALUES (NEW.id, v_welcome_credits)
  RETURNING id INTO v_wallet_id;

  INSERT INTO public.projects (user_id, name)
  VALUES (NEW.id, 'My First Project');

  IF v_welcome_credits > 0 THEN
    INSERT INTO public.credit_transactions (wallet_id, amount, type, description)
    VALUES (
      v_wallet_id,
      v_welcome_credits,
      'welcome_bonus',
      v_welcome_credits::text || ' Free Credits on Sign-up'
    );
  END IF;

  RETURN NEW;
END;
$$;
