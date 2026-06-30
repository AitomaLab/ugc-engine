'use client';

import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { TopUpCreditsModal } from '@/components/billing/TopUpCreditsModal';
import { useTranslation } from '@/lib/i18n';
import { useApp } from '@/providers/AppProvider';

export interface TopUpOptions {
  notice?: string;
  required?: number;
  balance?: number;
}

interface TopUpContextType {
  openTopUp: (opts?: TopUpOptions) => void;
  closeTopUp: () => void;
}

const TopUpContext = createContext<TopUpContextType | undefined>(undefined);

export function TopUpProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { wallet } = useApp();
  const [open, setOpen] = useState(false);
  const [notice, setNotice] = useState<string | undefined>();

  const openTopUp = useCallback((opts?: TopUpOptions) => {
    let resolvedNotice = opts?.notice;
    if (!resolvedNotice && opts?.required != null) {
      const balance = opts.balance ?? wallet?.balance ?? 0;
      resolvedNotice = t('manage.topUpInsufficientNotice')
        .replace('{balance}', String(balance))
        .replace('{required}', String(opts.required));
    }
    setNotice(resolvedNotice);
    setOpen(true);
  }, [t, wallet?.balance]);

  const closeTopUp = useCallback(() => {
    setOpen(false);
    setNotice(undefined);
  }, []);

  const value = useMemo(() => ({ openTopUp, closeTopUp }), [openTopUp, closeTopUp]);

  return (
    <TopUpContext.Provider value={value}>
      {children}
      <TopUpCreditsModal open={open} onClose={closeTopUp} notice={notice} />
    </TopUpContext.Provider>
  );
}

export function useTopUp() {
  const ctx = useContext(TopUpContext);
  if (!ctx) throw new Error('useTopUp must be used within TopUpProvider');
  return ctx;
}
