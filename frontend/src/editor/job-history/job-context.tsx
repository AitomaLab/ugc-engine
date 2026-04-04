'use client';

import React, { createContext, useContext, useState, useCallback, useEffect, useRef } from 'react';
import { apiFetch } from '@/lib/utils';

export type EditorJob = {
  id: string;
  name: string;
  final_video_url: string;
  status: string;
  created_at: string;
  updated_at: string;
  has_editor_state: boolean;
  source: string;
};

type JobContextValue = {
  activeJobId: string | null;
  setActiveJobId: (id: string) => void;
  jobs: EditorJob[];
  loading: boolean;
  refreshJobs: () => void;
  sidebarOpen: boolean;
  toggleSidebar: () => void;
};

const JobContext = createContext<JobContextValue | null>(null);

export function useJobHistory() {
  const ctx = useContext(JobContext);
  if (!ctx) throw new Error('useJobHistory must be used within JobHistoryProvider');
  return ctx;
}

export function JobHistoryProvider({
  initialJobId,
  children,
}: {
  initialJobId?: string | null;
  children: React.ReactNode;
}) {
  const [activeJobId, setActiveJobIdRaw] = useState<string | null>(initialJobId ?? null);
  const [jobs, setJobs] = useState<EditorJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Fetch the list of editor-eligible jobs
  const refreshJobs = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiFetch<{ jobs: EditorJob[] }>('/api/editor/jobs');
      console.log('[JobHistory] Fetched jobs:', data?.jobs?.length ?? 0);
      setJobs(data.jobs || []);
    } catch (err) {
      console.error('[JobHistory] Failed to fetch jobs:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refreshJobs();
  }, [refreshJobs]);

  // Switch to a different job — full page navigation so the editor
  // re-initializes with the new job's state from the API.
  const setActiveJobId = useCallback((newJobId: string) => {
    if (newJobId === activeJobId) return;

    // Navigate to the new job URL — this triggers a full page load
    // which runs the editor page's useEffect to fetch + inject state.
    window.location.href = `/editor/${newJobId}`;
  }, [activeJobId]);

  const toggleSidebar = useCallback(() => {
    setSidebarOpen(prev => !prev);
  }, []);

  return (
    <JobContext.Provider
      value={{
        activeJobId,
        setActiveJobId,
        jobs,
        loading,
        refreshJobs,
        sidebarOpen,
        toggleSidebar,
      }}
    >
      {children}
    </JobContext.Provider>
  );
}
