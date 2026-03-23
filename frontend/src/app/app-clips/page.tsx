'use client';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function AppClipsRedirect() {
  const router = useRouter();
  useEffect(() => {
    router.replace('/products?tab=digital');
  }, [router]);
  return null;
}
