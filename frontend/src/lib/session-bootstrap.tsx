'use client';

/**
 * Host session adapter for embedding the editor in another SaaS shell.
 *
 * Supported integration patterns (see README):
 * 1) Same-origin: parent calls `window.__EDITOR_HANDOFF_SESSION__ = { access_token, refresh_token }`
 *    before the editor bundle executes, then removes it after bootstrap.
 * 2) PostMessage: parent sends `{ type: 'EDITOR_HANDOFF_SET_SESSION', access_token, refresh_token }`.
 * 3) Users already have Supabase cookies from your app on the same domain (createBrowserClient).
 */
import { useEffect, useRef } from 'react';
import { supabase } from '@/lib/supabaseClient';

declare global {
  interface Window {
    __EDITOR_HANDOFF_SESSION__?: {
      access_token: string;
      refresh_token: string;
    };
  }
}

export function SessionBootstrap() {
  const appliedRef = useRef(false);

  useEffect(() => {
    if (appliedRef.current) return;

    const apply = async (access_token: string, refresh_token: string) => {
      const { error } = await supabase.auth.setSession({
        access_token,
        refresh_token,
      });
      if (error) {
        console.warn('[editor-handoff] setSession failed:', error.message);
      }
    };

    const fromGlobal = window.__EDITOR_HANDOFF_SESSION__;
    if (fromGlobal?.access_token && fromGlobal?.refresh_token) {
      appliedRef.current = true;
      void apply(fromGlobal.access_token, fromGlobal.refresh_token);
      delete window.__EDITOR_HANDOFF_SESSION__;
      return;
    }

    const onMessage = (event: MessageEvent) => {
      const data = event.data as {
        type?: string;
        access_token?: string;
        refresh_token?: string;
      };
      if (data?.type !== 'EDITOR_HANDOFF_SET_SESSION') return;
      if (!data.access_token || !data.refresh_token) return;
      appliedRef.current = true;
      void apply(data.access_token, data.refresh_token);
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);

  return null;
}
