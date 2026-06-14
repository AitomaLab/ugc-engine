-- Temporarily disable invite-code gating on signup.
-- Run in Supabase SQL Editor while NEXT_PUBLIC_REQUIRE_INVITE_CODE=false.
-- Before production launch, restore the strict empty-code rejection in 052.

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
  v_email := lower(trim(event -> 'user' ->> 'email'));

  v_code := upper(trim(coalesce(
    event -> 'user' -> 'raw_user_meta_data' ->> 'invite_code',
    event -> 'user' -> 'user_metadata'      ->> 'invite_code',
    event -> 'claims' -> 'user_metadata'     ->> 'invite_code',
    event ->> 'invite_code',
    ''
  )));

  -- Open signup while invite gate is disabled. Codes are still validated when provided.
  if v_code is null or v_code = '' then
    return '{}'::jsonb;
  end if;

  select * into v_row
  from public.invite_codes
  where upper(trim(code)) = v_code
  limit 1;

  if not found then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'This invite code is invalid. Please check your invitation email.'
    ));
  end if;

  if coalesce(v_row.is_used, false) then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'This invite code has already been used.'
    ));
  end if;

  if v_row.email is null or lower(trim(v_row.email)) <> v_email then
    return jsonb_build_object('error', jsonb_build_object(
      'http_code', 403,
      'message', 'This invite code does not match this email address. Please use the email the code was assigned to.'
    ));
  end if;

  update public.invite_codes set is_used = true, used_at = now() where id = v_row.id;
  return '{}'::jsonb;
end;
$$;

grant usage on schema public to supabase_auth_admin;
grant execute on function public.validate_invite_code(jsonb) to supabase_auth_admin;
grant select, update on table public.invite_codes to supabase_auth_admin;
revoke execute on function public.validate_invite_code(jsonb) from authenticated, anon, public;
