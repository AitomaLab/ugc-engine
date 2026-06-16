'use client';

import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { supabase } from '@/lib/supabaseClient';
import type { Session } from '@supabase/supabase-js';
import type { UserProfile, Subscription, CreditWallet, Project } from '@/lib/saas-types';
import { I18nProvider } from '@/lib/i18n';
import { fetchWithAuth, getValidAccessToken } from '@/lib/auth';

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
        fetchUserDataRef.current?.();
      }
      // Only wipe scoped state on explicit sign-out — not on transient null
      // sessions during token refresh or INITIAL_SESSION races.
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

  // Refocus: validate token and refetch if it changed while tab was backgrounded
  useEffect(() => {
    const onVisibilityChange = async () => {
      if (document.visibilityState !== 'visible' || !session) return;
      const token = await getValidAccessToken();
      if (!token) return;
      if (token !== lastTokenRef.current) {
        lastTokenRef.current = token;
        fetchUserDataRef.current?.();
      }
    };
    document.addEventListener('visibilitychange', onVisibilityChange);
    return () => document.removeEventListener('visibilitychange', onVisibilityChange);
  }, [session]);

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
      authFetch<UserProfile>('/api/profile'),
      authFetch<Project[]>('/api/projects'),
      authFetch<Subscription>('/api/subscription'),
      authFetch<CreditWallet>('/api/wallet'),
    ]);

    // Hard auth failure after refresh — force re-login instead of ghost "User" state
    if (
      profileResult.unauthorized
      || projectsResult.unauthorized
      || subResult.unauthorized
      || walletResult.unauthorized
    ) {
      setProfileStatus('error');
      const { forceReauth } = await import('@/lib/auth');
      await forceReauth();
      return;
    }

    let resolvedProfile = profileResult.data;
    let resolvedWallet = walletResult.data;
    let resolvedProjects = projectsResult.data;
    const subData = subResult.data;

    // Race condition guard: on signup the Supabase auth session is ready
    // before the handle_new_user DB trigger finishes creating the profile,
    // wallet, and default project rows. Retry a few times with a delay to let
    // the trigger complete rather than rendering a ghost "User" state.
    if (!resolvedProfile && token && !profileResult.unauthorized) {
      for (let attempt = 1; attempt <= 3; attempt++) {
        await new Promise(r => setTimeout(r, 1000));
        const [retryProfile, retryWallet, retryProjects] = await Promise.all([
          authFetch<UserProfile>('/api/profile'),
          authFetch<CreditWallet>('/api/wallet'),
          authFetch<Project[]>('/api/projects'),
        ]);
        if (retryProfile.unauthorized) {
          setProfileStatus('error');
          const { forceReauth } = await import('@/lib/auth');
          await forceReauth();
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

    // Profile may exist while the default project is still being created.
    if (resolvedProfile && (!resolvedProjects || resolvedProjects.length === 0) && token) {
      for (let attempt = 1; attempt <= 3; attempt++) {
        await new Promise(r => setTimeout(r, 1000));
        const retryProjects = await authFetch<Project[]>('/api/projects');
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
    const result = await authFetch<CreditWallet>('/api/wallet');
    if (result.unauthorized) {
      const { forceReauth } = await import('@/lib/auth');
      await forceReauth();
      return;
    }
    if (result.data) setWallet(result.data);
  }, [token]);

  const refreshSubscription = useCallback(async () => {
    if (!token) return;
    const result = await authFetch<Subscription>('/api/subscription');
    if (result.unauthorized) {
      const { forceReauth } = await import('@/lib/auth');
      await forceReauth();
      return;
    }
    if (result.data) setSubscription(result.data);
  }, [token]);

  const refreshProjects = useCallback(async () => {
    if (!token) return;
    const result = await authFetch<Project[]>('/api/projects');
    if (result.unauthorized) {
      const { forceReauth } = await import('@/lib/auth');
      await forceReauth();
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
