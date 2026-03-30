-- Fix for the handle_new_user trigger
-- The previous trigger automatically forced users into the 'Starter' plan with 1000 credits.
-- This updated trigger fixes it so users are placed on the 'Free' plan (by not inserting a subscription)
-- and gives them exactly 100 welcome credits.

CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_wallet_id UUID;
BEGIN
  -- Create user profile (using 'name' and 'email' as per the live schema)
  INSERT INTO public.profiles (id, name, email)
  VALUES (NEW.id, split_part(NEW.email, '@', 1), NEW.email);

  -- Create wallet with exactly 100 credits (No subscription attached)
  INSERT INTO public.credit_wallets (user_id, balance)
  VALUES (NEW.id, 100)
  RETURNING id INTO v_wallet_id;

  -- Create default project
  INSERT INTO public.projects (user_id, name)
  VALUES (NEW.id, 'My First Project');

  -- Log the 100 free credits as a welcome bonus transaction
  INSERT INTO public.credit_transactions (wallet_id, amount, type, description)
  VALUES (v_wallet_id, 100, 'welcome_bonus', '100 Free Credits on Sign-up');

  RETURN NEW;
END;
$$;
