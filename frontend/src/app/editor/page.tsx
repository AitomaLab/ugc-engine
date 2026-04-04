'use client';

import dynamic from 'next/dynamic';

const EditorComponent = dynamic(
  () => import('@/editor/editor').then((mod) => ({ default: mod.Editor })),
  {
    ssr: false,
    loading: () => (
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
        <p style={{ fontSize: 16, color: '#8A93B0' }}>Loading editor...</p>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    ),
  }
);

/**
 * General editor page — opens with an empty canvas and the sidebar.
 * Use the sidebar to select a video from your history.
 */
export default function EditorGeneralPage() {
  return (
    <div className="editor-page" style={{ width: '100vw', height: '100vh', overflow: 'hidden' }}>
      <EditorComponent initialJobId={null} />
    </div>
  );
}
