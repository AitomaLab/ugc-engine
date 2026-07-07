'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useRouter } from 'next/navigation';
import { creativeFetch, CreativeFetchAbortedError } from '@/lib/creative-os-api';
import { fetchCreditCosts } from '@/lib/credit-costs';
import { useApp } from '@/providers/AppProvider';
import { useTranslation, type SupportedLang } from '@/lib/i18n';
import { apiFetch } from '@/lib/utils';
import type { SocialConnection } from '@/lib/types';
import SchedulePostModal, { type BrandScheduleHandoff } from '@/components/modals/SchedulePostModal';
import en from '@/locales/en.json';
import es from '@/locales/es.json';

const API_PREFIX = '/creative-os/brands';

const BRAND_API_PATHS = new Set([
  '/api/health',
  '/api/brand',
  '/api/session',
  '/api/scrape',
  '/api/save',
  '/api/generate',
  '/api/ideas',
  '/api/store-image',
  '/api/stored-renders',
  '/api/pick-logo',
  '/api/credits',
]);

const localeDicts: Record<SupportedLang, Record<string, string>> = {
  en: en as Record<string, string>,
  es: es as Record<string, string>,
};

function buildStudioI18n(lang: SupportedLang): Record<string, string> {
  const dict = localeDicts[lang] || localeDicts.en;
  const out: Record<string, string> = {};
  for (const [key, value] of Object.entries(dict)) {
    if (key.startsWith('brands.studio.')) out[key] = value;
  }
  return out;
}

function applyStudioGlobals(lang: SupportedLang) {
  const w = window as Window & {
    __BRAND_STUDIO_LANG__?: SupportedLang;
    __BRAND_STUDIO_I18N__?: Record<string, string>;
  };
  w.__BRAND_STUDIO_LANG__ = lang;
  w.__BRAND_STUDIO_I18N__ = buildStudioI18n(lang);
}

function timeoutForPath(path: string): number {
  if (path.endsWith('/generate')) return 300_000;
  if (path.endsWith('/store-image')) return 180_000;
  if (path.endsWith('/ideas')) return 180_000;
  if (path.endsWith('/scrape')) return 45_000;
  if (path.endsWith('/stored-renders')) return 30_000;
  if (path.endsWith('/brand') || path.endsWith('/session') || path.endsWith('/health')) return 30_000;
  return 120_000;
}

function toCreativePath(url: string): string | null {
  const qIdx = url.indexOf('?');
  const path = qIdx >= 0 ? url.slice(0, qIdx) : url.split('?')[0];
  const query = qIdx >= 0 ? url.slice(qIdx + 1) : '';
  let mapped: string | null = null;
  if (BRAND_API_PATHS.has(path)) {
    mapped = API_PREFIX + path.replace('/api', '');
  } else if (path.startsWith('/api/brands/')) {
    mapped = path.replace('/api/brands', API_PREFIX);
  }
  if (!mapped) return null;
  return query ? `${mapped}?${query}` : mapped;
}

export interface BrandStudioSchedulePayload {
  caption?: string;
  hashtags?: string[];
  imageUrls?: string[];
  brandName?: string;
  postId?: number;
}

declare global {
  interface Window {
    brandStudioOpenSchedule?: (payload?: BrandStudioSchedulePayload) => void;
    __CREATIVE_OS_URL?: string;
    __BRAND_STUDIO_LANG__?: SupportedLang;
    __BRAND_STUDIO_I18N__?: Record<string, string>;
    __BRAND_STUDIO_CREDIT_COSTS__?: Record<string, number>;
    __brandStudioApplyI18n?: () => void;
    __brandStudioRefreshRows?: () => void;
    __brandStudioRefreshCreditHints?: () => void;
    __brandStudioRefreshWallet?: () => void;
    __brandStudioMarkScheduled?: (postId: number) => void;
  }
}

const PLATFORMS_CACHE_TTL_MS = 60_000;

export function BrandStudioApp() {
  const rootRef = useRef<HTMLDivElement>(null);
  const router = useRouter();
  const initialized = useRef(false);
  const { lang } = useTranslation();
  const { refreshWallet } = useApp();
  const langRef = useRef(lang);
  langRef.current = lang;
  const platformsCacheRef = useRef<{ platforms: string[]; fetchedAt: number } | null>(null);
  const handoffRef = useRef<BrandScheduleHandoff | null>(null);

  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [brandHandoff, setBrandHandoff] = useState<BrandScheduleHandoff | null>(null);
  const [connectedPlatforms, setConnectedPlatforms] = useState<string[]>(['instagram']);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    window.__brandStudioRefreshWallet = () => {
      void refreshWallet();
    };
    return () => {
      delete window.__brandStudioRefreshWallet;
    };
  }, [refreshWallet]);

  const refreshConnectedPlatforms = useCallback(async () => {
    const cached = platformsCacheRef.current;
    if (cached && Date.now() - cached.fetchedAt < PLATFORMS_CACHE_TTL_MS) {
      setConnectedPlatforms(cached.platforms);
      return;
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    try {
      const connData = await apiFetch<{ socials: SocialConnection[] }>(
        '/api/connections?cached=true',
        { signal: controller.signal },
      );
      const platforms = (connData?.socials || [])
        .map((s) => s.platform?.toLowerCase())
        .filter(Boolean) as string[];
      const resolved = platforms.length ? platforms : ['instagram'];
      platformsCacheRef.current = { platforms: resolved, fetchedAt: Date.now() };
      setConnectedPlatforms(resolved);
    } catch {
      if (cached?.platforms.length) {
        setConnectedPlatforms(cached.platforms);
      } else {
        setConnectedPlatforms(['instagram']);
      }
    } finally {
      clearTimeout(timeoutId);
    }
  }, []);

  const openBrandSchedule = useCallback((payload: BrandStudioSchedulePayload) => {
    const imageUrls = (payload.imageUrls || []).filter((u) => /^https?:/i.test(u || ''));
    if (!imageUrls.length) return;

    if (platformsCacheRef.current?.platforms.length) {
      setConnectedPlatforms(platformsCacheRef.current.platforms);
    }

    const handoff: BrandScheduleHandoff = {
      caption: payload.caption || '',
      hashtags: payload.hashtags || [],
      imageUrls,
      brandName: payload.brandName,
      postId: payload.postId,
    };
    handoffRef.current = handoff;
    setBrandHandoff(handoff);
    setScheduleOpen(true);
    void refreshConnectedPlatforms();
  }, [refreshConnectedPlatforms]);

  useEffect(() => {
    applyStudioGlobals(lang);
    window.__brandStudioApplyI18n?.();
    window.__brandStudioRefreshRows?.();
  }, [lang]);

  useEffect(() => {
    if (initialized.current || !rootRef.current) return;
    initialized.current = true;

    const container = rootRef.current;
    const origFetch = window.fetch.bind(window);

    window.brandStudioOpenSchedule = (payload) => {
      if (payload?.imageUrls?.length) {
        openBrandSchedule(payload);
        return;
      }
      router.push('/schedule');
    };

    (async () => {
      applyStudioGlobals(langRef.current);

      const res = await fetch('/brands/studio.html');
      const html = await res.text();
      const parser = new DOMParser();
      const doc = parser.parseFromString(html, 'text/html');

      container.innerHTML = '';

      doc.querySelectorAll('style').forEach((node) => {
        const el = document.createElement('style');
        el.textContent = node.textContent;
        container.appendChild(el);
      });

      const mount = document.createElement('div');
      mount.style.flex = '1';
      mount.style.height = '100%';
      mount.style.display = 'flex';
      mount.style.flexDirection = 'column';
      mount.style.minHeight = '0';
      mount.style.overflow = 'hidden';
      mount.innerHTML = doc.body.innerHTML;
      container.appendChild(mount);

      const creativeOsUrl = process.env.NEXT_PUBLIC_CREATIVE_OS_URL || 'http://localhost:8001';
      window.__CREATIVE_OS_URL = creativeOsUrl;

      try {
        window.__BRAND_STUDIO_CREDIT_COSTS__ = await fetchCreditCosts();
      } catch {
        window.__BRAND_STUDIO_CREDIT_COSTS__ = {
          brand_studio_ideas_per_idea: 2,
          brand_studio_ideas_batch_min: 6,
          brand_studio_slide_render: 25,
        };
      }
      window.__brandStudioRefreshCreditHints?.();

      window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
        const creativePath = toCreativePath(url);
        if (creativePath) {
          try {
            const timeoutMs = timeoutForPath(creativePath);
            const maxAttempts = creativePath.endsWith('/scrape') ? 1 : 3;
            const data = await creativeFetch(creativePath, init, timeoutMs, maxAttempts);
            return new Response(JSON.stringify(data), {
              status: 200,
              headers: { 'Content-Type': 'application/json' },
            });
          } catch (err) {
            let message = err instanceof Error ? err.message : String(err);
            let status = 502;
            if (err instanceof CreativeFetchAbortedError && err.kind === 'timeout') {
              if (creativePath.endsWith('/scrape')) {
                message = 'Request timed out';
              } else if (creativePath.endsWith('/generate')) {
                message = 'Image generation timed out — try rendering fewer carousels at once';
              }
            } else if (
              /402/.test(message)
              || /insufficient credits/i.test(message)
            ) {
              status = 402;
            } else if (message.includes('404')) {
              status = 404;
            }
            const body: Record<string, unknown> = { error: message, detail: message };
            const balM = message.match(/balance[:\s]+(\d+)/i);
            const reqM = message.match(/required[:\s]+(\d+)/i);
            if (balM) body.balance = Number(balM[1]);
            if (reqM) body.required = Number(reqM[1]);
            if (status === 402) body.error = 'insufficient_credits';
            return new Response(JSON.stringify(body), {
              status,
              headers: { 'Content-Type': 'application/json' },
            });
          }
        }
        return origFetch(input, init);
      };

      mount.querySelectorAll('script').forEach((oldScript) => {
        const script = document.createElement('script');
        script.textContent = oldScript.textContent;
        oldScript.replaceWith(script);
      });
    })();

    return () => {
      window.fetch = origFetch;
      delete window.brandStudioOpenSchedule;
      delete window.__BRAND_STUDIO_LANG__;
      delete window.__BRAND_STUDIO_I18N__;
      delete window.__BRAND_STUDIO_CREDIT_COSTS__;
      delete window.__brandStudioApplyI18n;
      delete window.__brandStudioRefreshRows;
      delete window.__brandStudioRefreshWallet;
      delete window.__brandStudioMarkScheduled;
    };
  }, [router, openBrandSchedule]);

  return (
    <>
      <div ref={rootRef} className="brand-studio-page" />
      {mounted && createPortal(
        <SchedulePostModal
          isOpen={scheduleOpen}
          onClose={() => {
            setScheduleOpen(false);
            setBrandHandoff(null);
            handoffRef.current = null;
          }}
          brandHandoff={scheduleOpen ? (brandHandoff ?? undefined) : undefined}
          initialConnectedPlatforms={connectedPlatforms}
          onScheduled={() => {
            const postId = handoffRef.current?.postId;
            if (postId != null) {
              window.__brandStudioMarkScheduled?.(postId);
            }
          }}
        />,
        document.body,
      )}
    </>
  );
}
