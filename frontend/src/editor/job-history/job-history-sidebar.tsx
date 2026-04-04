import React, { useMemo } from 'react';
import { useJobHistory, EditorJob } from './job-context';
import { scrollbarStyle } from '../constants';

const SIDEBAR_WIDTH = 280;

function timeAgo(dateStr: string): string {
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return 'Just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHrs = Math.floor(diffMin / 60);
  if (diffHrs < 24) return `${diffHrs}h ago`;
  const diffDays = Math.floor(diffHrs / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}

const JobCard: React.FC<{
  job: EditorJob;
  isActive: boolean;
  onClick: () => void;
}> = ({ job, isActive, onClick }) => {
  return (
    <button
      onClick={onClick}
      style={{
        display: 'block',
        width: '100%',
        textAlign: 'left',
        padding: 10,
        borderRadius: 8,
        border: isActive ? '1px solid rgba(59,130,246,0.5)' : '1px solid transparent',
        background: isActive ? 'rgba(59,130,246,0.15)' : 'rgba(255,255,255,0.03)',
        cursor: 'pointer',
        transition: 'all 0.15s ease',
      }}
      onMouseEnter={(e) => {
        if (!isActive) {
          e.currentTarget.style.background = 'rgba(255,255,255,0.06)';
          e.currentTarget.style.borderColor = 'rgba(255,255,255,0.08)';
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          e.currentTarget.style.background = 'rgba(255,255,255,0.03)';
          e.currentTarget.style.borderColor = 'transparent';
        }
      }}
    >
      {/* Thumbnail */}
      <div style={{
        position: 'relative',
        width: '100%',
        aspectRatio: '16/9',
        borderRadius: 6,
        overflow: 'hidden',
        background: 'rgba(0,0,0,0.4)',
        marginBottom: 8,
      }}>
        <video
          src={`${job.final_video_url}#t=0.5`}
          muted
          preload="metadata"
          style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
        />
        {/* Status badge */}
        <div style={{ position: 'absolute', top: 6, right: 6 }}>
          <span style={{
            fontSize: 10,
            fontWeight: 500,
            padding: '2px 6px',
            borderRadius: 99,
            background: job.has_editor_state ? 'rgba(245,158,11,0.2)' : 'rgba(16,185,129,0.2)',
            color: job.has_editor_state ? '#f59e0b' : '#10b981',
          }}>
            {job.has_editor_state ? 'Editing' : 'New'}
          </span>
        </div>
      </div>

      {/* Info */}
      <div style={{
        fontSize: 12,
        fontWeight: 500,
        color: '#e5e5e5',
        overflow: 'hidden',
        textOverflow: 'ellipsis',
        whiteSpace: 'nowrap',
      }}>
        {job.name}
      </div>
      <div style={{ fontSize: 11, color: '#737373', marginTop: 2 }}>
        {timeAgo(job.updated_at || job.created_at)}
      </div>
    </button>
  );
};

const TOGGLE_TAB_WIDTH = 16;

const ToggleButton: React.FC<{
  isOpen: boolean;
  onClick: () => void;
}> = ({ isOpen, onClick }) => {
  return (
    <button
      onClick={onClick}
      style={{
        position: 'absolute',
        // When open: stick to the right edge of the sidebar panel
        // When closed: sit at the left edge of the wrapper
        right: isOpen ? -TOGGLE_TAB_WIDTH : undefined,
        left: isOpen ? undefined : 0,
        top: '50%',
        transform: 'translateY(-50%)',
        zIndex: 10,
        width: TOGGLE_TAB_WIDTH,
        height: 40,
        background: 'var(--editor-starter-panel, #28282e)',
        border: '1px solid rgba(255,255,255,0.12)',
        borderLeft: isOpen ? '1px solid rgba(255,255,255,0.12)' : 'none',
        borderRadius: '0 6px 6px 0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        color: '#999',
        transition: 'background 0.15s',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.12)'; e.currentTarget.style.color = '#ddd'; }}
      onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--editor-starter-panel, #28282e)'; e.currentTarget.style.color = '#999'; }}
      title={isOpen ? 'Collapse sidebar' : 'Expand sidebar'}
    >
      <svg
        width="10"
        height="10"
        viewBox="0 0 10 10"
        fill="none"
        style={{ transition: 'transform 0.15s', transform: isOpen ? 'none' : 'rotate(180deg)' }}
      >
        <path d="M6.5 1.5L3.5 5L6.5 8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
};

export const JobHistorySidebar: React.FC = () => {
  const { jobs, loading, activeJobId, setActiveJobId, sidebarOpen, toggleSidebar } = useJobHistory();

  const containerStyle = useMemo((): React.CSSProperties => ({
    ...scrollbarStyle,
    width: sidebarOpen ? SIDEBAR_WIDTH : 0,
    minWidth: sidebarOpen ? SIDEBAR_WIDTH : 0,
    height: '100%',
    overflowY: 'auto',
    overflowX: 'hidden',
    borderRight: '1px solid var(--editor-starter-border, rgba(255,255,255,0.08))',
    background: 'var(--editor-starter-panel, #28282e)',
    color: '#fff',
    transition: 'width 200ms ease, min-width 200ms ease',
  }), [sidebarOpen]);

  return (
    <div style={{ position: 'relative', flexShrink: 0, width: sidebarOpen ? SIDEBAR_WIDTH : TOGGLE_TAB_WIDTH, transition: 'width 200ms ease' }}>
      <ToggleButton isOpen={sidebarOpen} onClick={toggleSidebar} />
      <div style={containerStyle}>
        {sidebarOpen && (
          <div style={{ padding: '16px 14px 16px 16px' }}>
            {/* Header — matches InspectorLabel: text-xs font-bold text-neutral-300 */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
              <span style={{ fontSize: 12, fontWeight: 700, color: '#d4d4d4' }}>
                History
              </span>
              <span style={{ fontSize: 10, fontWeight: 500, color: '#737373' }}>
                {jobs.length}
              </span>
            </div>

            {/* Job List */}
            {loading ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {[1, 2, 3].map((i) => (
                  <div key={i} style={{ padding: 10, borderRadius: 8 }}>
                    <div style={{ aspectRatio: '16/9', borderRadius: 6, background: 'rgba(255,255,255,0.05)', marginBottom: 8 }} />
                    <div style={{ height: 12, borderRadius: 4, background: 'rgba(255,255,255,0.05)', width: '75%', marginBottom: 6 }} />
                    <div style={{ height: 10, borderRadius: 4, background: 'rgba(255,255,255,0.03)', width: '50%' }} />
                  </div>
                ))}
              </div>
            ) : jobs.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px 8px' }}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#525252" strokeWidth="1.5" style={{ margin: '0 auto 8px' }}>
                  <rect x="2" y="3" width="20" height="14" rx="2" />
                  <path d="M8 21h8M12 17v4" />
                </svg>
                <div style={{ color: '#a3a3a3', fontSize: 12, fontWeight: 500, marginBottom: 2 }}>No videos yet</div>
                <div style={{ color: '#525252', fontSize: 11, lineHeight: 1.5 }}>
                  Generate a video to start editing
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {jobs.map((job) => (
                  <JobCard
                    key={job.id}
                    job={job}
                    isActive={job.id === activeJobId}
                    onClick={() => setActiveJobId(job.id)}
                  />
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
