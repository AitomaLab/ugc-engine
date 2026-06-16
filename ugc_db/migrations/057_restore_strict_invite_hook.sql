-- 057_restore_strict_invite_hook.sql
-- Re-close the invite-code gate for the gated-beta launch.
--
-- Ordering context:
--   051_invite_codes.sql        -> creates public.invite_codes
--   052_invite_code_hook.sql    -> STRICT hook (empty/invalid code rejected)
--   053_invite_signup_optional  -> TEMPORARILY opened the gate (empty code allowed)
--   057 (this file)             -> restores the STRICT behavior from 052 so signup
--                                  is invite-only again.
--
-- Run this in the Supabase SQL Editor, then ensure the "Before User Created" hook
-- is ENABLED under Authentication > Hooks pointing at:
--     pg-functions://postgres/public/validate_invite_code
-- and set NEXT_PUBLIC_REQUIRE_INVITE_CODE=true on the frontend.

create or replace function public.validate_invite_code(event jsonb)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  v_email text;
  v_code  text;
  v_row   public.invite_codes%rowtype;
begin
  -- Email of the user being created.
  v_email := lower(trim(event -> 'user' ->> 'email'));

  -- The invite code arrives via supabase.auth.signUp({ options: { data: { invite_code }}}).
  -- Depending on the auth version it lands in raw_user_meta_data / user_metadata /
  -- claims.user_metadata, so read all of them defensively.
  v_code := upper(trim(coalesce(
    event -> 'user' -> 'raw_user_meta_data' ->> 'invite_code',
    event -> 'user' -> 'user_metadata'      ->> 'invite_code',
    event -> 'claims' -> 'user_metadata'     ->> 'invite_code',
    event ->> 'invite_code',
    ''
  )));

  -- No code supplied -> reject (gate CLOSED).
  if v_code is null or v_code = '' then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'An invite code is required to sign up. Please use your invitation link.'
    ));
  end if;

  select * into v_row
  from public.invite_codes
  where upper(trim(code)) = v_code
  limit 1;

  -- Code does not exist.
  if not found then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'This invite code is invalid. Please check your invitation email.'
    ));
  end if;

  -- Code already consumed.
  if coalesce(v_row.is_used, false) then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'This invite code has already been used.'
    ));
  end if;

  -- Email must match the address the code was issued to (case-insensitive).
  if v_row.email is null or lower(trim(v_row.email)) <> v_email then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'This invite code does not match this email address. Please use the email the code was assigned to.'
    ));
  end if;

  -- Valid: consume the code and allow the signup (empty object = allow).
  update public.invite_codes set is_used = true, used_at = now() where id = v_row.id;
  return '{}'::jsonb;
end;
$$;

-- Hook executes as supabase_auth_admin; without these grants every call throws.
grant usage on schema public to supabase_auth_admin;
grant execute on function public.validate_invite_code(jsonb) to supabase_auth_admin;
grant select, update on table public.invite_codes to supabase_auth_admin;

-- Don't expose the hook to client roles.
revoke execute on function public.validate_invite_code(jsonb) from authenticated, anon, public;
