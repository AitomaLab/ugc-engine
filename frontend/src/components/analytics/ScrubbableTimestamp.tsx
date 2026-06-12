'use client';

import { timestampToSeconds } from './analytics-types';

interface Props {
    ts: string | null | undefined;
    videoRef: React.RefObject<HTMLVideoElement | null>;
    label?: string;
}

export default function ScrubbableTimestamp({ ts, videoRef, label }: Props) {
    if (!ts) return null;
    const seconds = timestampToSeconds(ts);
    return (
        <button
            type="button"
            onClick={(e) => {
                e.stopPropagation();
                const video = videoRef.current;
                if (!video) return;
                try {
                    video.currentTime = seconds;
                    void video.play().catch(() => {});
                } catch {
                    // Ignore — happens when the source has no media metadata loaded yet.
                }
            }}
            style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '4px',
                padding: '3px 8px',
                borderRadius: '999px',
                border: '1px solid var(--border)',
                background: 'var(--blue-light)',
                color: 'var(--blue)',
                fontSize: '11px',
                fontWeight: 700,
                fontFamily: 'ui-monospace, SFMono-Regular, monospace',
                cursor: 'pointer',
                transition: 'background 0.15s ease',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(51,122,255,0.18)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'var(--blue-light)'; }}
            aria-label={label ? `${label} — jump to ${ts}` : `Jump to ${ts}`}
        >
            <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5.14v13.72a1 1 0 001.5.86l11.24-6.86a1 1 0 000-1.72L9.5 4.28A1 1 0 008 5.14z" />
            </svg>
            {ts}
        </button>
    );
}
