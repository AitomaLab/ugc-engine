'use client';

import { usePathname } from 'next/navigation';
import { AppProvider } from '@/providers/AppProvider';
import { Header } from '@/components/layout/Header';

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
      <AppProvider>
        {children}
      </AppProvider>
    );
  }

  return (
    <AppProvider>
      {!isAuthPage && <Header />}
      <main className="app-body">
        {children}
      </main>
    </AppProvider>
  );
}
