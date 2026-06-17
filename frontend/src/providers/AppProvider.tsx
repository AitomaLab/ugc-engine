'use client';

import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { supabase } from '@/lib/supabaseClient';
import type { Session } from '@supabase/supabase-js';
import type { UserProfile, Subscription, CreditWallet, Project } from '@/lib/saas-types';
import { I18nProvider } from '@/lib/i18n';
import {
  fetchWithAuth,
  refreshSessionOnce,
  forceReauth,
} from '@/lib/auth';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export type ProfileStatus = 'idle' | 'loading' | 'ready' | 'error';

// ── Context shape ──────────────────────────────────────────────────────
interface AppContextType {
  session: Session | null;
  profile: UserProfile | null;
  profileStatus: ProfileStatus;
  projects: Project[];
  activeProject: Project | null;
  setActiveProject: (projectId: string) => void;
  subscription: Subscription | null;
  wallet: CreditWallet | null;
  isLoading: boolean;
  refreshWallet: () => void;
  refreshSubscription: () => void;
  refreshProjects: () => void;
  getAuthHeaders: () => Record<string, string>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

// ── Fetcher with auth ──────────────────────────────────────────────────
async function authFetch<T>(url: string): Promise<{ data: T | null; unauthorized: boolean }> {
  const result = await fetchWithAuth<T>(`${API_URL}${url}`, { skipReauth: true });
  if (result.ok) return { data: result.data, unauthorized: false };
  if (result.unauthorized) {
    console.warn(`[AppProvider] ${url} returned 401`);
    return { data: null, unauthorized: true };
  }
  console.warn(`[AppProvider] ${url} returned ${result.status}`);
  return { data: null, unauthorized: false };
}

async function authFetchWithRetry<T>(url: string): Promise<{ data: T | null; unauthorized: boolean }> {
  let result = await authFetch<T>(url);
  if (!result.unauthorized) return result;

  await refreshSessionOnce();
  result = await authFetch<T>(url);
  return result;
}

async function handleAuthFailure(): Promise<void> {
  const recovered = await refreshSessionOnce();
  if (recovered?.access_token) return;
  await forceReauth();
}

// ── Provider ───────────────────────────────────────────────────────────
export function AppProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [profileStatus, setProfileStatus] = useState<ProfileStatus>('idle');
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProjectState] = useState<Project | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [wallet, setWallet] = useState<CreditWallet | null>(null);
  const fetchUserDataRef = useRef<(() => Promise<void>) | null>(null);
  const lastTokenRef = useRef<string | null>(null);
  const sessionRef = useRef<Session | null>(null);

  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  // ── Auth state ─────────────────────────────────────────────────────
  useEffect(() => {
    const getSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      setSession(session);
      setLoading(false);
    };
    getSession();

    const { data: authListener } = supabase.auth.onAuthStateChange((event, session) => {
      setSession(session);
      if (event === 'TOKEN_REFRESHED' && session) {
        lastTokenRef.current = session.access_token;
        fetchUserDataRef.current?.();
      }
      if (event === 'SIGNED_OUT') {
        setProfile(null);
        setProfileStatus('idle');
        setProjects([]);
        setActiveProjectState(null);
        setSubscription(null);
        setWallet(null);
        if (typeof window !== 'undefined') {
          localStorage.removeItem('activeProjectId');
        }
      }
    });

    return () => authListener.subscription.unsubscribe();
  }, []);

  // Proactive refresh when tab regains focus after idle
  useEffect(() => {
    const onResume = async () => {
      if (document.visibilityState !== 'visible' || !sessionRef.current) return;

      const refreshed = await refreshSessionOnce();
      if (refreshed) {
        setSession(refreshed);
        lastTokenRef.current = refreshed.access_token;
      }

      const { data: { session: current } } = await supabase.auth.getSession();
      if (current) {
        setSession(current);
        lastTokenRef.current = current.access_token;
      }

      fetchUserDataRef.current?.();
    };

    document.addEventListener('visibilitychange', onResume);
    window.addEventListener('focus', onResume);
    return () => {
      document.removeEventListener('visibilitychange', onResume);
      window.removeEventListener('focus', onResume);
    };
  }, []);

  const token = session?.access_token ?? null;

  // ── Fetch user data when session exists ────────────────────────────
  const fetchUserData = useCallback(async () => {
    if (!token) {
      setProfileStatus('idle');
      return;
    }

    setProfileStatus('loading');
    lastTokenRef.current = token;

    const [profileResult, projectsResult, subResult, walletResult] = await Promise.all([
      authFetchWithRetry<UserProfile>('/api/profile'),
      authFetchWithRetry<Project[]>('/api/projects'),
      authFetchWithRetry<Subscription>('/api/subscription'),
      authFetchWithRetry<CreditWallet>('/api/wallet'),
    ]);

    if (
      profileResult.unauthorized
      || projectsResult.unauthorized
      || subResult.unauthorized
      || walletResult.unauthorized
    ) {
      setProfileStatus('error');
      await handleAuthFailure();
      return;
    }

    let resolvedProfile = profileResult.data;
    let resolvedWallet = walletResult.data;
    let resolvedProjects = projectsResult.data;
    const subData = subResult.data;

    if (!resolvedProfile && token && !profileResult.unauthorized) {
      for (let attempt = 1; attempt <= 3; attempt++) {
        await new Promise(r => setTimeout(r, 1000));
        const [retryProfile, retryWallet, retryProjects] = await Promise.all([
          authFetchWithRetry<UserProfile>('/api/profile'),
          authFetchWithRetry<CreditWallet>('/api/wallet'),
          authFetchWithRetry<Project[]>('/api/projects'),
        ]);
        if (retryProfile.unauthorized) {
          setProfileStatus('error');
          await handleAuthFailure();
          return;
        }
        if (retryProfile.data) {
          resolvedProfile = retryProfile.data;
          resolvedWallet = retryWallet.data || resolvedWallet;
          resolvedProjects = retryProjects.data || resolvedProjects;
          break;
        }
        if (retryProjects.data && retryProjects.data.length > 0) {
          resolvedProjects = retryProjects.data;
        }
      }
    }

    if (resolvedProfile && (!resolvedProjects || resolvedProjects.length === 0) && token) {
      for (let attempt = 1; attempt <= 3; attempt++) {
        await new Promise(r => setTimeout(r, 1000));
        const retryProjects = await authFetchWithRetry<Project[]>('/api/projects');
        if (retryProjects.unauthorized) break;
        if (retryProjects.data && retryProjects.data.length > 0) {
          resolvedProjects = retryProjects.data;
          break;
        }
      }
    }

    if (resolvedProfile) {
      setProfile(resolvedProfile);
      setProfileStatus('ready');
    } else if (!profileResult.unauthorized) {
      setProfileStatus('ready');
    }

    if (resolvedProjects && resolvedProjects.length > 0) {
      setProjects(resolvedProjects);
      const storedId = typeof window !== 'undefined' ? localStorage.getItem('activeProjectId') : null;
      const restored = resolvedProjects.find(p => p.id === storedId)
        || resolvedProjects.find(p => p.is_default)
        || resolvedProjects[0]
        || null;
      setActiveProjectState(restored);
      if (restored && typeof window !== 'undefined') {
        localStorage.setItem('activeProjectId', restored.id);
      }
    } else if (resolvedProjects) {
      setProjects([]);
      setActiveProjectState(null);
    }
    if (subData) setSubscription(subData);
    if (resolvedWallet) setWallet(resolvedWallet);
  }, [token]);

  fetchUserDataRef.current = fetchUserData;

  useEffect(() => {
    fetchUserData();
  }, [fetchUserData]);

  // ── Actions ────────────────────────────────────────────────────────
  const setActiveProject = (projectId: string) => {
    const project = projects.find(p => p.id === projectId);
    if (project) {
      setActiveProjectState(project);
      localStorage.setItem('activeProjectId', projectId);
      window.dispatchEvent(new CustomEvent('projectChanged', { detail: projectId }));
    }
  };

  const refreshWallet = useCallback(async () => {
    if (!token) return;
    const result = await authFetchWithRetry<CreditWallet>('/api/wallet');
    if (result.unauthorized) {
      await handleAuthFailure();
      return;
    }
    if (result.data) setWallet(result.data);
  }, [token]);

  const refreshSubscription = useCallback(async () => {
    if (!token) return;
    const result = await authFetchWithRetry<Subscription>('/api/subscription');
    if (result.unauthorized) {
      await handleAuthFailure();
      return;
    }
    if (result.data) setSubscription(result.data);
  }, [token]);

  const refreshProjects = useCallback(async () => {
    if (!token) return;
    const result = await authFetchWithRetry<Project[]>('/api/projects');
    if (result.unauthorized) {
      await handleAuthFailure();
      return;
    }
    if (result.data) {
      setProjects(result.data);
      setActiveProjectState(prev => {
        if (!prev) return prev;
        const updated = result.data!.find(p => p.id === prev.id);
        return updated || prev;
      });
    }
  }, [token]);

  const getAuthHeaders = useCallback((): Record<string, string> => {
    if (!token) return {};
    return { Authorization: `Bearer ${token}` };
  }, [token]);

  // ── Value ──────────────────────────────────────────────────────────
  const value: AppContextType = {
    session,
    profile,
    profileStatus,
    projects,
    activeProject,
    setActiveProject,
    subscription,
    wallet,
    isLoading: loading,
    refreshWallet,
    refreshSubscription,
    refreshProjects,
    getAuthHeaders,
  };

  return (
    <AppContext.Provider value={value}>
      <I18nProvider>{children}</I18nProvider>
    </AppContext.Provider>
  );
}

export function useApp() {
  const context = useContext(AppContext);
  if (context === undefined) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
}
