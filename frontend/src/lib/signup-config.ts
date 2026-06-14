/** When true, signup requires an invite code (UI + metadata). Keep false until production launch. */
export const REQUIRE_INVITE_CODE =
  process.env.NEXT_PUBLIC_REQUIRE_INVITE_CODE === 'true';
