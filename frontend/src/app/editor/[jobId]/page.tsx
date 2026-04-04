'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import dynamic from 'next/dynamic';
import { apiFetch } from '@/lib/utils';

const EditorComponent = dynamic(
  () => import('@/editor/editor').then((mod) => ({ default: mod.Editor })),
  {
    ssr: false,
    loading: () => <EditorLoadingScreen message="Loading editor..." />,
  }
);

function EditorLoadingScreen({ message, error }: { message: string; error?: string }) {
  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        width: '100vw',
        backgroundColor: '#28282e',
        color: '#fff',
        fontFamily: 'Inter, system-ui, sans-serif',
        gap: 16,
      }}
    >
      {error ? (
        <>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#EF4444" strokeWidth="2">
            <circle cx="12" cy="12" r="10" />
            <line x1="15" y1="9" x2="9" y2="15" />
            <line x1="9" y1="9" x2="15" y2="15" />
          </svg>
          <p style={{ fontSize: 18, fontWeight: 600 }}>Error loading editor</p>
          <p style={{ fontSize: 14, color: '#8A93B0', maxWidth: 400, textAlign: 'center' }}>
            {error}
          </p>
        </>
      ) : (
        <>
          <div
            style={{
              width: 40,
              height: 40,
              border: '3px solid rgba(255,255,255,0.2)',
              borderTop: '3px solid #0b84f3',
              borderRadius: '50%',
              animation: 'spin 1s linear infinite',
            }}
          />
          <p style={{ fontSize: 16, color: '#8A93B0' }}>{message}</p>
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </>
      )}
    </div>
  );
}

export default function EditorPage() {
  const params = useParams();
  const jobId = params?.jobId as string;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!jobId) {
      setError('No job ID provided');
      setLoading(false);
      return;
    }

    const loadEditorState = async () => {
      try {
        setLoading(true);
        setError(null);

        const editorState = await apiFetch(`/api/editor/state/${jobId}`);
        const encodedState = btoa(JSON.stringify(editorState));
        window.location.hash = `#state=${encodedState}`;

        setReady(true);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load editor');
      } finally {
        setLoading(false);
      }
    };

    loadEditorState();
  }, [jobId]);

  // Auto-save editor state every 30 seconds
  useEffect(() => {
    if (!ready || !jobId) return;

    const saveInterval = setInterval(async () => {
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
        // Silent fail on auto-save
      }
    }, 30000);

    return () => clearInterval(saveInterval);
  }, [ready, jobId]);

  if (loading) {
    return <EditorLoadingScreen message="Loading video editor..." />;
  }

  if (error) {
    return <EditorLoadingScreen message="" error={error} />;
  }

  if (!ready) {
    return <EditorLoadingScreen message="Preparing editor..." />;
  }

  return (
    <div className="editor-page" style={{ width: '100vw', height: '100vh', overflow: 'hidden' }}>
      <EditorComponent initialJobId={jobId} />
    </div>
  );
}
