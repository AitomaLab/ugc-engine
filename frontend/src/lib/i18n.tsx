'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';

import en from '@/locales/en.json';
import es from '@/locales/es.json';

// ──────────────────────────────────────────────────────────────
// Supported Languages
// ──────────────────────────────────────────────────────────────
export type SupportedLang = 'en' | 'es';

// ──────────────────────────────────────────────────────────────
// Translation Dictionary (loaded from JSON files)
// ──────────────────────────────────────────────────────────────
const translations: Record<SupportedLang, Record<string, string>> = {
  en: en as Record<string, string>,
  es: es as Record<string, string>,
};

// ──────────────────────────────────────────────────────────────
// Context
// ──────────────────────────────────────────────────────────────
interface I18nContextType {
  lang: SupportedLang;
  setLang: (lang: SupportedLang) => void;
  t: (key: string) => string;
}

const I18nContext = createContext<I18nContextType | undefined>(undefined);

const STORAGE_KEY = 'aitoma_ui_language';

// ──────────────────────────────────────────────────────────────
// Provider
// ──────────────────────────────────────────────────────────────
export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<SupportedLang>('en');

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY) as SupportedLang | null;
      if (stored && (stored === 'en' || stored === 'es')) {
        setLangState(stored);
      }
    } catch {
      // SSR or localStorage unavailable — keep default
    }
  }, []);

  const setLang = useCallback((newLang: SupportedLang) => {
    setLangState(newLang);
    try {
      localStorage.setItem(STORAGE_KEY, newLang);
    } catch {
      // Ignore storage errors
    }
  }, []);

  const t = useCallback(
    (key: string): string => {
      return translations[lang]?.[key] ?? translations['en']?.[key] ?? key;
    },
    [lang]
  );

  return (
    <I18nContext.Provider value={{ lang, setLang, t }}>
      {children}
    </I18nContext.Provider>
  );
}

// ──────────────────────────────────────────────────────────────
// Hook
// ──────────────────────────────────────────────────────────────
export function useTranslation() {
  const context = useContext(I18nContext);
  if (!context) {
    // Fallback for components outside provider (shouldn't happen in practice)
    return {
      lang: 'en' as SupportedLang,
      setLang: () => {},
      t: (key: string) => translations['en']?.[key] ?? key,
    };
  }
  return context;
}
