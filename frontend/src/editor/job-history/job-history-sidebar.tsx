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
      className={`w-full text-left p-2.5 rounded-lg transition-all duration-150 group ${
        isActive
          ? 'bg-blue-600/20 border border-blue-500/50'
          : 'bg-white/[0.04] border border-transparent hover:bg-white/[0.08] hover:border-white/10'
      }`}
    >
      {/* Thumbnail */}
      <div className="relative w-full aspect-video rounded overflow-hidden bg-black/40 mb-2">
        <video
          src={`${job.final_video_url}#t=0.5`}
          muted
          preload="metadata"
          className="w-full h-full object-cover"
        />
        {/* Status badge */}
        <div className="absolute top-1.5 right-1.5">
          <span
            className={`text-[10px] font-medium px-1.5 py-0.5 rounded-full ${
              job.has_editor_state
                ? 'bg-amber-500/20 text-amber-400'
                : 'bg-emerald-500/20 text-emerald-400'
            }`}
          >
            {job.has_editor_state ? 'Editing' : 'New'}
          </span>
        </div>
      </div>

      {/* Info */}
      <div className="truncate text-xs font-medium text-neutral-200">
        {job.name}
      </div>
      <div className="text-[11px] text-neutral-500 mt-0.5">
        {timeAgo(job.updated_at || job.created_at)}
      </div>
    </button>
  );
};

const ToggleButton: React.FC<{
  isOpen: boolean;
  onClick: () => void;
}> = ({ isOpen, onClick }) => {
  return (
    <button
      onClick={onClick}
      className="absolute -right-3 top-1/2 -translate-y-1/2 z-10 w-6 h-10 bg-editor-starter-panel border border-white/10 rounded-r-md flex items-center justify-center hover:bg-white/10 transition-colors"
      title={isOpen ? 'Collapse sidebar' : 'Expand sidebar'}
    >
      <svg
        width="10"
        height="10"
        viewBox="0 0 10 10"
        fill="none"
        className={`transition-transform ${isOpen ? '' : 'rotate-180'}`}
      >
        <path d="M6.5 1.5L3.5 5L6.5 8.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </button>
  );
};

export const JobHistorySidebar: React.FC = () => {
  const { jobs, loading, activeJobId, setActiveJobId, sidebarOpen, toggleSidebar } = useJobHistory();

  const style = useMemo((): React.CSSProperties => ({
    ...scrollbarStyle,
    width: sidebarOpen ? SIDEBAR_WIDTH : 0,
    minWidth: sidebarOpen ? SIDEBAR_WIDTH : 0,
    transition: 'width 200ms ease, min-width 200ms ease',
  }), [sidebarOpen]);

  return (
    <div className="relative flex-shrink-0" style={{ width: sidebarOpen ? SIDEBAR_WIDTH : 0 }}>
      <ToggleButton isOpen={sidebarOpen} onClick={toggleSidebar} />
      <div
        className="border-r-editor-starter-border bg-editor-starter-panel h-full overflow-y-auto overflow-x-hidden border-r text-white"
        style={style}
      >
        {sidebarOpen && (
          <div className="p-4">
            {/* Header — matches InspectorLabel style: text-xs font-bold text-neutral-300 */}
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-bold text-neutral-300">
                History
              </span>
              <span className="text-[10px] font-medium text-neutral-500">
                {jobs.length}
              </span>
            </div>

            {/* Job List */}
            {loading ? (
              <div className="flex flex-col gap-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="w-full rounded-lg p-2.5">
                    <div className="aspect-video rounded bg-white/[0.06] mb-2 animate-pulse" />
                    <div className="h-3 bg-white/[0.06] rounded w-3/4 mb-1.5 animate-pulse" />
                    <div className="h-2 bg-white/[0.04] rounded w-1/2 animate-pulse" />
                  </div>
                ))}
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-6 px-2">
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mx-auto mb-2 text-neutral-600">
                  <rect x="2" y="3" width="20" height="14" rx="2" />
                  <path d="M8 21h8M12 17v4" />
                </svg>
                <div className="text-neutral-400 text-xs font-medium mb-0.5">No videos yet</div>
                <div className="text-neutral-600 text-[11px] leading-relaxed">
                  Generate a video to start editing
                </div>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
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
