'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { creativeFetch } from '@/lib/creative-os-api';

/* ── Types ─────────────────────────────────────────────────────── */

interface VideoAsset {
    id: string;
    final_video_url?: string;
    video_url?: string;
    preview_url?: string;
    campaign_name?: string;
    product_name?: string;
    model_api?: string;
    length?: number;
    status?: string;
    prompt?: string;
    script_text?: string;
    video_language?: string;
    subtitles_enabled?: boolean;
    music_enabled?: boolean;
    created_at?: string;
    credits_used?: number;
    influencer_name?: string;
    metadata?: Record<string, unknown>;
}

interface VideoDetailModalProps {
    asset: VideoAsset;
    projectId: string;
    onClose: () => void;
    onRefresh?: () => void;
}

/* ── Helpers ───────────────────────────────────────────────────── */

function formatDuration(sec?: number): string {
    if (!sec) return '—';
    if (sec >= 60) return `${Math.floor(sec / 60)}m ${sec % 60}s`;
    return `${sec}s`;
}

function timeAgo(iso?: string): string {
    if (!iso) return '';
    const diff = Date.now() - new Date(iso).getTime();
    const hrs = Math.floor(diff / 3600000);
    if (hrs < 1) return `${Math.floor(diff / 60000)}m ago`;
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return days === 1 ? 'Yesterday' : `${days}d ago`;
}

function modeLabel(api?: string): string {
    if (!api) return 'Video';
    const map: Record<string, string> = {
        kling: 'UGC',
        kie: 'UGC',
        wavespeed: 'UGC',
        veo: 'Cinematic',
        cinematic: 'Cinematic',
    };
    const lower = api.toLowerCase();
    for (const [key, label] of Object.entries(map)) {
        if (lower.includes(key)) return label;
    }
    return 'Video';
}

/* ── Component ─────────────────────────────────────────────────── */

export function VideoDetailModal({ asset, projectId, onClose, onRefresh }: VideoDetailModalProps) {
    const router = useRouter();
    const videoRef = useRef<HTMLVideoElement>(null);
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(0);
    const [rePrompt, setRePrompt] = useState(asset.prompt || asset.script_text || '');
    const [generating, setGenerating] = useState(false);
    const [copied, setCopied] = useState(false);

    const videoUrl = asset.final_video_url || asset.video_url || '';
    const createdAgo = timeAgo(asset.created_at);
    const mode = modeLabel(asset.model_api);

    /* ── Video player controls ─────────────────────────────────── */

    const togglePlay = useCallback(() => {
        const v = videoRef.current;
        if (!v) return;
        if (v.paused) {
            v.play().catch(() => {});
            setIsPlaying(true);
        } else {
            v.pause();
            setIsPlaying(false);
        }
    }, []);

    useEffect(() => {
        const v = videoRef.current;
        if (!v) return;
        const onTime = () => setCurrentTime(v.currentTime);
        const onMeta = () => setDuration(v.duration);
        const onEnd = () => setIsPlaying(false);
        v.addEventListener('timeupdate', onTime);
        v.addEventListener('loadedmetadata', onMeta);
        v.addEventListener('ended', onEnd);
        return () => {
            v.removeEventListener('timeupdate', onTime);
            v.removeEventListener('loadedmetadata', onMeta);
            v.removeEventListener('ended', onEnd);
        };
    }, []);

    const seekTo = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
        const v = videoRef.current;
        if (!v || !duration) return;
        const rect = e.currentTarget.getBoundingClientRect();
        const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
        v.currentTime = pct * duration;
    }, [duration]);

    const formatSeconds = (s: number) => {
        const m = Math.floor(s / 60);
        const sec = Math.floor(s % 60);
        return `${m}:${sec.toString().padStart(2, '0')}`;
    };

    /* ── Actions ───────────────────────────────────────────────── */

    const handleDownload = useCallback(async () => {
        if (!videoUrl) return;
        try {
            const resp = await fetch(videoUrl);
            const blob = await resp.blob();
            const blobUrl = URL.createObjectURL(blob);
            const urlExt = new URL(videoUrl).pathname.split('.').pop()?.toLowerCase();
            const ext = ['mp4', 'webm', 'mov'].includes(urlExt || '') ? urlExt! : 'mp4';
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = `${asset.campaign_name || 'video'}_${asset.id?.slice(0, 8) || Date.now()}.${ext}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(blobUrl);
        } catch {
            window.open(videoUrl, '_blank');
        }
    }, [videoUrl, asset.campaign_name, asset.id]);

    const handleEdit = useCallback(() => {
        router.push(`/editor/${asset.id}`);
    }, [router, asset.id]);

    const handleSchedule = useCallback(() => {
        // TODO: Open schedule modal — for now alert
        alert('Schedule publishing coming soon!');
    }, []);

    const handleReGenerate = useCallback(async () => {
        if (!rePrompt.trim()) return;
        setGenerating(true);
        try {
            await creativeFetch('/creative-os/generate/video', {
                method: 'POST',
                body: JSON.stringify({
                    prompt: rePrompt,
                    mode: 'ugc',
                    project_id: projectId,
                    clip_length: asset.length || 5,
                }),
            });
            onRefresh?.();
            onClose();
        } catch (err) {
            console.error('Re-generation failed:', err);
            alert(`Generation failed: ${err instanceof Error ? err.message : 'Unknown error'}`);
        } finally {
            setGenerating(false);
        }
    }, [rePrompt, projectId, asset.length, onRefresh, onClose]);

    const handleCopy = useCallback(() => {
        navigator.clipboard.writeText(rePrompt);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }, [rePrompt]);

    /* ── Render ─────────────────────────────────────────────────── */

    return (
        <>
            {/* Backdrop */}
            <div
                onClick={onClose}
                style={{
                    position: 'fixed',
                    inset: 0,
                    background: 'rgba(0,0,0,0.55)',
                    backdropFilter: 'blur(6px)',
                    zIndex: 9999,
                    animation: 'vdm-fadeIn 0.2s ease',
                }}
            />

            {/* Modal */}
            <div style={{
                position: 'fixed',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                width: '94vw',
                maxWidth: '1080px',
                height: '92vh',
                maxHeight: '820px',
                background: '#FFF',
                borderRadius: '20px',
                boxShadow: '0 32px 80px rgba(0,0,0,0.25)',
                zIndex: 10000,
                display: 'flex',
                overflow: 'hidden',
                animation: 'vdm-scaleIn 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
            }}>
                {/* ── Left: Video Preview ── */}
                <div style={{
                    flex: '0 0 55%',
                    background: '#0A0A0F',
                    display: 'flex',
                    flexDirection: 'column',
                    position: 'relative',
                }}>
                    {/* Video */}
                    <div
                        onClick={togglePlay}
                        style={{
                            flex: 1,
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            cursor: 'pointer',
                            position: 'relative',
                            overflow: 'hidden',
                        }}
                    >
                        {videoUrl ? (
                            <video
                                ref={videoRef}
                                src={videoUrl}
                                playsInline
                                preload="metadata"
                                style={{
                                    maxWidth: '100%',
                                    maxHeight: '100%',
                                    objectFit: 'contain',
                                    display: 'block',
                                }}
                            />
                        ) : (
                            <div style={{
                                width: '120px', height: '120px',
                                borderRadius: '50%',
                                background: 'linear-gradient(135deg, #1a1a2e, #2d2d44)',
                            }} />
                        )}

                        {/* Play/Pause overlay */}
                        {!isPlaying && videoUrl && (
                            <div style={{
                                position: 'absolute',
                                top: '50%',
                                left: '50%',
                                transform: 'translate(-50%, -50%)',
                                width: '56px',
                                height: '56px',
                                borderRadius: '50%',
                                background: 'rgba(255,255,255,0.15)',
                                backdropFilter: 'blur(10px)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                transition: 'all 0.2s',
                            }}>
                                <svg viewBox="0 0 24 24" style={{
                                    width: '24px', height: '24px',
                                    fill: 'white', marginLeft: '3px',
                                }}>
                                    <polygon points="5,3 19,12 5,21" />
                                </svg>
                            </div>
                        )}
                    </div>

                    {/* Scrubber bar */}
                    <div style={{
                        padding: '0 16px 14px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '10px',
                    }}>
                        <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', fontWeight: 500, minWidth: '32px' }}>
                            {formatSeconds(currentTime)}
                        </span>
                        <div
                            onClick={seekTo}
                            style={{
                                flex: 1,
                                height: '4px',
                                borderRadius: '2px',
                                background: 'rgba(255,255,255,0.12)',
                                cursor: 'pointer',
                                position: 'relative',
                                overflow: 'hidden',
                            }}
                        >
                            <div style={{
                                height: '100%',
                                borderRadius: '2px',
                                background: 'linear-gradient(90deg, #337AFF, #6C5CE7)',
                                width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%`,
                                transition: 'width 0.1s linear',
                            }} />
                        </div>
                        <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', fontWeight: 500, minWidth: '32px', textAlign: 'right' }}>
                            {formatSeconds(duration)}
                        </span>
                    </div>
                </div>

                {/* ── Right: Info Panel ── */}
                <div style={{
                    flex: '1 1 auto',
                    padding: '20px 20px 16px',
                    display: 'flex',
                    flexDirection: 'column',
                    overflowY: 'auto',
                    position: 'relative',
                }}>
                    {/* Header: Name + Close */}
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        paddingBottom: '16px',
                        borderBottom: '1px solid rgba(0,0,0,0.06)',
                        marginBottom: '16px',
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                            <div style={{
                                width: '36px', height: '36px',
                                borderRadius: '50%',
                                background: 'linear-gradient(135deg, #337AFF, #6C5CE7)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                fontSize: '14px',
                                color: 'white',
                                fontWeight: 700,
                            }}>
                                {(asset.campaign_name || asset.influencer_name || 'V').charAt(0).toUpperCase()}
                            </div>
                            <div>
                                <div style={{ fontSize: '14px', fontWeight: 600, color: '#0D1B3E', lineHeight: 1.2 }}>
                                    {asset.campaign_name || asset.influencer_name || 'Video'}
                                </div>
                                <div style={{ fontSize: '12px', color: '#8A93B0', marginTop: '1px' }}>
                                    {createdAgo || 'Video'}
                                </div>
                            </div>
                        </div>
                        <button
                            onClick={onClose}
                            style={{
                                width: '30px', height: '30px',
                                borderRadius: '50%',
                                border: 'none',
                                background: 'rgba(0,0,0,0.05)',
                                cursor: 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                padding: 0,
                                transition: 'background 0.15s',
                                flexShrink: 0,
                            }}
                            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.1)')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.05)')}
                        >
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#666" strokeWidth="2" strokeLinecap="round">
                                <line x1="1" y1="1" x2="11" y2="11" />
                                <line x1="11" y1="1" x2="1" y2="11" />
                            </svg>
                        </button>
                    </div>

                    {/* Script / Prompt */}
                    {(asset.prompt || asset.script_text) && (
                        <div style={{ marginBottom: '20px' }}>
                            <div style={{
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'space-between',
                                marginBottom: '8px',
                            }}>
                                <span style={{
                                    fontSize: '11px', fontWeight: 700, color: '#8A93B0',
                                    letterSpacing: '0.5px', textTransform: 'uppercase',
                                }}>
                                    {asset.script_text ? 'SCRIPT' : 'PROMPT'}
                                </span>
                                <button
                                    onClick={handleCopy}
                                    style={{
                                        fontSize: '12px', color: '#337AFF',
                                        background: 'none', border: 'none',
                                        cursor: 'pointer', fontWeight: 600,
                                        padding: '2px 8px', borderRadius: '4px',
                                    }}
                                >{copied ? '✓ Copied' : 'Copy'}</button>
                            </div>
                            <div style={{
                                padding: '12px 14px',
                                borderRadius: '10px',
                                borderLeft: '3px solid #6C5CE7',
                                background: 'rgba(108,92,231,0.03)',
                                fontSize: '13px',
                                color: '#4A5578',
                                lineHeight: '1.65',
                                fontStyle: 'italic',
                                maxHeight: '120px',
                                overflowY: 'auto',
                            }}>
                                &ldquo;{asset.script_text || asset.prompt}&rdquo;
                            </div>
                        </div>
                    )}

                    {/* Information */}
                    <div style={{ marginBottom: '16px' }}>
                        <span style={{
                            fontSize: '11px', fontWeight: 700, color: '#8A93B0',
                            letterSpacing: '0.5px', textTransform: 'uppercase',
                            display: 'block', marginBottom: '8px',
                        }}>INFORMATION</span>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <InfoRow label="Mode" value={mode} highlight />
                            <InfoRow label="Duration" value={formatDuration(asset.length)} />
                            <InfoRow label="Language" value={
                                asset.video_language === 'en' ? 'English' :
                                asset.video_language === 'es' ? 'Spanish' :
                                asset.video_language || 'English'
                            } />
                            {asset.music_enabled !== undefined && (
                                <InfoRow label="Music" value={asset.music_enabled ? 'Included' : 'None'} />
                            )}
                            {asset.subtitles_enabled !== undefined && (
                                <InfoRow label="Captions" value={asset.subtitles_enabled ? 'Burned' : 'None'} />
                            )}
                            {asset.credits_used && (
                                <InfoRow label="Cost" value={`${asset.credits_used} credits`} />
                            )}
                            {createdAgo && <InfoRow label="Created" value={createdAgo} />}
                        </div>
                    </div>

                    {/* Re-prompt */}
                    <div style={{ marginBottom: '16px' }}>
                        <span style={{
                            fontSize: '11px', fontWeight: 700, color: '#8A93B0',
                            letterSpacing: '0.5px', textTransform: 'uppercase',
                            display: 'block', marginBottom: '8px',
                        }}>RE-PROMPT</span>
                        <textarea
                            value={rePrompt}
                            onChange={e => setRePrompt(e.target.value)}
                            placeholder="Describe the video you want to regenerate..."
                            rows={3}
                            style={{
                                width: '100%',
                                padding: '10px 12px',
                                borderRadius: '10px',
                                border: '1px solid rgba(0,0,0,0.08)',
                                borderLeft: '3px solid #337AFF',
                                background: 'rgba(51,122,255,0.02)',
                                fontSize: '13px',
                                color: '#0D1B3E',
                                lineHeight: '1.5',
                                resize: 'none',
                                outline: 'none',
                                fontFamily: 'inherit',
                                boxSizing: 'border-box',
                            }}
                        />
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            marginTop: '8px',
                            gap: '8px',
                        }}>
                            <span style={{
                                fontSize: '13px',
                                color: '#8A93B0',
                                lineHeight: '1.35',
                                flex: 1,
                            }}>Edit the prompt above and re-generate to create a new variation</span>
                            <button
                                onClick={handleReGenerate}
                                disabled={generating || !rePrompt.trim()}
                                style={{
                                    padding: '7px 14px',
                                    borderRadius: '8px',
                                    border: '1px solid rgba(51,122,255,0.2)',
                                    background: 'rgba(51,122,255,0.06)',
                                    color: '#337AFF',
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    cursor: generating ? 'wait' : 'pointer',
                                    opacity: generating || !rePrompt.trim() ? 0.5 : 1,
                                    transition: 'all 0.15s',
                                    whiteSpace: 'nowrap',
                                    flexShrink: 0,
                                }}
                            >
                                {generating ? '⏳ Generating...' : '✨ Re-generate'}
                            </button>
                        </div>
                    </div>

                    {/* Spacer */}
                    <div style={{ flex: 1 }} />

                    {/* Action Buttons */}
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: '1fr 1fr',
                        gap: '8px',
                    }}>
                        <ActionButton label="Download" onClick={handleDownload} icon={
                            <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2' }}>
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" />
                            </svg>
                        } />
                        <ActionButton label="Schedule" onClick={handleSchedule} icon={
                            <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2' }}>
                                <rect x="3" y="4" width="18" height="18" rx="2" />
                                <line x1="16" y1="2" x2="16" y2="6" />
                                <line x1="8" y1="2" x2="8" y2="6" />
                                <line x1="3" y1="10" x2="21" y2="10" />
                            </svg>
                        } />
                        <ActionButton
                            label="Edit in Editor"
                            onClick={handleEdit}
                            primary
                            icon={
                                <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2' }}>
                                    <path d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 1 1 3.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                </svg>
                            }
                        />
                        <ActionButton
                            label="Extend"
                            onClick={() => alert('Video extension coming soon!')}
                            icon={
                                <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2' }}>
                                    <path d="M17 1l4 4-4 4" />
                                    <path d="M3 11V9a4 4 0 0 1 4-4h14" />
                                    <path d="M7 23l-4-4 4-4" />
                                    <path d="M21 13v2a4 4 0 0 1-4 4H3" />
                                </svg>
                            }
                        />
                    </div>
                </div>
            </div>

            <style>{`
                @keyframes vdm-fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @keyframes vdm-scaleIn {
                    from { opacity: 0; transform: translate(-50%, -50%) scale(0.95); }
                    to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
                }
            `}</style>
        </>
    );
}

/* ── Sub-components ──────────────────────────────────────────────── */

function InfoRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
    return (
        <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '6px 0',
            borderBottom: '1px solid rgba(0,0,0,0.04)',
        }}>
            <span style={{ fontSize: '13px', color: '#8A93B0' }}>{label}</span>
            <span style={{
                fontSize: '13px',
                fontWeight: 600,
                color: highlight ? '#337AFF' : '#5A6178',
            }}>{value}</span>
        </div>
    );
}

function ActionButton({
    label, onClick, disabled, icon, primary,
}: {
    label: string;
    onClick: () => void;
    disabled?: boolean;
    icon?: React.ReactNode;
    primary?: boolean;
}) {
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            style={{
                padding: '10px 12px',
                borderRadius: '10px',
                border: primary ? 'none' : '1px solid rgba(0,0,0,0.08)',
                background: primary ? 'linear-gradient(135deg, #337AFF, #6C5CE7)' : 'white',
                color: primary ? 'white' : '#5A6178',
                fontSize: '13px',
                fontWeight: 600,
                cursor: disabled ? 'wait' : 'pointer',
                transition: 'all 0.15s',
                opacity: disabled ? 0.5 : 1,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: '6px',
            }}
            onMouseEnter={e => {
                if (!disabled && !primary) e.currentTarget.style.background = 'rgba(51,122,255,0.04)';
            }}
            onMouseLeave={e => {
                if (!primary) e.currentTarget.style.background = 'white';
            }}
        >
            {icon}
            {label}
        </button>
    );
}
