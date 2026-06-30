'use client';

import { usePathname } from 'next/navigation';
import { SWRConfig } from 'swr';
import { AppProvider } from '@/providers/AppProvider';
import { TopUpProvider } from '@/providers/TopUpProvider';
import { Header } from '@/components/layout/Header';
import { FeedbackBubble } from '@/components/feedback/FeedbackBubble';
import { studioSwrOptions } from '@/lib/swr';

/**
 * Client-side providers wrapper.
 * Separated from layout.tsx so that the server component can export metadata.
 */
export function ClientProviders({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const isAuthPage = pathname === '/login' || pathname === '/signup' || pathname === '/forgot-password' || pathname === '/reset-password';
  const isEditorPage = pathname?.startsWith('/editor');

  // Editor page: full viewport, no header/wrapper
  if (isEditorPage) {
    return (
      <SWRConfig value={studioSwrOptions}>
        <AppProvider>
          <TopUpProvider>
            {children}
          </TopUpProvider>
        </AppProvider>
      </SWRConfig>
    );
  }

  return (
    <SWRConfig value={studioSwrOptions}>
      <AppProvider>
        <TopUpProvider>
          {!isAuthPage && <Header />}
          <main className="app-body">
            {children}
          </main>
          <FeedbackBubble />
        </TopUpProvider>
      </AppProvider>
    </SWRConfig>
  );
}
