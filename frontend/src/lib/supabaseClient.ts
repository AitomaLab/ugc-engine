/**
 * UGC Engine v3 — Supabase Client
 *
 * Singleton Supabase client for frontend data fetching and storage operations.
 * Uses the anon key (safe for client-side use).
 */
import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || '';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || '';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
