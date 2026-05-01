'use client';

import { useState, useCallback, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { creativeFetch } from '@/lib/creative-os-api';
import { useTranslation } from '@/lib/i18n';
import { MODAL_HEIGHT, MODAL_WIDTH } from '@/lib/modal-sizing';
import { SharePopover } from './SharePopover';

/* Renders the animation preview clip; falls back to a large emoji tile on load error.
   The container is a fixed 9:16 box to match Kling's output aspect ratio. */
function AnimationPreview({ style }: { style: { emoji: string; previewUrl?: string } }) {
    const [failed, setFailed] = useState(false);
    return (
        <div style={{
            width: '100%',
            aspectRatio: '9 / 16',
            background: 'linear-gradient(180deg, #F4F6FA 0%, #E9EEF6 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            overflow: 'hidden',
        }}>
            {style.previewUrl && !failed ? (
                <video
                    src={style.previewUrl}
                    autoPlay
                    loop
                    muted
                    playsInline
                    onError={() => setFailed(true)}
                    style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                        display: 'block',
                    }}
                />
            ) : (
                <div style={{ fontSize: '48px', lineHeight: 1, opacity: 0.7 }}>
                    {style.emoji}
                </div>
            )}
        </div>
    );
}

interface ImageAsset {
    id: string;
    image_url?: string;
    result_url?: string;
    prompt?: string;
    shot_type?: string;
    product_name?: string;
    product_id?: string;
    influencer_id?: string;
    analysis_json?: Record<string, unknown>;
    created_at?: string;
    status?: string;
    metadata?: Record<string, unknown>;
}

interface ImageEditModalProps {
    asset: ImageAsset;
    projectId: string;
    onClose: () => void;
    onGenerated?: () => void;
    onAnimated?: () => void;
    onCreateVideo?: (asset: ImageAsset) => void;
}

/* ── All 12 animation styles — all use Kling 3.0 ── */
/* previewUrl points to a 5s looping MP4 in /public/animation-previews/.
   Cards fall back to the emoji if the video file is missing.
   Labels + descriptions are translated via labelKey / descKey. */
const ANIMATION_STYLES = [
    { id: 'dolly_in', labelKey: 'creativeOs.imageModal.animStyleDollyIn', descKey: 'creativeOs.imageModal.animStyleDollyInDesc', emoji: '🎯', previewUrl: '/animation-previews/dolly_in.mp4' },
    { id: 'dolly_out', labelKey: 'creativeOs.imageModal.animStyleDollyOut', descKey: 'creativeOs.imageModal.animStyleDollyOutDesc', emoji: '🔭', previewUrl: '/animation-previews/dolly_out.mp4' },
    { id: 'orbit', labelKey: 'creativeOs.imageModal.animStyleOrbit', descKey: 'creativeOs.imageModal.animStyleOrbitDesc', emoji: '🌀', previewUrl: '/animation-previews/orbit.mp4' },
    { id: 'tracking', labelKey: 'creativeOs.imageModal.animStyleTracking', descKey: 'creativeOs.imageModal.animStyleTrackingDesc', emoji: '🏃', previewUrl: '/animation-previews/tracking.mp4' },
    { id: 'pan', labelKey: 'creativeOs.imageModal.animStylePan', descKey: 'creativeOs.imageModal.animStylePanDesc', emoji: '↔️', previewUrl: '/animation-previews/pan.mp4' },
    { id: 'tilt', labelKey: 'creativeOs.imageModal.animStyleTilt', descKey: 'creativeOs.imageModal.animStyleTiltDesc', emoji: '↕️', previewUrl: '/animation-previews/tilt.mp4' },
    { id: 'crane', labelKey: 'creativeOs.imageModal.animStyleCrane', descKey: 'creativeOs.imageModal.animStyleCraneDesc', emoji: '🏗️', previewUrl: '/animation-previews/crane.mp4' },
    { id: 'static', labelKey: 'creativeOs.imageModal.animStyleStatic', descKey: 'creativeOs.imageModal.animStyleStaticDesc', emoji: '📷', previewUrl: '/animation-previews/static.mp4' },
    { id: 'handheld', labelKey: 'creativeOs.imageModal.animStyleHandheld', descKey: 'creativeOs.imageModal.animStyleHandheldDesc', emoji: '🤳', previewUrl: '/animation-previews/handheld.mp4' },
    { id: 'reveal', labelKey: 'creativeOs.imageModal.animStyleReveal', descKey: 'creativeOs.imageModal.animStyleRevealDesc', emoji: '✨', previewUrl: '/animation-previews/reveal.mp4' },
    { id: 'float', labelKey: 'creativeOs.imageModal.animStyleFloat', descKey: 'creativeOs.imageModal.animStyleFloatDesc', emoji: '🎈', previewUrl: '/animation-previews/float.mp4' },
    { id: 'drift', labelKey: 'creativeOs.imageModal.animStyleDrift', descKey: 'creativeOs.imageModal.animStyleDriftDesc', emoji: '🌊', previewUrl: '/animation-previews/drift.mp4' },
];

/* ── Quick action system prompts for NanoBanana Pro enhancements ── */
const QUICK_ACTIONS = [
    {
        id: 'animate',
        labelKey: 'creativeOs.imageModal.quickAnimate',
        icon: 'M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653z',
        systemPrompt: '',
        isAnimate: true,
    },
    {
        id: 'upscale',
        labelKey: 'creativeOs.imageModal.quickUpscale',
        icon: 'M21 21l-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607zM10.5 7.5v6m3-3h-6',
        systemPrompt: 'Upscale this image to ultra-high resolution. Enhance fine details, textures, skin pores, fabric patterns, and text sharpness. Maintain exact composition, colors, and lighting.',
    },
    {
        id: 'relight',
        labelKey: 'creativeOs.imageModal.quickRelight',
        icon: 'M12 18v-5.25m0 0a6.01 6.01 0 0 0 1.5-.189m-1.5.189a6.01 6.01 0 0 1-1.5-.189m3.75 7.478a12.06 12.06 0 0 1-4.5 0m3.75 2.383a14.406 14.406 0 0 1-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 1 0-7.517 0c.85.493 1.509 1.333 1.509 2.316V18',
        systemPrompt: 'Relight this image with golden hour natural lighting. Add warm, soft directional light from the upper left. Create gentle shadows for depth. Add a subtle rim light on the subject. Make the lighting look like a professional studio setup.',
    },
    {
        id: 'angles',
        labelKey: 'creativeOs.imageModal.quickNewAngle',
        icon: 'M6.827 6.175A2.31 2.31 0 0 1 5.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 0 0-1.134-.175 2.31 2.31 0 0 1-1.64-1.055l-.822-1.316a2.192 2.192 0 0 0-1.736-1.039 48.774 48.774 0 0 0-5.232 0 2.192 2.192 0 0 0-1.736 1.039l-.821 1.316z M16.5 12.75a4.5 4.5 0 1 1-9 0 4.5 4.5 0 0 1 9 0z',
        systemPrompt: 'Generate a new angle of this same subject. Keep the same person, product, and styling, but change the camera angle to a different perspective. Try a 3/4 view, slightly from below, or an over-the-shoulder angle. Maintain identical lighting and color grade.',
    },
];

export function ImageEditModal({ asset, projectId, onClose, onGenerated, onAnimated, onCreateVideo }: ImageEditModalProps) {
    const { t } = useTranslation();
    const [editPrompt, setEditPrompt] = useState(asset.prompt || '');
    const [isAnimating, setIsAnimating] = useState(false);
    const [selectedAnimStyle, setSelectedAnimStyle] = useState<string>('dolly_in');
    const [animDuration, setAnimDuration] = useState(5);
    const [generating, setGenerating] = useState(false);
    const [actionLoading, setActionLoading] = useState<string | null>(null);
    const [copied, setCopied] = useState(false);
    const [showAnimateModal, setShowAnimateModal] = useState(false);
    const [shareOpen, setShareOpen] = useState(false);
    const [mounted, setMounted] = useState(false);
    useEffect(() => { setMounted(true); }, []);

    // ── Editable title ──────────────────────────────────────────────
    const _rawName = asset.product_name || t('creativeOs.imageModal.imageFallback');
    const displayName = (() => {
        const words = _rawName.split(/\s+/);
        return words.length <= 4 ? _rawName : words.slice(0, 4).join(' ') + '…';
    })();
    const [title, setTitle] = useState(displayName);
    const [editingTitle, setEditingTitle] = useState(false);
    const [savingTitle, setSavingTitle] = useState(false);
    const titleInputRef = useRef<HTMLInputElement>(null);

    const handleSaveTitle = useCallback(async () => {
        const trimmed = title.trim();
        if (!trimmed || trimmed === displayName) {
            setTitle(displayName);
            setEditingTitle(false);
            return;
        }
        setSavingTitle(true);
        try {
            await creativeFetch(`/creative-os/projects/${projectId}/assets/images/${asset.id}`, {
                method: 'PATCH',
                body: JSON.stringify({ name: trimmed }),
            });
            asset.product_name = trimmed; // update local ref
            onGenerated?.(); // triggers gallery refresh
        } catch (err) {
            console.error('Rename failed:', err);
            setTitle(displayName); // revert on error
        } finally {
            setSavingTitle(false);
            setEditingTitle(false);
        }
    }, [title, displayName, projectId, asset, onGenerated]);

    useEffect(() => {
        if (editingTitle && titleInputRef.current) {
            titleInputRef.current.focus();
            titleInputRef.current.select();
        }
    }, [editingTitle]);

    const imageUrl = asset.image_url || asset.result_url || '';
    const createdAgo = asset.created_at
        ? (() => {
            const diff = Date.now() - new Date(asset.created_at).getTime();
            const hrs = Math.floor(diff / 3600000);
            if (hrs < 1) return t('creativeOs.imageModal.minutesAgo').replace('{n}', String(Math.floor(diff / 60000)));
            if (hrs < 24) return t('creativeOs.imageModal.hoursAgo').replace('{n}', String(hrs));
            const days = Math.floor(hrs / 24);
            if (days === 1) return t('creativeOs.imageModal.yesterday');
            return t('creativeOs.imageModal.daysAgo').replace('{n}', String(days));
        })()
        : '';

    const handleCopyPrompt = () => {
        navigator.clipboard.writeText(editPrompt);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    const handleAnimate = useCallback(async () => {
        setIsAnimating(true);
        try {
            await creativeFetch('/creative-os/animate/', {
                method: 'POST',
                body: JSON.stringify({
                    image_url: imageUrl,
                    style: selectedAnimStyle,
                    user_context: editPrompt || undefined,
                    duration: animDuration,
                    project_id: projectId,
                }),
            });
            // Switch to Videos tab and refresh
            onAnimated?.();
        } catch (err) {
            console.error('Animation failed:', err);
            const msg = err instanceof Error ? err.message : t('creativeOs.imageModal.unknownError');
            alert(t('creativeOs.imageModal.animationFailed').replace('{msg}', msg));
        } finally {
            setIsAnimating(false);
        }
    }, [editPrompt, selectedAnimStyle, animDuration, projectId, imageUrl, onAnimated, t]);

    // Extract influencer ID from the original shot metadata
    const influencerId = asset.influencer_id
        || (asset.analysis_json?.influencer_id as string | undefined)
        || undefined;

    const handleReGenerate = useCallback(async () => {
        if (!editPrompt.trim()) return;
        setGenerating(true);
        try {
            const origAspect = (asset.analysis_json?.aspect_ratio as string) || '9:16';
            const origQuality = (asset.analysis_json?.quality as string) || '4k';
            const origPrompt = asset.prompt || '';
            const isEdit = origPrompt && editPrompt.trim() !== origPrompt.trim();
            const promptPayload = isEdit
                ? `Edit the reference image as described below. Preserve all subjects, composition, style, lighting, color grade, aspect ratio, and framing from the reference image. Only change what is explicitly requested.\n\nEdit instruction: ${editPrompt}`
                : editPrompt;
            await creativeFetch('/creative-os/generate/image/execute', {
                method: 'POST',
                body: JSON.stringify({
                    prompt: promptPayload,
                    mode: (asset.analysis_json?.mode as string) || asset.shot_type || 'cinematic',
                    project_id: projectId,
                    product_id: asset.product_id,
                    influencer_id: influencerId,
                    reference_image_url: imageUrl || undefined,
                    aspect_ratio: origAspect,
                    quality: origQuality,
                    quick_action: true,
                }),
            });
            onGenerated?.();
            onClose();
        } catch (err) {
            console.error('Re-generation failed:', err);
            const msg = err instanceof Error ? err.message : t('creativeOs.imageModal.unknownError');
            alert(t('creativeOs.imageModal.generationFailed').replace('{msg}', msg));
        } finally {
            setGenerating(false);
        }
    }, [editPrompt, asset.analysis_json, asset.shot_type, asset.product_id, asset.prompt, influencerId, projectId, imageUrl, onGenerated, onClose, t]);

    const handleQuickAction = useCallback(async (action: typeof QUICK_ACTIONS[0]) => {
        setActionLoading(action.id);
        try {
            const enhancedPrompt = `${action.systemPrompt}\n\nOriginal prompt: ${editPrompt || 'Professional product photography'}`;
            await creativeFetch('/creative-os/generate/image/execute', {
                method: 'POST',
                body: JSON.stringify({
                    prompt: enhancedPrompt,
                    mode: (asset.analysis_json?.mode as string) || asset.shot_type || 'cinematic',
                    project_id: projectId,
                    product_id: asset.product_id,
                    influencer_id: influencerId,
                    reference_image_url: imageUrl || undefined,
                    aspect_ratio: '9:16',
                    quality: '4k',
                    quick_action: true,
                }),
            });
            onGenerated?.();
        } catch (err) {
            const label = t(action.labelKey);
            console.error(`${label} failed:`, err);
            const msg = err instanceof Error ? err.message : t('creativeOs.imageModal.unknownError');
            alert(t('creativeOs.imageModal.actionFailed').replace('{label}', label).replace('{msg}', msg));
        } finally {
            setActionLoading(null);
        }
    }, [editPrompt, asset.analysis_json, asset.shot_type, asset.product_id, influencerId, projectId, imageUrl, onGenerated, t]);

    const handleDownload = async () => {
        if (!imageUrl) return;
        try {
            const proxied = `/api/download-image?url=${encodeURIComponent(imageUrl)}`;
            const resp = await fetch(proxied);
            if (!resp.ok) throw new Error(`Download proxy returned ${resp.status}`);
            const blob = await resp.blob();
            const blobUrl = URL.createObjectURL(blob);
            // Detect extension from URL or content-type
            const contentType = resp.headers.get('content-type') || '';
            const urlExt = new URL(imageUrl).pathname.split('.').pop()?.toLowerCase();
            const validExts = ['png', 'jpg', 'jpeg', 'webp', 'gif'];
            let ext = validExts.includes(urlExt || '') ? urlExt! : 'png';
            if (ext === 'png' && contentType.includes('jpeg')) ext = 'jpg';
            if (ext === 'png' && contentType.includes('webp')) ext = 'webp';
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = `${asset.product_name || 'image'}_${asset.id?.slice(0, 8) || 'download'}.${ext}`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(blobUrl);
        } catch (err) {
            console.error('Download failed:', err);
            // Fallback: open in new tab
            window.open(imageUrl, '_blank');
        }
    };

    if (!mounted) return null;

    return createPortal(
        <>
            {/* Backdrop */}
            <div
                onClick={onClose}
                style={{
                    position: 'fixed',
                    inset: 0,
                    background: 'rgba(0,0,0,0.5)',
                    backdropFilter: 'blur(6px)',
                    zIndex: 9999,
                    animation: 'fadeIn 0.2s ease',
                }}
            />

            {/* Modal — wider, taller, image-dominant */}
            <div style={{
                position: 'fixed',
                top: '50%',
                left: '50%',
                transform: 'translate(-50%, -50%)',
                width: MODAL_WIDTH,
                maxWidth: MODAL_WIDTH,
                height: MODAL_HEIGHT,
                maxHeight: MODAL_HEIGHT,
                background: '#FFF',
                borderRadius: '20px',
                boxShadow: '0 32px 80px rgba(0,0,0,0.25)',
                zIndex: 10000,
                display: 'flex',
                overflow: 'hidden',
                animation: 'scaleIn 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
            }}>
                {/* ── Left: Image Preview ── */}
                <div style={{
                    flex: '0 0 44%',
                    background: '#0D1117',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    overflow: 'hidden',
                    position: 'relative',
                    padding: '16px',
                }}>
                    {imageUrl ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                            src={imageUrl}
                            alt=""
                            style={{
                                maxWidth: '100%',
                                maxHeight: '100%',
                                objectFit: 'contain',
                                display: 'block',
                                borderRadius: '12px',
                            }}
                        />
                    ) : (
                        <div style={{
                            width: '120px', height: '120px',
                            borderRadius: '50%',
                            background: 'linear-gradient(135deg, #C3D4F7, #D1C4F9)',
                        }} />
                    )}
                </div>

                {/* ── Right: Config Panel ─────────────────────── */}
                <div style={{
                    flex: '1 1 auto',
                    minWidth: '380px',
                    minHeight: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    position: 'relative',
                }}>
                    {/* ─ Top: Product info + Download/Publish links + close ─ */}
                    <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '20px 20px 16px',
                        borderBottom: '1px solid rgba(0,0,0,0.06)',
                        flexShrink: 0,
                    }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: 0 }}>
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
                                flexShrink: 0,
                            }}>
                                {title.charAt(0).toUpperCase()}
                            </div>
                            <div style={{ flex: 1, minWidth: 0, overflow: 'hidden' }}>
                                {editingTitle ? (
                                    <input
                                        ref={titleInputRef}
                                        value={title}
                                        onChange={e => setTitle(e.target.value)}
                                        onBlur={handleSaveTitle}
                                        onKeyDown={e => {
                                            if (e.key === 'Enter') handleSaveTitle();
                                            if (e.key === 'Escape') {
                                                setTitle(displayName);
                                                setEditingTitle(false);
                                            }
                                        }}
                                        disabled={savingTitle}
                                        style={{
                                            fontSize: '14px',
                                            fontWeight: 600,
                                            color: '#0D1B3E',
                                            lineHeight: 1.2,
                                            border: '1px solid rgba(51,122,255,0.3)',
                                            borderRadius: '6px',
                                            padding: '2px 6px',
                                            outline: 'none',
                                            width: '100%',
                                            background: 'rgba(51,122,255,0.04)',
                                            fontFamily: 'inherit',
                                            boxSizing: 'border-box',
                                        }}
                                    />
                                ) : (
                                    <div
                                        onClick={() => setEditingTitle(true)}
                                        style={{
                                            fontSize: '14px',
                                            fontWeight: 600,
                                            color: '#0D1B3E',
                                            lineHeight: 1.2,
                                            cursor: 'pointer',
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '6px',
                                        }}
                                        title={t('creativeOs.imageModal.clickRename')}
                                    >
                                        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{title}</span>
                                        <svg viewBox="0 0 24 24" style={{
                                            width: '12px', height: '12px',
                                            fill: 'none', stroke: '#8A93B0',
                                            strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round',
                                            opacity: 0.6, flexShrink: 0,
                                        }}>
                                            <path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
                                        </svg>
                                    </div>
                                )}
                                <div style={{ fontSize: '12px', color: '#8A93B0', marginTop: '1px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                    {createdAgo || t('creativeOs.imageModal.imageFallback')}
                                </div>
                            </div>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
                            <button
                                onClick={handleDownload}
                                style={{
                                    fontSize: '13px',
                                    fontWeight: 600,
                                    color: '#5A6178',
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '2px 0',
                                    transition: 'color 0.15s',
                                }}
                                onMouseEnter={e => (e.currentTarget.style.color = '#337AFF')}
                                onMouseLeave={e => (e.currentTarget.style.color = '#5A6178')}
                            >{t('creativeOs.imageModal.download')}</button>
                            <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
                                <button
                                    onClick={() => setShareOpen(v => !v)}
                                    style={{
                                        fontSize: '13px',
                                        fontWeight: 600,
                                        color: shareOpen ? '#337AFF' : '#5A6178',
                                        background: 'none',
                                        border: 'none',
                                        cursor: 'pointer',
                                        padding: '2px 0',
                                        transition: 'color 0.15s',
                                    }}
                                    onMouseEnter={e => { if (!shareOpen) e.currentTarget.style.color = '#337AFF'; }}
                                    onMouseLeave={e => { if (!shareOpen) e.currentTarget.style.color = '#5A6178'; }}
                                >{t('share.share')}</button>
                                {shareOpen && (
                                    <SharePopover
                                        url={imageUrl}
                                        assetType="image"
                                        onClose={() => setShareOpen(false)}
                                    />
                                )}
                            </div>
                            <button
                                onClick={() => alert(t('creativeOs.imageModal.publishComingSoon'))}
                                style={{
                                    fontSize: '13px',
                                    fontWeight: 600,
                                    color: '#5A6178',
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    padding: '2px 0',
                                    transition: 'color 0.15s',
                                }}
                                onMouseEnter={e => (e.currentTarget.style.color = '#337AFF')}
                                onMouseLeave={e => (e.currentTarget.style.color = '#5A6178')}
                            >{t('creativeOs.imageModal.publish')}</button>
                            <button
                                onClick={onClose}
                                style={{
                                    width: '30px',
                                    height: '30px',
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
                    </div>

                    {/* ─ Scrollable body (Prompt + Information) ─ */}
                    <div style={{
                        flex: 1,
                        minHeight: 0,
                        overflowY: 'auto',
                        padding: '16px 20px 0',
                    }}>
                    {/* ─ Prompt Section ─ */}
                    <div style={{ marginBottom: '20px' }}>
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            marginBottom: '8px',
                        }}>
                            <span style={{
                                fontSize: '11px',
                                fontWeight: 700,
                                color: '#8A93B0',
                                letterSpacing: '0.5px',
                                textTransform: 'uppercase',
                            }}>{t('creativeOs.imageModal.promptSection')}</span>
                            <button
                                onClick={handleCopyPrompt}
                                style={{
                                    fontSize: '12px',
                                    color: '#337AFF',
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    fontWeight: 600,
                                    padding: '2px 8px',
                                    borderRadius: '4px',
                                }}
                            >{copied ? t('creativeOs.imageModal.copied') : t('creativeOs.imageModal.copy')}</button>
                        </div>
                        <textarea
                            value={editPrompt}
                            onChange={e => setEditPrompt(e.target.value)}
                            placeholder={t('creativeOs.imageModal.promptTextPlaceholder')}
                            rows={8}
                            style={{
                                width: '100%',
                                padding: '12px 14px',
                                borderRadius: '10px',
                                border: '1px solid rgba(0,0,0,0.08)',
                                borderLeft: '3px solid #337AFF',
                                background: 'rgba(51,122,255,0.02)',
                                fontSize: '13px',
                                color: '#0D1B3E',
                                lineHeight: '1.6',
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
                            }}>{t('creativeOs.imageModal.rePromptHint')}</span>
                            <button
                                onClick={handleReGenerate}
                                disabled={generating || !editPrompt.trim()}
                                style={{
                                    padding: '7px 14px',
                                    borderRadius: '8px',
                                    border: '1px solid rgba(51,122,255,0.2)',
                                    background: 'rgba(51,122,255,0.06)',
                                    color: '#337AFF',
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    cursor: generating ? 'wait' : 'pointer',
                                    opacity: generating || !editPrompt.trim() ? 0.5 : 1,
                                    transition: 'all 0.15s',
                                    whiteSpace: 'nowrap',
                                    flexShrink: 0,
                                }}
                            >
                                {generating ? t('creativeOs.imageModal.generating') : t('creativeOs.imageModal.regenerate')}
                            </button>
                        </div>
                    </div>

                    {/* ─ Information Rows ─ */}
                    <div style={{ marginBottom: '16px' }}>
                        <span style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            color: '#8A93B0',
                            letterSpacing: '0.5px',
                            textTransform: 'uppercase',
                            display: 'block',
                            marginBottom: '8px',
                        }}>{t('creativeOs.imageModal.information')}</span>
                        <div style={{
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '0',
                        }}>
                            <InfoRow label={t('creativeOs.imageModal.labelMode')} value={(() => {
                                const m = (asset.analysis_json?.mode as string) || asset.shot_type || '';
                                const map: Record<string, string> = {
                                    iphone_look: t('creativeOs.imageModal.modeIphoneLook'),
                                    cinematic: t('creativeOs.imageModal.modeCinematic'),
                                    luxury: t('creativeOs.imageModal.modeLuxury'),
                                    ugc: t('creativeOs.imageModal.modeUgc'),
                                };
                                return map[m] || m.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()) || t('creativeOs.imageModal.modeStandard');
                            })()} highlight />
                            <InfoRow label={t('creativeOs.imageModal.labelQuality')} value={(asset.analysis_json?.quality as string || '4k').toUpperCase()} />
                            <InfoRow label={t('creativeOs.imageModal.labelAspect')} value={(asset.analysis_json?.aspect_ratio as string) || '9:16'} />
                            <InfoRow label={t('creativeOs.imageModal.labelCost')} value={t('creativeOs.imageModal.costCredits')} />
                            {createdAgo && <InfoRow label={t('creativeOs.imageModal.labelCreated')} value={createdAgo} />}
                        </div>
                    </div>

                    </div>
                    {/* ─ Pinned Footer (Create Video + Quick Actions) ─ */}
                    <div style={{
                        flexShrink: 0,
                        padding: '12px 20px 16px',
                        borderTop: '1px solid rgba(0,0,0,0.06)',
                        background: '#FFF',
                    }}>
                        {/* ─ Create Video CTA ─ */}
                        <button
                            onClick={() => {
                                onCreateVideo?.(asset);
                                onClose();
                            }}
                            style={{
                                width: '100%',
                                padding: '12px',
                                borderRadius: '12px',
                                border: 'none',
                                background: 'linear-gradient(135deg, #337AFF, #6C5CE7)',
                                color: 'white',
                                fontSize: '14px',
                                fontWeight: 700,
                                cursor: 'pointer',
                                transition: 'all 0.2s',
                                letterSpacing: '0.3px',
                                marginBottom: '12px',
                            }}
                        >
                            {t('creativeOs.imageModal.createVideo')}
                        </button>

                        {/* ─ Quick Actions ─ */}
                        <span style={{
                            fontSize: '11px', fontWeight: 700, color: '#8A93B0',
                            letterSpacing: '0.5px', textTransform: 'uppercase',
                            display: 'block', marginBottom: '8px',
                        }}>{t('creativeOs.imageModal.quickActions')}</span>
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: '1fr 1fr',
                            gap: '6px',
                        }}>
                            {QUICK_ACTIONS.map(action => (
                                <ActionButton
                                    key={action.id}
                                    label={actionLoading === action.id ? '...' : t(action.labelKey)}
                                    onClick={() => {
                                        if ((action as any).isAnimate) {
                                            setShowAnimateModal(true);
                                        } else {
                                            handleQuickAction(action);
                                        }
                                    }}
                                    disabled={actionLoading !== null && actionLoading !== action.id}
                                />
                            ))}
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Animate Style Selection Modal (12-Style Grid) ── */}
            {showAnimateModal && (
                <>
                    <div
                        onClick={() => setShowAnimateModal(false)}
                        style={{
                            position: 'fixed',
                            inset: 0,
                            background: 'rgba(0,0,0,0.4)',
                            zIndex: 10001,
                            animation: 'fadeIn 0.15s ease',
                        }}
                    />
                    <div style={{
                        position: 'fixed',
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        width: 'min(96vw, 880px)',
                        maxWidth: 'min(96vw, 880px)',
                        maxHeight: 'min(88vh, 760px)',
                        overflowY: 'auto',
                        background: '#FFF',
                        borderRadius: '20px',
                        padding: '28px',
                        boxShadow: '0 24px 60px rgba(0,0,0,0.25)',
                        zIndex: 10002,
                        animation: 'scaleIn 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    }}>
                        {/* Header */}
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            marginBottom: '16px',
                        }}>
                            <div>
                                <h3 style={{
                                    fontSize: '17px',
                                    fontWeight: 700,
                                    color: '#0D1B3E',
                                    margin: 0,
                                    letterSpacing: '-0.2px',
                                }}>{t('creativeOs.imageModal.chooseAnimationStyle')}</h3>
                                <span style={{
                                    fontSize: '12px',
                                    color: '#8A93B0',
                                    fontWeight: 500,
                                }}>{t('creativeOs.imageModal.poweredByKling')}</span>
                            </div>
                            <button
                                onClick={() => setShowAnimateModal(false)}
                                style={{
                                    width: '30px',
                                    height: '30px',
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

                        {/* 12-Style Grid (4 columns × 3 rows) */}
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: 'repeat(4, 1fr)',
                            gap: '14px',
                            marginBottom: '20px',
                        }}>
                            {ANIMATION_STYLES.map(style => {
                                const isSelected = selectedAnimStyle === style.id;
                                return (
                                    <button
                                        key={style.id}
                                        onClick={() => setSelectedAnimStyle(style.id)}
                                        style={{
                                            padding: '0',
                                            borderRadius: '14px',
                                            border: isSelected ? '2px solid #337AFF' : '1.5px solid rgba(0,0,0,0.08)',
                                            background: isSelected ? 'rgba(51,122,255,0.04)' : 'white',
                                            cursor: 'pointer',
                                            textAlign: 'center',
                                            transition: 'all 0.15s',
                                            overflow: 'hidden',
                                            display: 'flex',
                                            flexDirection: 'column',
                                        }}
                                    >
                                        <AnimationPreview style={style} />
                                        <div style={{
                                            padding: '10px 8px 12px',
                                        }}>
                                            <div style={{
                                                fontSize: '13px',
                                                fontWeight: 700,
                                                color: isSelected ? '#337AFF' : '#0D1B3E',
                                                marginBottom: '3px',
                                            }}>{t(style.labelKey)}</div>
                                            <div style={{
                                                fontSize: '11px',
                                                color: '#8A93B0',
                                                lineHeight: 1.3,
                                            }}>{t(style.descKey)}</div>
                                        </div>
                                    </button>
                                );
                            })}
                        </div>

                        {/* Duration Selector */}
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            marginBottom: '16px',
                            padding: '10px 14px',
                            borderRadius: '12px',
                            background: 'rgba(51,122,255,0.03)',
                            border: '1px solid rgba(51,122,255,0.08)',
                        }}>
                            <span style={{
                                fontSize: '12px',
                                fontWeight: 600,
                                color: '#4A5578',
                                marginRight: 'auto',
                            }}>{t('creativeOs.imageModal.durationLabel')}</span>
                            {[5, 10].map(d => (
                                <button
                                    key={d}
                                    onClick={() => setAnimDuration(d)}
                                    style={{
                                        padding: '5px 14px',
                                        borderRadius: '8px',
                                        border: animDuration === d ? '1.5px solid #337AFF' : '1px solid rgba(0,0,0,0.08)',
                                        background: animDuration === d ? 'rgba(51,122,255,0.08)' : 'white',
                                        color: animDuration === d ? '#337AFF' : '#4A5578',
                                        fontSize: '12px',
                                        fontWeight: 600,
                                        cursor: 'pointer',
                                        transition: 'all 0.15s',
                                    }}
                                >{t('creativeOs.imageModal.durationSeconds').replace('{n}', String(d))}</button>
                            ))}
                        </div>

                        {/* Selected style info + CTA */}
                        <div style={{
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            gap: '12px',
                        }}>
                            <span style={{
                                fontSize: '12px',
                                color: '#8A93B0',
                                fontWeight: 500,
                            }}>
                                {(() => {
                                    const sel = ANIMATION_STYLES.find(s => s.id === selectedAnimStyle);
                                    const label = sel ? t(sel.labelKey) : t('creativeOs.imageModal.styleSelect');
                                    return t('creativeOs.imageModal.styleSummary').replace('{label}', label).replace('{n}', String(animDuration));
                                })()}
                            </span>
                            <button
                                onClick={() => {
                                    setShowAnimateModal(false);
                                    handleAnimate();
                                }}
                                disabled={isAnimating}
                                style={{
                                    padding: '10px 24px',
                                    borderRadius: '12px',
                                    border: 'none',
                                    background: 'linear-gradient(135deg, #337AFF, #6C5CE7)',
                                    color: 'white',
                                    fontSize: '13px',
                                    fontWeight: 700,
                                    cursor: isAnimating ? 'wait' : 'pointer',
                                    opacity: isAnimating ? 0.7 : 1,
                                    transition: 'all 0.2s',
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                {isAnimating ? t('creativeOs.imageModal.animateGenerating') : t('creativeOs.imageModal.animate')}
                            </button>
                        </div>
                    </div>
                </>
            )}

            <style>{`
                @keyframes fadeIn {
                    from { opacity: 0; }
                    to { opacity: 1; }
                }
                @keyframes scaleIn {
                    from { opacity: 0; transform: translate(-50%, -50%) scale(0.95); }
                    to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
                }
            `}</style>
        </>,
        document.body
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

function ActionButton({ label, onClick, disabled }: { label: string; onClick: () => void; disabled?: boolean }) {
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            style={{
                padding: '9px 12px',
                borderRadius: '10px',
                border: '1px solid rgba(0,0,0,0.08)',
                background: 'white',
                color: '#5A6178',
                fontSize: '13px',
                fontWeight: 600,
                cursor: disabled ? 'wait' : 'pointer',
                transition: 'all 0.15s',
                opacity: disabled ? 0.5 : 1,
            }}
            onMouseEnter={e => { if (!disabled) e.currentTarget.style.background = 'rgba(51,122,255,0.04)'; }}
            onMouseLeave={e => (e.currentTarget.style.background = 'white')}
        >
            {label}
        </button>
    );
}

/* AnimateModeCard removed — replaced by inline 12-style grid */
