'use client';

import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { supabase } from '@/lib/supabaseClient';
import type { Session } from '@supabase/supabase-js';
import type { UserProfile, Subscription, CreditWallet, Project } from '@/lib/saas-types';
import { I18nProvider } from '@/lib/i18n';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// ── Context shape ──────────────────────────────────────────────────────
interface AppContextType {
  session: Session | null;
  profile: UserProfile | null;
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
async function authFetch<T>(url: string, token: string | null): Promise<T | null> {
  if (!token) return null;
  try {
    const res = await fetch(`${API_URL}${url}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

// ── Provider ───────────────────────────────────────────────────────────
export function AppProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [activeProject, setActiveProjectState] = useState<Project | null>(null);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [wallet, setWallet] = useState<CreditWallet | null>(null);

  // ── Auth state ─────────────────────────────────────────────────────
  useEffect(() => {
    const getSession = async () => {
      const { data: { session } } = await supabase.auth.getSession();
      setSession(session);
      setLoading(false);
    };
    getSession();

    const { data: authListener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      if (!session) {
        setProfile(null);
        setProjects([]);
        setActiveProjectState(null);
        setSubscription(null);
        setWallet(null);
      }
    });

    return () => authListener.subscription.unsubscribe();
  }, []);

  const token = session?.access_token ?? null;

  // ── Fetch user data when session exists ────────────────────────────
  const fetchUserData = useCallback(async () => {
    if (!token) return;

    const [profileData, projectsData, subData, walletData] = await Promise.all([
      authFetch<UserProfile>('/api/profile', token),
      authFetch<Project[]>('/api/projects', token),
      authFetch<Subscription>('/api/subscription', token),
      authFetch<CreditWallet>('/api/wallet', token),
    ]);

    if (profileData) setProfile(profileData);
    if (projectsData) {
      setProjects(projectsData);
      // Restore active project from localStorage
      const storedId = typeof window !== 'undefined' ? localStorage.getItem('activeProjectId') : null;
      const restored = projectsData.find(p => p.id === storedId)
        || projectsData.find(p => p.is_default)
        || projectsData[0]
        || null;
      setActiveProjectState(restored);
    }
    if (subData) setSubscription(subData);
    if (walletData) setWallet(walletData);
  }, [token]);

  useEffect(() => {
    fetchUserData();
  }, [fetchUserData]);

  // ── Actions ────────────────────────────────────────────────────────
  const setActiveProject = (projectId: string) => {
    const project = projects.find(p => p.id === projectId);
    if (project) {
      setActiveProjectState(project);
      localStorage.setItem('activeProjectId', projectId);
      // Notify all pages to re-fetch their data for the new project
      window.dispatchEvent(new CustomEvent('projectChanged', { detail: projectId }));
    }
  };

  const refreshWallet = useCallback(async () => {
    if (!token) return;
    const walletData = await authFetch<CreditWallet>('/api/wallet', token);
    if (walletData) setWallet(walletData);
  }, [token]);

  const refreshSubscription = useCallback(async () => {
    if (!token) return;
    const subData = await authFetch<Subscription>('/api/subscription', token);
    if (subData) setSubscription(subData);
  }, [token]);

  const refreshProjects = useCallback(async () => {
    if (!token) return;
    const projectsData = await authFetch<Project[]>('/api/projects', token);
    if (projectsData) {
      setProjects(projectsData);
      // Sync activeProject so header name updates after edits
      setActiveProjectState(prev => {
        if (!prev) return prev;
        const updated = projectsData.find(p => p.id === prev.id);
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
