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
  const isSaving = useRef(false);

  // Fetch the list of editor-eligible jobs
  const refreshJobs = useCallback(async () => {
    try {
      setLoading(true);
      const data = await apiFetch<{ jobs: EditorJob[] }>('/api/editor/jobs');
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

  // Save current editor state before switching
  const saveCurrentState = useCallback(async (jobId: string) => {
    if (isSaving.current) return;
    isSaving.current = true;
    try {
      const hash = window.location.hash;
      if (!hash.startsWith('#state=')) return;
      const encoded = hash.slice('#state='.length);
      const state = JSON.parse(atob(encoded));
      await apiFetch(`/api/editor/state/${jobId}`, {
        method: 'POST',
        body: JSON.stringify(state),
      });
    } catch {
      // Silent fail
    } finally {
      isSaving.current = false;
    }
  }, []);

  // Load a job's editor state into the URL hash
  const loadJobState = useCallback(async (jobId: string) => {
    try {
      const editorState = await apiFetch(`/api/editor/state/${jobId}`);
      const encodedState = btoa(JSON.stringify(editorState));
      window.location.hash = `#state=${encodedState}`;
    } catch (err) {
      console.error('[JobHistory] Failed to load job state:', err);
    }
  }, []);

  // Switch to a different job
  const setActiveJobId = useCallback(async (newJobId: string) => {
    if (newJobId === activeJobId) return;

    // Save current job's state first
    if (activeJobId) {
      await saveCurrentState(activeJobId);
    }

    // Load new job's state
    await loadJobState(newJobId);

    // Update URL without full page reload
    window.history.replaceState({}, '', `/editor/${newJobId}`);

    setActiveJobIdRaw(newJobId);
  }, [activeJobId, saveCurrentState, loadJobState]);

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
