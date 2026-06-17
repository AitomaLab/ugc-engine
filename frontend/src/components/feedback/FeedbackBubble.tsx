'use client';

import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import { usePathname } from 'next/navigation';
import { useApp } from '@/providers/AppProvider';

const PRIMARY = '#337AFF';
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const HIDDEN_PREFIXES = ['/editor', '/admin', '/login', '/signup', '/forgot-password', '/reset-password', '/logout'];

function isHiddenRoute(pathname: string | null): boolean {
    if (!pathname) return true;
    return HIDDEN_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

function truncateFileName(name: string, max = 24): string {
    if (name.length <= max) return name;
    return `${name.slice(0, max - 1)}…`;
}

function FeedbackBubbleIcon({ size = 24 }: { size?: number }) {
    return (
        <svg
            width={size}
            height={size}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
        >
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
            <path d="M12 8v4" />
            <path d="M12 16h.01" />
        </svg>
    );
}

export function FeedbackBubble() {
    const pathname = usePathname();
    const { getAuthHeaders } = useApp();
    const fileInputRef = useRef<HTMLInputElement>(null);
    const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    const [open, setOpen] = useState(false);
    const [panelVisible, setPanelVisible] = useState(false);
    const [narrow, setNarrow] = useState(false);
    const [name, setName] = useState('');
    const [message, setMessage] = useState('');
    const [imageFile, setImageFile] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [sending, setSending] = useState(false);
    const [error, setError] = useState('');
    const [thanks, setThanks] = useState(false);
    const [submitAttempted, setSubmitAttempted] = useState(false);

    useEffect(() => {
        const check = () => setNarrow(window.innerWidth < 420);
        check();
        window.addEventListener('resize', check);
        return () => window.removeEventListener('resize', check);
    }, []);

    useEffect(() => {
        if (open) {
            requestAnimationFrame(() => setPanelVisible(true));
        } else {
            setPanelVisible(false);
        }
    }, [open]);

    useEffect(() => {
        return () => {
            if (previewUrl) URL.revokeObjectURL(previewUrl);
            if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
        };
    }, [previewUrl]);

    const resetForm = useCallback(() => {
        setName('');
        setMessage('');
        setImageFile(null);
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setPreviewUrl(null);
        setError('');
        setThanks(false);
        setSubmitAttempted(false);
        setSending(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
    }, [previewUrl]);

    const close = useCallback(() => {
        setPanelVisible(false);
        if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
        closeTimerRef.current = setTimeout(() => {
            setOpen(false);
            resetForm();
        }, 200);
    }, [resetForm]);

    const toggleOpen = () => {
        if (open) {
            close();
        } else {
            if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
            setOpen(true);
        }
    };

    const onPickImage = (file: File | null) => {
        if (previewUrl) URL.revokeObjectURL(previewUrl);
        setImageFile(file);
        setPreviewUrl(file ? URL.createObjectURL(file) : null);
    };

    const clearImage = () => {
        onPickImage(null);
        if (fileInputRef.current) fileInputRef.current.value = '';
    };

    const submit = async () => {
        setSubmitAttempted(true);
        if (!name.trim() || !message.trim()) return;

        setSending(true);
        setError('');
        try {
            const fd = new FormData();
            fd.append('name', name.trim());
            fd.append('message', message.trim());
            if (imageFile) fd.append('image', imageFile);

            const res = await fetch(`${API_BASE}/api/feedback/submit`, {
                method: 'POST',
                headers: getAuthHeaders(),
                body: fd,
            });
            const text = await res.text();
            const json = text ? JSON.parse(text) : {};
            if (!res.ok) {
                throw new Error((json as { detail?: string })?.detail || 'Could not send feedback.');
            }
            setThanks(true);
            closeTimerRef.current = setTimeout(() => {
                close();
            }, 2000);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Could not send feedback.');
        } finally {
            setSending(false);
        }
    };

    const canSubmit = Boolean(name.trim() && message.trim()) && !sending;
    const nameInvalid = submitAttempted && !name.trim();
    const messageInvalid = submitAttempted && !message.trim();

    const handleSubmitClick = () => {
        if (!name.trim() || !message.trim() || sending) {
            setSubmitAttempted(true);
            return;
        }
        void submit();
    };

    if (isHiddenRoute(pathname)) return null;

    const panelStyle: CSSProperties = {
        position: 'fixed',
        bottom: 84,
        right: narrow ? 12 : 20,
        left: narrow ? 12 : undefined,
        width: narrow ? 'auto' : 360,
        maxHeight: 520,
        overflowY: 'auto',
        zIndex: 59,
        background: '#FFFFFF',
        borderRadius: 16,
        border: '1px solid #E2E8F0',
        boxShadow: '0 8px 32px rgba(15, 23, 42, 0.14)',
        opacity: panelVisible ? 1 : 0,
        transform: panelVisible ? 'translateY(0)' : 'translateY(12px)',
        transition: 'transform 200ms ease-out, opacity 200ms ease-out',
        pointerEvents: panelVisible ? 'auto' : 'none',
    };

    return (
        <>
            <style>{`@keyframes admin-spin { to { transform: rotate(360deg); } }`}</style>

            <button
                type="button"
                aria-label="Send feedback"
                aria-expanded={open}
                onClick={toggleOpen}
                style={{
                    position: 'fixed',
                    right: 20,
                    bottom: 20,
                    zIndex: 60,
                    width: 56,
                    height: 56,
                    borderRadius: '50%',
                    border: 'none',
                    background: PRIMARY,
                    color: '#FFFFFF',
                    boxShadow: '0 4px 14px rgba(51,122,255,0.45)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    transition: 'transform 0.15s ease',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.transform = 'scale(1.05)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.transform = 'scale(1)'; }}
            >
                <FeedbackBubbleIcon size={24} />
            </button>

            {open && (
                <div
                    role="dialog"
                    aria-labelledby="feedback-panel-title"
                    style={panelStyle}
                >
                    <div
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            padding: '14px 16px',
                            borderBottom: '1px solid #F1F5F9',
                        }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={PRIMARY} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                            </svg>
                            <span id="feedback-panel-title" style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>
                                Send Feedback
                            </span>
                        </div>
                        <button
                            type="button"
                            aria-label="Close feedback panel"
                            onClick={close}
                            style={{
                                background: 'none',
                                border: 'none',
                                padding: 4,
                                cursor: 'pointer',
                                color: '#94A3B8',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}
                            onMouseEnter={(e) => { e.currentTarget.style.color = '#0F172A'; }}
                            onMouseLeave={(e) => { e.currentTarget.style.color = '#94A3B8'; }}
                        >
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                                <path d="M18 6 6 18M6 6l12 12" />
                            </svg>
                        </button>
                    </div>

                    {thanks ? (
                        <div
                            style={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: 10,
                                padding: '40px 24px',
                                textAlign: 'center',
                            }}
                        >
                            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                                <path d="M22 4 12 14.01l-3-3" />
                            </svg>
                            <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: '#059669' }}>
                                Thanks for your feedback!
                            </p>
                        </div>
                    ) : (
                        <div style={{ padding: '16px' }}>
                            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
                                Name
                            </label>
                            <input
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder="Your name"
                                style={{
                                    ...inputStyle,
                                    borderColor: nameInvalid ? '#EF4444' : '#E2E8F0',
                                }}
                            />
                            {nameInvalid && (
                                <p style={{ margin: '4px 0 0', fontSize: 11, color: '#EF4444' }}>Required</p>
                            )}

                            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', margin: '12px 0 6px' }}>
                                Your feedback
                            </label>
                            <textarea
                                value={message}
                                onChange={(e) => setMessage(e.target.value)}
                                placeholder="What's on your mind?"
                                rows={4}
                                style={{
                                    ...inputStyle,
                                    resize: 'vertical',
                                    borderColor: messageInvalid ? '#EF4444' : '#E2E8F0',
                                }}
                            />
                            {messageInvalid && (
                                <p style={{ margin: '4px 0 0', fontSize: 11, color: '#EF4444' }}>Required</p>
                            )}

                            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, color: '#374151', margin: '12px 0 6px' }}>
                                Attach image{' '}
                                <span style={{ fontWeight: 500, color: '#94A3B8' }}>(optional)</span>
                            </label>
                            <input
                                ref={fileInputRef}
                                type="file"
                                accept="image/*"
                                onChange={(e) => onPickImage(e.target.files?.[0] || null)}
                                style={{ display: 'none' }}
                            />
                            {imageFile && previewUrl ? (
                                <div
                                    style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: 10,
                                        padding: '8px 12px',
                                        border: '1px solid #E2E8F0',
                                        borderRadius: 10,
                                        background: '#F8FAFC',
                                    }}
                                >
                                    <img
                                        src={previewUrl}
                                        alt="Preview"
                                        style={{ width: 48, height: 48, borderRadius: 8, objectFit: 'cover', flexShrink: 0 }}
                                    />
                                    <span style={{ flex: 1, fontSize: 13, color: '#64748B', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                        {truncateFileName(imageFile.name)}
                                    </span>
                                    <button
                                        type="button"
                                        aria-label="Remove image"
                                        onClick={clearImage}
                                        style={{
                                            background: 'none',
                                            border: 'none',
                                            padding: 4,
                                            cursor: 'pointer',
                                            color: '#94A3B8',
                                            fontSize: 18,
                                            lineHeight: 1,
                                        }}
                                        onMouseEnter={(e) => { e.currentTarget.style.color = '#EF4444'; }}
                                        onMouseLeave={(e) => { e.currentTarget.style.color = '#94A3B8'; }}
                                    >
                                        ×
                                    </button>
                                </div>
                            ) : (
                                <button
                                    type="button"
                                    onClick={() => fileInputRef.current?.click()}
                                    style={{
                                        width: '100%',
                                        border: '1.5px dashed #CBD5E1',
                                        borderRadius: 10,
                                        padding: '12px 16px',
                                        background: '#F8FAFC',
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        gap: 8,
                                    }}
                                >
                                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                        <polyline points="17 8 12 3 7 8" />
                                        <line x1="12" y1="3" x2="12" y2="15" />
                                    </svg>
                                    <span style={{ fontSize: 13, color: '#64748B' }}>Attach a screenshot</span>
                                </button>
                            )}

                            <div style={{ marginTop: 16 }}>
                                <button
                                    type="button"
                                    aria-disabled={!canSubmit}
                                    onClick={handleSubmitClick}
                                    style={{
                                        width: '100%',
                                        padding: 11,
                                        borderRadius: 10,
                                        background: canSubmit ? PRIMARY : '#94A3B8',
                                        color: '#FFFFFF',
                                        fontSize: 14,
                                        fontWeight: 700,
                                        border: 'none',
                                        cursor: canSubmit ? 'pointer' : 'not-allowed',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        gap: 8,
                                    }}
                                >
                                    {sending ? (
                                        <>
                                            <span
                                                style={{
                                                    width: 14,
                                                    height: 14,
                                                    border: '2px solid rgba(255,255,255,0.35)',
                                                    borderTopColor: '#FFFFFF',
                                                    borderRadius: '50%',
                                                    animation: 'admin-spin 0.7s linear infinite',
                                                    flexShrink: 0,
                                                }}
                                            />
                                            Sending…
                                        </>
                                    ) : (
                                        'Submit'
                                    )}
                                </button>
                            </div>

                            {error && (
                                <div
                                    style={{
                                        marginTop: 10,
                                        background: 'rgba(220,38,38,0.10)',
                                        color: '#DC2626',
                                        fontSize: 13,
                                        borderRadius: 8,
                                        padding: '8px 12px',
                                    }}
                                >
                                    {error}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            )}
        </>
    );
}

const inputStyle: CSSProperties = {
    width: '100%',
    padding: '10px 12px',
    border: '1px solid #E2E8F0',
    borderRadius: 10,
    fontSize: 14,
    outline: 'none',
    boxSizing: 'border-box',
    color: '#0F172A',
    fontFamily: 'inherit',
};
