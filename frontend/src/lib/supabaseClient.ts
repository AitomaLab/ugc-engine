/**
 * UGC Engine v3 — Supabase Client (Cookie-based)
 *
 * Uses @supabase/ssr's createBrowserClient which stores auth tokens
 * in cookies instead of localStorage. This is required for the
 * Next.js middleware to detect the session on the server side.
 */
import { createBrowserClient } from '@supabase/ssr';

const supabaseUrl =
	process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://placeholder.supabase.co';
const supabaseAnonKey =
	process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'placeholder-anon-key';

export const supabase = createBrowserClient(supabaseUrl, supabaseAnonKey);
