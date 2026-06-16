-- 043_invite_code_hook.sql
-- Canonical "Before User Created" auth hook for the gated-beta invite system.
--
-- Run this in the Supabase SQL Editor, then make sure the hook is enabled under
-- Authentication > Hooks > "Before User Created" pointing at:
--     pg-functions://postgres/public/validate_invite_code
--
-- WHY THIS FILE EXISTS
-- A hand-written version of this hook was rejecting *valid* email+code pairs
-- with "Error running hook URI: pg-functions://postgres/public/validate_invite_code".
-- That generic error means the function THREW (it didn't cleanly reject). The two
-- usual causes are:
--   1. The supabase_auth_admin role (which executes the hook) lacked SELECT/UPDATE
--      on public.invite_codes  ->  "permission denied for relation invite_codes".
--   2. The code was read from the wrong JSON path (NULL) and the function used
--      RAISE EXCEPTION to reject, which surfaces as the same generic hook error.
--
-- This version fixes both: it reads invite_code from every metadata location auth
-- may use, normalizes case, returns STRUCTURED errors (so the client shows a clean
-- message instead of a raw Postgres error), and grants the executing role access.

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

  -- No code supplied.
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

  -- Valid: consume the code and allow the signup.
  -- IMPORTANT: the Before User Created hook must return an EMPTY object to allow.
  -- Returning the `event` is treated as an invalid payload and fails the signup
  -- with "Error running hook URI".
  update public.invite_codes set is_used = true, used_at = now() where id = v_row.id;
  return '{}'::jsonb;
end;
$$;

-- The hook executes as supabase_auth_admin; without these grants every call throws
-- "permission denied" and Supabase reports the generic "Error running hook URI".
grant usage on schema public to supabase_auth_admin;
grant execute on function public.validate_invite_code(jsonb) to supabase_auth_admin;
grant select, update on table public.invite_codes to supabase_auth_admin;

-- Don't expose the hook to client roles.
revoke execute on function public.validate_invite_code(jsonb) from authenticated, anon, public;
