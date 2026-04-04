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
      className={`w-full text-left p-3 rounded-lg transition-all duration-150 group ${
        isActive
          ? 'bg-blue-600/20 border border-blue-500/50'
          : 'bg-white/5 border border-transparent hover:bg-white/10 hover:border-white/10'
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
      <div className="truncate text-sm font-medium text-white/90">
        {job.name}
      </div>
      <div className="text-[11px] text-white/40 mt-0.5">
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
          <div className="p-3">
            {/* Header */}
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-white/50">
                Video History
              </h3>
              <span className="text-[10px] text-white/30">
                {jobs.length} videos
              </span>
            </div>

            {/* Job List */}
            {loading ? (
              <div className="flex flex-col gap-2">
                {[1, 2, 3].map((i) => (
                  <div key={i} className="w-full bg-white/5 rounded-lg animate-pulse">
                    <div className="aspect-video rounded bg-white/5 mb-2" />
                    <div className="h-3 bg-white/5 rounded w-3/4 mx-3 mb-2" />
                    <div className="h-2 bg-white/5 rounded w-1/2 mx-3 mb-3" />
                  </div>
                ))}
              </div>
            ) : jobs.length === 0 ? (
              <div className="text-center py-8">
                <div className="text-white/30 text-sm mb-1">No videos yet</div>
                <div className="text-white/20 text-xs">
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
