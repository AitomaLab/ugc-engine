'use client';

import { useEffect } from 'react';

interface Props {
    title: string;
    onClose: () => void;
    children: React.ReactNode;
    /** Sets the modal's max width — passes through to the shell's CSS. */
    maxWidth?: number;
    /** Optional footer row (typically primary + cancel CTAs). */
    footer?: React.ReactNode;
}

/**
 * Tiny modal primitive used by the analytics v2 surfaces (Add Account,
 * Settings, Account Detail). Deliberately co-located in the analytics
 * folder so we don't add a one-off dependency on a shared modal lib.
 *
 * Pattern matches PostDetailModal — backdrop click + Escape to close,
 * `flex: 1, minHeight: 0` body so long content scrolls inside instead
 * of blowing out the viewport.
 */
export default function Modal({ title, onClose, children, maxWidth = 560, footer }: Props) {
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [onClose]);

    return (
        <div
            onClick={onClose}
            style={{
                position: 'fixed', inset: 0,
                background: 'rgba(13,27,62,0.55)',
                backdropFilter: 'blur(6px)',
                zIndex: 9999,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '24px',
                animation: 'analytics-modal-fade 0.18s ease-out',
            }}
        >
            <div
                onClick={(e) => e.stopPropagation()}
                style={{
                    background: 'white',
                    borderRadius: 'var(--radius)',
                    boxShadow: 'var(--shadow-lg)',
                    width: '100%',
                    maxWidth,
                    maxHeight: '92vh',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                }}
            >
                <div
                    style={{
                        padding: '14px 18px',
                        borderBottom: '1px solid var(--border)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '12px',
                    }}
                >
                    <h2 style={{ margin: 0, fontSize: '15px', fontWeight: 700, color: 'var(--text-1)' }}>
                        {title}
                    </h2>
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label="Close"
                        style={{
                            width: 32, height: 32, borderRadius: '8px',
                            border: '1px solid var(--border)',
                            background: 'white', cursor: 'pointer',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            color: 'var(--text-2)',
                        }}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5} strokeLinecap="round">
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                </div>

                <div
                    style={{
                        flex: 1,
                        minHeight: 0,
                        overflowY: 'auto',
                        padding: '18px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '14px',
                    }}
                >
                    {children}
                </div>

                {footer && (
                    <div
                        style={{
                            padding: '12px 18px',
                            borderTop: '1px solid var(--border)',
                            display: 'flex',
                            justifyContent: 'flex-end',
                            gap: '8px',
                            background: 'var(--blue-light)',
                        }}
                    >
                        {footer}
                    </div>
                )}
            </div>

            <style>{`
                @keyframes analytics-modal-fade {
                    from { opacity: 0; transform: scale(0.98); }
                    to { opacity: 1; transform: scale(1); }
                }
            `}</style>
        </div>
    );
}
