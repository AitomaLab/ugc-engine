'use client';

import { useState, useEffect, useCallback, useMemo } from 'react';
import VideoThumbnail from '@/components/ui/VideoThumbnail';
import { apiFetch } from '@/lib/utils';
import { creativeFetch } from '@/lib/creative-os-api';
import { useProgressiveList } from '@/hooks/useProgressiveList';
import { useTranslation } from '@/lib/i18n';
import type { VideoJob, Influencer, SocialConnection } from '@/lib/types';
import { MODAL_HEIGHT_SHORT } from '@/lib/modal-sizing';

/* ── Platform config ────────────────────────────────────────────────────── */
const PLATFORM_META: Record<string, { label: string; color: string; maxCaption: number }> = {
    instagram: { label: 'Instagram', color: '#E1306C', maxCaption: 2200 },
    tiktok:    { label: 'TikTok',    color: '#000000', maxCaption: 200 },
    youtube:   { label: 'YouTube',   color: '#FF0000', maxCaption: 500 },
    facebook:  { label: 'Facebook',  color: '#1877F2', maxCaption: 500 },
};

/* ── Per-video config shape ─────────────────────────────────────────────── */
interface VideoConfig {
    videoJobId: string;
    platforms: string[];
    caption: string;
    hashtags: string[];
    scheduledAt: string;
    useCustomTime: boolean;
    ready: boolean;
}

interface Props {
    isOpen: boolean;
    onClose: () => void;
    preSelectedIds?: Set<string>;
}

/* ── Helpers ─────────────────────────────────────────────────────────────── */
function toLocalDatetimeString(date: Date): string {
    const pad = (n: number) => n.toString().padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function toLocalDateString(d: Date) {
    return d.toLocaleDateString(undefined, { month: '2-digit', day: '2-digit', year: 'numeric' });
}

function toLocalTimeString(d: Date) {
    return d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' });
}

function formatShortDate(dateStr: string | null | undefined): string {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return `${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`;
}

/* ── Component ──────────────────────────────────────────────────────────── */
/* ── Project type for Step 1 ─────────────────────────────────────────── */
interface ProjectInfo {
    id: string;
    name: string;
    is_default?: boolean;
    created_at?: string;
    recent_previews?: { url: string; type: 'image' | 'video' }[];
    asset_counts?: { images?: number; videos?: number };
}

/* ── Unified asset type for Step 2 (videos + images) ─────────────────── */
interface ScheduleAsset {
    id: string;
    type: 'video' | 'image';
    url: string;  // final_video_url or image url
    previewUrl?: string;
    label: string;
    subLabel: string;
    created_at?: string;
}

export default function SchedulePostModal({ isOpen, onClose, preSelectedIds }: Props) {
    const { t } = useTranslation();
    const [step, setStep] = useState(1);

    // ── Step 1: Project selection ────────────────────────────────────
    const [projects, setProjects] = useState<ProjectInfo[]>([]);
    const [loadingProjects, setLoadingProjects] = useState(true);
    const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);

    // ── Step 2: Asset selection ──────────────────────────────────────
    const [assets, setAssets] = useState<ScheduleAsset[]>([]);
    const [loadingAssets, setLoadingAssets] = useState(false);
    const [assetFilter, setAssetFilter] = useState<'all' | 'video' | 'image'>('all');
    const [jobs, setJobs] = useState<VideoJob[]>([]);
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [connectedPlatforms, setConnectedPlatforms] = useState<string[]>([]);
    const [selectedIds, setSelectedIds] = useState<string[]>([]);
    const [configs, setConfigs] = useState<Record<string, VideoConfig>>({});
    const [activeVideoIdx, setActiveVideoIdx] = useState(0);
    const [globalDate, setGlobalDate] = useState(toLocalDatetimeString(new Date(Date.now() + 86400000)).split('T')[0]);
    const [globalTime, setGlobalTime] = useState('09:00');
    const [submitting, setSubmitting] = useState(false);
    const [aiLoading, setAiLoading] = useState(false);
    const [aiCaptions, setAiCaptions] = useState<string[]>([]);
    const [toast, setToast] = useState('');
    const [search, setSearch] = useState('');
    const [loadingData, setLoadingData] = useState(true);
    const [thumbMap, setThumbMap] = useState<Record<string, string>>({});

    // ── Step 1: Fetch projects ─────────────────────────────────────────
    useEffect(() => {
        if (!isOpen) return;
        setLoadingProjects(true);
        (async () => {
            try {
                const data = await creativeFetch<ProjectInfo[]>('/creative-os/projects/');
                setProjects(data || []);
            } catch (err) {
                console.error('[ScheduleModal] Failed to fetch projects:', err);
                setProjects([]);
            }
            setLoadingProjects(false);
        })();
        // Fetch connections separately (non-blocking)
        (async () => {
            try {
                const connData = await apiFetch<{ socials: SocialConnection[] }>('/api/connections');
                setConnectedPlatforms((connData?.socials || []).map(s => s.platform?.toLowerCase()).filter(Boolean) as string[]);
            } catch {
                setConnectedPlatforms([]);
            }
        })();
        // Fetch influencers for labels
        (async () => {
            try {
                const infData = await apiFetch<Influencer[]>('/influencers');
                setInfluencers(infData || []);
            } catch { /* non-critical */ }
        })();
    }, [isOpen]);

    // ── Step 2: Fetch assets when project is selected ─────────────────
    useEffect(() => {
        if (!selectedProjectId) return;
        setLoadingAssets(true);
        setAssets([]);
        setSelectedIds([]);
        setSearch('');
        (async () => {
            try {
                const [videos, images] = await Promise.all([
                    creativeFetch<any[]>(`/creative-os/projects/${selectedProjectId}/assets/videos`),
                    creativeFetch<any[]>(`/creative-os/projects/${selectedProjectId}/assets/images`),
                ]);
                const videoAssets: ScheduleAsset[] = (videos || []).filter((v: any) => v.status === 'success' && v.final_video_url).map((v: any) => ({
                    id: v.id,
                    type: 'video' as const,
                    url: v.final_video_url,
                    previewUrl: v.preview_url || v.reference_image_url || v.thumbnail_url,
                    label: v.campaign_name || 'Video',
                    subLabel: formatShortDate(v.created_at),
                    created_at: v.created_at,
                }));
                const imageAssets: ScheduleAsset[] = (images || []).map((img: any) => ({
                    id: img.id,
                    type: 'image' as const,
                    url: img.url || img.image_url,
                    previewUrl: img.url || img.image_url,
                    label: img.name || img.prompt?.slice(0, 40) || 'Image',
                    subLabel: formatShortDate(img.created_at),
                    created_at: img.created_at,
                }));
                const all = [...videoAssets, ...imageAssets].sort(
                    (a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime()
                );
                setAssets(all);
                // Also set jobs for compatibility with Step 3/4
                setJobs((videos || []).filter((v: any) => v.status === 'success' && v.final_video_url));
            } catch (err) {
                console.error('[ScheduleModal] Failed to fetch assets:', err);
                setAssets([]);
            }
            setLoadingAssets(false);
            setLoadingData(false);
        })();
    }, [selectedProjectId]);

    // ── generate thumbnails for videos without image previews ──────────
    useEffect(() => {
        const videoAssets = assets.filter(a => a.type === 'video');
        if (!videoAssets.length) return;
        const VIDEO_EXT_RE = /\.(mp4|webm|mov|avi|mkv)(\?.*)?$/i;
        // Find videos that don't have a usable image thumbnail
        const needsThumbnail = videoAssets.filter(a => {
            return !a.previewUrl || VIDEO_EXT_RE.test(a.previewUrl);
        });
        if (!needsThumbnail.length) return;
        // Call backend to generate FFmpeg thumbnails (non-blocking)
        (async () => {
            try {
                const result = await creativeFetch<{ thumbnails: Record<string, string> }>(
                    '/creative-os/projects/video-thumbnails',
                    {
                        method: 'POST',
                        body: JSON.stringify({
                            jobs: needsThumbnail.map(a => ({ id: a.id, video_url: a.url })),
                        }),
                    }
                );
                if (result?.thumbnails && Object.keys(result.thumbnails).length > 0) {
                    setThumbMap(prev => ({ ...prev, ...result.thumbnails }));
                }
            } catch (err) {
                console.error('[ScheduleModal] Thumbnail generation failed:', err);
            }
        })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [assets]);

    // ── pre-select from videos page ────────────────────────────────────
    useEffect(() => {
        if (preSelectedIds && preSelectedIds.size > 0 && assets.length > 0) {
            // Only include IDs that exist in the loaded assets
            const validIds = [...preSelectedIds].filter(id => assets.some(a => a.id === id));
            if (validIds.length > 0) setSelectedIds(validIds);
        }
    }, [preSelectedIds, assets]);

    // ── reset on close ─────────────────────────────────────────────────
    useEffect(() => {
        if (!isOpen) {
            setStep(1);
            setSelectedProjectId(null);
            setAssets([]);
            setAssetFilter('all');
            setSelectedIds([]);
            setConfigs({});
            setActiveVideoIdx(0);
            setAiCaptions([]);
            setSubmitting(false);
            setSearch('');
            setThumbMap({});
        }
    }, [isOpen]);

    const influencerMap = useMemo(() => new Map(influencers.map(i => [i.id, i])), [influencers]);

    const getJobLabel = useCallback((job: VideoJob): string => {
        const inf = influencerMap.get(job.influencer_id || '');
        const parts: string[] = [];
        if (job.campaign_name) parts.push(job.campaign_name);
        else if (inf?.name) parts.push(inf.name);
        return parts.join(' — ') || 'Video';
    }, [influencerMap]);

    const getJobSubLabel = useCallback((job: VideoJob): string => {
        const date = formatShortDate(job.created_at);
        return date || '';
    }, []);

    const getAssetLabel = useCallback((id: string): string => {
        const asset = assets.find(a => a.id === id);
        if (asset) return asset.label;
        const job = jobs.find(j => j.id === id);
        return job ? getJobLabel(job) : 'Asset';
    }, [assets, jobs, getJobLabel]);

    const getAssetSubLabel = useCallback((id: string): string => {
        const asset = assets.find(a => a.id === id);
        return asset?.subLabel || '';
    }, [assets]);

    // ── toggle video selection ──────────────────────────────────────────
    const toggleVideo = (id: string) => {
        setSelectedIds(prev => {
            if (prev.includes(id)) return prev.filter(x => x !== id);
            return [...prev, id];
        });
    };

    // ── select all / deselect all ───────────────────────────────────────
    const toggleAll = () => {
        if (selectedIds.length === filteredAssets.length) {
            setSelectedIds([]);
        } else {
            setSelectedIds(filteredAssets.map(a => a.id));
        }
    };

    // ── filter assets by search and type ─────────────────────────────────
    const filteredAssets = useMemo(() => {
        let filtered = assets;
        if (assetFilter !== 'all') {
            filtered = filtered.filter(a => a.type === assetFilter);
        }
        if (search) {
            const q = search.toLowerCase();
            filtered = filtered.filter(a =>
                a.label.toLowerCase().includes(q) ||
                a.id.toLowerCase().includes(q)
            );
        }
        return filtered;
    }, [assets, search, assetFilter]);

    // ── progressive loading for the asset grid ──────────────────────────
    const { visibleItems: visibleAssets, sentinelRef, hasMore, scrollContainerRef } = useProgressiveList(filteredAssets, 12);

    // Compat: keep filteredJobs for Step 3/4
    const filteredJobs = filteredAssets;

    // ── initialise configs when stepping from 1→2 ──────────────────────
    const initConfigs = useCallback(() => {
        const scheduleDate = `${globalDate}T${globalTime}`;
        const newConfigs: Record<string, VideoConfig> = {};
        selectedIds.forEach(id => {
            newConfigs[id] = configs[id] || {
                videoJobId: id,
                platforms: connectedPlatforms.length > 0 ? [connectedPlatforms[0]] : ['instagram'],
                caption: '',
                hashtags: [],
                scheduledAt: new Date(scheduleDate).toISOString(),
                useCustomTime: false,
                ready: false,
            };
        });
        setConfigs(newConfigs);
        setActiveVideoIdx(0);
    }, [selectedIds, globalDate, globalTime, configs, connectedPlatforms]);

    // ── update a specific video config ──────────────────────────────────
    const updateConfig = (id: string, patch: Partial<VideoConfig>) => {
        setConfigs(prev => {
            const updated = { ...prev[id], ...patch };
            updated.ready = updated.caption.trim().length > 0 && updated.platforms.length > 0;
            return { ...prev, [id]: updated };
        });
    };

    // ── toggle platform for a video ─────────────────────────────────────
    const togglePlatform = (videoId: string, platformId: string) => {
        const cfg = configs[videoId];
        if (!cfg) return;
        const next = cfg.platforms.includes(platformId)
            ? cfg.platforms.filter(p => p !== platformId)
            : [...cfg.platforms, platformId];
        updateConfig(videoId, { platforms: next });
    };

    // ── AI caption generation ───────────────────────────────────────────
    const generateCaption = async (assetId: string, platform: string) => {
        setAiLoading(true);
        setAiCaptions([]);
        try {
            const asset = assets.find(a => a.id === assetId);
            if (asset?.type === 'image') {
                // For images: generate captions via creative-os (which can handle arbitrary context)
                const data = await creativeFetch<{ captions: string[] }>('/creative-os/projects/generate-caption', {
                    method: 'POST',
                    body: JSON.stringify({
                        asset_type: 'image',
                        asset_label: asset.label,
                        asset_url: asset.url,
                        platform,
                    }),
                });
                setAiCaptions(data.captions || []);
            } else {
                // For videos: use existing endpoint
                const data = await apiFetch<{ captions: string[] }>('/api/schedule/generate-caption', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ video_job_id: assetId, platform }),
                });
                setAiCaptions(data.captions || []);
            }
        } catch (err) {
            console.error('[ScheduleModal] Caption generation failed:', err);
        }
        setAiLoading(false);
    };

    // ── submit ──────────────────────────────────────────────────────────
    const handleSubmit = async () => {
        setSubmitting(true);
        const scheduleDate = `${globalDate}T${globalTime}`;
        try {
            const posts = selectedIds.map(id => {
                const cfg = configs[id];
                return {
                    video_job_id: id,
                    platforms: cfg.platforms,
                    caption: cfg.caption,
                    hashtags: cfg.hashtags.length > 0 ? cfg.hashtags : undefined,
                    scheduled_at: cfg.useCustomTime ? cfg.scheduledAt : new Date(scheduleDate).toISOString(),
                };
            });
            await apiFetch('/api/schedule/bulk', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ posts }),
            });
            setToast(t('scheduleModal.successToast').replace('{count}', String(posts.length)));
            setTimeout(() => { setToast(''); onClose(); }, 2000);
        } catch {
            setToast(t('scheduleModal.failToast'));
            setTimeout(() => setToast(''), 3000);
        }
        setSubmitting(false);
    };

    if (!isOpen) return null;

    const activeVideoId = selectedIds[activeVideoIdx];
    const activeConfig = activeVideoId ? configs[activeVideoId] : null;
    const allReady = selectedIds.every(id => configs[id]?.ready);
    const selectedProject = projects.find(p => p.id === selectedProjectId);
    const STEPS = ['Select Project', 'Select Assets', t('scheduleModal.step2'), t('scheduleModal.step3')];
    const videoCount = assets.filter(a => a.type === 'video').length;
    const imageCount = assets.filter(a => a.type === 'image').length;

    /* ── RENDER ──────────────────────────────────────────────────────────── */
    return (
        <div style={{
            position: 'fixed', inset: 0, zIndex: 9999,
            background: 'rgba(0,0,0,0.45)', backdropFilter: 'blur(6px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
        }} onClick={onClose}>
            <div style={{
                background: '#fafbfd', borderRadius: '20px',
                width: 'min(94vw, 1100px)', maxWidth: 'min(94vw, 1100px)', height: MODAL_HEIGHT_SHORT, maxHeight: MODAL_HEIGHT_SHORT,
                display: 'flex', flexDirection: 'column', overflow: 'hidden',
                boxShadow: '0 24px 80px rgba(0,0,0,0.18)',
            }} onClick={e => e.stopPropagation()}>

                {/* ── Header ──────────────────────────────────────────── */}
                <div style={{
                    padding: '24px 32px 0', display: 'flex', alignItems: 'flex-start',
                    justifyContent: 'space-between',
                }}>
                    <div>
                        <h2 style={{ margin: 0, fontSize: '22px', fontWeight: 700 }}>{t('scheduleModal.title')}</h2>
                        <p style={{ margin: '4px 0 0', color: 'var(--text-3)', fontSize: '13px' }}>
                            {t('scheduleModal.subtitle')}
                        </p>
                    </div>
                    <button onClick={onClose} style={{
                        width: 32, height: 32, borderRadius: '50%', border: 'none',
                        background: 'var(--surface-hover)', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                    }}>
                        <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: 'var(--text-2)', fill: 'none', strokeWidth: 2 }}>
                            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                        </svg>
                    </button>
                </div>

                {/* ── Step Indicator ──────────────────────────────────── */}
                <div style={{
                    padding: '16px 32px 0', display: 'flex', alignItems: 'center',
                    gap: '0',
                }}>
                    {STEPS.map((label, i) => {
                        const num = i + 1;
                        const isActive = step === num;
                        const isDone = step > num;
                        return (
                            <div key={label} style={{ display: 'flex', alignItems: 'center', flex: i < STEPS.length - 1 ? 1 : 'none' }}>
                                <div style={{
                                    display: 'flex', alignItems: 'center', gap: '8px',
                                    cursor: isDone ? 'pointer' : 'default',
                                }} onClick={() => isDone && setStep(num)}>
                                    <div style={{
                                        width: 28, height: 28, borderRadius: '50%',
                                        background: isActive || isDone ? 'var(--blue)' : 'var(--border)',
                                        color: 'white', fontSize: '12px', fontWeight: 700,
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    }}>
                                        {isDone ? '✓' : num}
                                    </div>
                                    <span style={{
                                        fontSize: '13px', fontWeight: isActive ? 700 : 500,
                                        color: isActive ? 'var(--blue)' : isDone ? 'var(--text-2)' : 'var(--text-3)',
                                        whiteSpace: 'nowrap',
                                    }}>{label}</span>
                                </div>
                                {i < STEPS.length - 1 && (
                                    <div style={{
                                        flex: 1, height: '2px', margin: '0 12px',
                                        background: step > num ? 'var(--blue)' : 'var(--border)',
                                        borderRadius: '1px',
                                    }} />
                                )}
                            </div>
                        );
                    })}
                </div>

                <div style={{ height: '1px', background: 'var(--border)', margin: '16px 0 0' }} />

                {/* ── Body ─────────────────────────────────────────────── */}
                <div style={{ flex: 1, overflow: (step === 1 || step === 2) ? 'hidden' : 'auto', padding: '20px 32px 0', minHeight: 0, display: 'flex', flexDirection: 'column' }}>

                    {/* ════ STEP 1: Select Project ════ */}
                    {step === 1 && (
                        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0, paddingBottom: '12px' }}>
                            {loadingProjects ? (
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '60px 0', color: 'var(--text-3)', fontSize: '14px' }}>
                                    Loading projects...
                                </div>
                            ) : projects.length === 0 ? (
                                <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-3)' }}>
                                    <div style={{ fontSize: '14px', marginBottom: '8px' }}>No projects found</div>
                                    <div style={{ fontSize: '12px' }}>Create a project first to schedule assets</div>
                                </div>
                            ) : (
                                <div style={{
                                    display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
                                    gap: '16px',
                                }}>
                                    {projects.map(project => {
                                        const counts = project.asset_counts || {};
                                        const totalAssets = (counts.images || 0) + (counts.videos || 0);
                                        const previews = (project.recent_previews || []).filter((p: any) => p?.url).slice(0, 4);
                                        const isSelected = selectedProjectId === project.id;
                                        return (
                                            <div key={project.id}
                                                onClick={() => { setSelectedProjectId(project.id); setStep(2); }}
                                                style={{
                                                    borderRadius: '16px', overflow: 'hidden', cursor: 'pointer',
                                                    border: `2px solid ${isSelected ? 'var(--blue)' : 'transparent'}`,
                                                    background: 'white',
                                                    boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                                                    transition: 'all 0.2s ease',
                                                }}
                                                onMouseEnter={e => { e.currentTarget.style.boxShadow = '0 8px 32px rgba(51,122,255,0.12)'; e.currentTarget.style.transform = 'translateY(-2px)'; }}
                                                onMouseLeave={e => { e.currentTarget.style.boxShadow = '0 1px 4px rgba(0,0,0,0.06)'; e.currentTarget.style.transform = 'none'; }}
                                            >
                                                {/* Preview grid */}
                                                <div style={{ aspectRatio: '16 / 10', overflow: 'hidden', background: 'linear-gradient(135deg, #E3ECFF 0%, #D5DCFA 50%, #EDE3FA 100%)' }}>
                                                    {(() => {
                                                        const VIDEO_RE = /\.(mp4|webm|mov)(\?|#|$)/i;
                                                        const renderPreviewItem = (p: { url: string; type: 'image' | 'video' }, i: number) => {
                                                            const isVid = VIDEO_RE.test(p.url);
                                                            return isVid ? (
                                                                <video key={i} src={p.url} muted playsInline preload="metadata"
                                                                    style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                                                                    onError={e => { (e.target as HTMLVideoElement).style.display = 'none'; }}
                                                                />
                                                            ) : (
                                                                // eslint-disable-next-line @next/next/no-img-element
                                                                <img key={i} src={p.url} alt="" loading="lazy"
                                                                    style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                                                                    onError={e => { (e.target as HTMLImageElement).style.display = 'none'; }}
                                                                />
                                                            );
                                                        };
                                                        if (previews.length === 0) return (
                                                            <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                                                <svg viewBox="0 0 24 24" style={{ width: 36, height: 36, fill: 'none', stroke: 'rgba(51,122,255,0.25)', strokeWidth: 1.5 }}>
                                                                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                                                                </svg>
                                                            </div>
                                                        );
                                                        if (previews.length === 1) return (
                                                            <div style={{ width: '100%', height: '100%' }}>
                                                                {renderPreviewItem(previews[0], 0)}
                                                            </div>
                                                        );
                                                        return (
                                                            <div style={{ display: 'grid', gridTemplateColumns: previews.length >= 2 ? '1fr 1fr' : '1fr', gridTemplateRows: previews.length >= 3 ? '1fr 1fr' : '1fr', gap: '2px', height: '100%' }}>
                                                                {previews.map((p, i) => (
                                                                    <div key={i} style={{ overflow: 'hidden' }}>
                                                                        {renderPreviewItem(p, i)}
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        );
                                                    })()}
                                                </div>
                                                {/* Info */}
                                                <div style={{ padding: '12px 14px' }}>
                                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                        <div style={{ fontSize: '14px', fontWeight: 650, color: 'var(--text-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }}>
                                                            {project.name}
                                                        </div>
                                                        {project.is_default && (
                                                            <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--blue)', background: 'rgba(51,122,255,0.08)', padding: '2px 7px', borderRadius: '4px' }}>
                                                                Default
                                                            </span>
                                                        )}
                                                    </div>
                                                    <div style={{ fontSize: '12px', color: 'var(--text-3)', marginTop: '4px', display: 'flex', gap: '4px' }}>
                                                        {(counts.videos || 0) > 0 && <span>{counts.videos} video{(counts.videos || 0) !== 1 ? 's' : ''}</span>}
                                                        {(counts.videos || 0) > 0 && (counts.images || 0) > 0 && <span style={{ opacity: 0.5 }}>·</span>}
                                                        {(counts.images || 0) > 0 && <span>{counts.images} image{(counts.images || 0) !== 1 ? 's' : ''}</span>}
                                                        {totalAssets === 0 && <span>No assets</span>}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}

                    {/* ════ STEP 2: Select Assets ════ */}
                    {step === 2 && (
                        <div style={{ display: 'flex', gap: '24px', flex: 1, minHeight: 0, overflow: 'hidden' }}>
                            {/* Left: Asset grid — scrolls independently */}
                            <div ref={scrollContainerRef} style={{
                                flex: 1, display: 'flex', flexDirection: 'column', gap: '14px',
                                overflowY: 'auto', minHeight: 0, paddingBottom: '12px',
                            }}>
                                {/* Project name + filter tabs */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '2px' }}>
                                    <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-2)', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                        <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}>
                                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                                        </svg>
                                        {selectedProject?.name || 'Project'}
                                    </div>
                                    <div style={{ flex: 1 }} />
                                    {/* Type filter tabs */}
                                    {[
                                        { key: 'all' as const, label: `All (${assets.length})` },
                                        { key: 'video' as const, label: `Videos (${videoCount})` },
                                        { key: 'image' as const, label: `Images (${imageCount})` },
                                    ].map(tab => (
                                        <button key={tab.key} onClick={() => setAssetFilter(tab.key)} style={{
                                            padding: '5px 12px', borderRadius: '8px', border: 'none',
                                            background: assetFilter === tab.key ? 'var(--blue)' : 'rgba(0,0,0,0.04)',
                                            color: assetFilter === tab.key ? 'white' : 'var(--text-2)',
                                            fontSize: '12px', fontWeight: 600, cursor: 'pointer',
                                            transition: 'all 0.15s ease',
                                        }}>
                                            {tab.label}
                                        </button>
                                    ))}
                                </div>
                                {/* Search + Select All */}
                                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                    <div style={{
                                        flex: 1, display: 'flex', alignItems: 'center', gap: '8px',
                                        padding: '9px 14px', borderRadius: '10px',
                                        border: '1px solid var(--border)', background: 'white',
                                    }}>
                                        <svg viewBox="0 0 24 24" style={{ width: 16, height: 16, stroke: 'var(--text-3)', fill: 'none', strokeWidth: 2, flexShrink: 0 }}>
                                            <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
                                        </svg>
                                        <input
                                            type="text" placeholder="Search assets..."
                                            value={search} onChange={e => setSearch(e.target.value)}
                                            style={{ border: 'none', outline: 'none', fontSize: '13px', flex: 1, background: 'transparent', color: 'var(--text-1)' }}
                                        />
                                    </div>
                                    <button onClick={toggleAll} style={{
                                        padding: '9px 16px', borderRadius: '10px',
                                        border: '1px solid var(--border)', background: 'white',
                                        fontSize: '13px', fontWeight: 600, cursor: 'pointer',
                                        color: 'var(--text-1)', whiteSpace: 'nowrap',
                                    }}>
                                        {selectedIds.length === filteredAssets.length && filteredAssets.length > 0 ? t('scheduleModal.deselectAll') : t('scheduleModal.selectAllN')}
                                    </button>
                                </div>

                                {/* Grid — progressive loading */}
                                {loadingAssets ? (
                                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '60px 0', color: 'var(--text-3)', fontSize: '14px' }}>
                                        Loading assets...
                                    </div>
                                ) : filteredAssets.length === 0 ? (
                                    <div style={{ textAlign: 'center', padding: '60px 0', color: 'var(--text-3)' }}>
                                        <div style={{ fontSize: '14px', marginBottom: '8px' }}>No assets found</div>
                                        <div style={{ fontSize: '12px' }}>Generate some images or videos in this project first</div>
                                    </div>
                                ) : (
                                    <div style={{ paddingBottom: '8px' }}>
                                        <div style={{
                                            display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))',
                                            gap: '14px',
                                        }}>
                                            {visibleAssets.map(asset => {
                                                const idx = selectedIds.indexOf(asset.id);
                                                const isSelected = idx >= 0;
                                                const isVideo = asset.type === 'video';
                                                return (
                                                    <div key={asset.id} onClick={() => toggleVideo(asset.id)} style={{
                                                        borderRadius: '14px', overflow: 'hidden', cursor: 'pointer',
                                                        border: `2.5px solid ${isSelected ? 'var(--blue)' : 'transparent'}`,
                                                        background: 'white', transition: 'all 0.15s ease',
                                                        boxShadow: isSelected ? '0 0 0 3px rgba(51,122,255,0.12)' : '0 1px 4px rgba(0,0,0,0.06)',
                                                    }}>
                                                        {/* Thumbnail */}
                                                        <div style={{
                                                            position: 'relative', paddingTop: '125%',
                                                            background: 'linear-gradient(135deg, #f0f0f5 0%, #e8e8ee 100%)',
                                                        }}>
                                                            {asset.previewUrl ? (
                                                                <VideoThumbnail
                                                                    previewUrl={thumbMap[asset.id] || asset.previewUrl}
                                                                    videoUrl={isVideo ? asset.url : undefined}
                                                                    alt={asset.label}
                                                                />
                                                            ) : (
                                                                <VideoThumbnail
                                                                    previewUrl={thumbMap[asset.id]}
                                                                    videoUrl={isVideo ? asset.url : undefined}
                                                                    alt={asset.label}
                                                                />
                                                            )}
                                                            {/* Type badge */}
                                                            <div style={{
                                                                position: 'absolute', bottom: 6, left: 6,
                                                                padding: '2px 6px', borderRadius: '4px',
                                                                background: 'rgba(0,0,0,0.6)',
                                                                color: 'white', fontSize: '9px', fontWeight: 700,
                                                                backdropFilter: 'blur(4px)', letterSpacing: '0.3px',
                                                            }}>
                                                                {isVideo ? '▶ VIDEO' : '▢ IMAGE'}
                                                            </div>
                                                            {/* Selection badge */}
                                                            {isSelected && (
                                                                <div style={{
                                                                    position: 'absolute', top: 8, left: 8,
                                                                    width: 26, height: 26, borderRadius: '50%',
                                                                    background: 'var(--blue)', color: 'white',
                                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                                    fontSize: '11px', fontWeight: 700,
                                                                    boxShadow: '0 2px 8px rgba(51,122,255,0.3)',
                                                                }}>
                                                                    {idx + 1}
                                                                </div>
                                                            )}
                                                            {/* Checkmark */}
                                                            {isSelected && (
                                                                <div style={{
                                                                    position: 'absolute', top: 8, right: 8,
                                                                    width: 24, height: 24, borderRadius: '50%',
                                                                    background: 'var(--blue)', color: 'white',
                                                                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                                                                }}>
                                                                    <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, stroke: 'currentColor', fill: 'none', strokeWidth: 3 }}>
                                                                        <polyline points="20 6 9 17 4 12" />
                                                                    </svg>
                                                                </div>
                                                            )}
                                                        </div>
                                                        {/* Info */}
                                                        <div style={{ padding: '10px 12px' }}>
                                                            <div style={{
                                                                fontSize: '12px', fontWeight: 600, color: 'var(--text-1)',
                                                                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                                            }}>
                                                                {asset.label}
                                                            </div>
                                                            <div style={{
                                                                fontSize: '11px', color: 'var(--text-3)', marginTop: '2px',
                                                                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                                                            }}>
                                                                {asset.subLabel}
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                        {hasMore && (
                                            <div ref={sentinelRef} style={{ height: '1px', marginTop: '8px' }} />
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* Right sidebar — full height, posting time pinned at bottom */}
                            <div style={{
                                width: '260px', flexShrink: 0,
                                display: 'flex', flexDirection: 'column',
                                justifyContent: 'space-between',
                                minHeight: 0,
                            }}>
                                {/* Top section: selection count + selected list */}
                                <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0, flex: 1 }}>
                                    <div style={{ fontWeight: 700, fontSize: '14px', marginBottom: '4px' }}>
                                        {selectedIds.length} asset{selectedIds.length !== 1 ? 's' : ''} selected
                                    </div>
                                    <div style={{ fontSize: '12px', color: 'var(--text-3)', marginBottom: '12px' }}>
                                        {t('scheduleModal.willBeScheduled')}
                                    </div>

                                    {/* Scrollable selected video list */}
                                    {selectedIds.length > 0 && (
                                        <div style={{
                                            display: 'flex', flexDirection: 'column', gap: '6px',
                                            flex: 1, overflowY: 'auto', minHeight: 0,
                                            marginBottom: '12px', paddingRight: '4px',
                                        }}>
                                            {selectedIds.map((id) => {
                                                const asset = assets.find(a => a.id === id);
                                                if (!asset) return null;
                                                return (
                                                    <div key={id} style={{
                                                        display: 'flex', alignItems: 'center', gap: '10px',
                                                        padding: '8px 10px', borderRadius: '10px',
                                                        background: 'white', border: '1px solid var(--border)',
                                                        flexShrink: 0,
                                                    }}>
                                                        <div style={{
                                                            width: 28, height: 28, borderRadius: '8px',
                                                            background: asset.type === 'video' ? 'rgba(51,122,255,0.08)' : 'rgba(34,197,94,0.08)',
                                                            display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                                                        }}>
                                                            {asset.type === 'video' ? (
                                                                <svg viewBox="0 0 24 24" style={{ width: 12, height: 12, fill: 'var(--blue)', stroke: 'none' }}>
                                                                    <polygon points="5 3 19 12 5 21 5 3" />
                                                                </svg>
                                                            ) : (
                                                                <svg viewBox="0 0 24 24" style={{ width: 12, height: 12, fill: 'none', stroke: '#22c55e', strokeWidth: 2 }}>
                                                                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                                                                    <circle cx="8.5" cy="8.5" r="1.5" />
                                                                    <polyline points="21 15 16 10 5 21" />
                                                                </svg>
                                                            )}
                                                        </div>
                                                        <div style={{ flex: 1, overflow: 'hidden' }}>
                                                            <div style={{ fontSize: '12px', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                                                {asset.label}
                                                            </div>
                                                            <div style={{ fontSize: '10px', color: 'var(--text-3)' }}>
                                                                {asset.subLabel}
                                                            </div>
                                                        </div>
                                                        <button onClick={e => { e.stopPropagation(); toggleVideo(id); }} style={{
                                                            background: 'none', border: 'none', cursor: 'pointer',
                                                            color: 'var(--text-3)', fontSize: '16px', padding: '0 2px', lineHeight: 1,
                                                        }}>×</button>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    )}
                                </div>

                                {/* Global posting time — always pinned at bottom */}
                                <div style={{
                                    padding: '14px', borderRadius: '12px',
                                    background: 'rgba(51,122,255,0.04)', border: '1px solid rgba(51,122,255,0.15)',
                                    flexShrink: 0,
                                }}>
                                    <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--blue)', marginBottom: '4px' }}>
                                        {t('scheduleModal.globalTime')}
                                    </div>
                                    <div style={{ fontSize: '11px', color: 'var(--text-3)', marginBottom: '10px' }}>
                                        {selectedIds.length > 0
                                            ? t('scheduleModal.globalTimeApplied')
                                            : t('scheduleModal.globalTimeSelect')
                                        }
                                    </div>
                                    <div style={{ display: 'flex', gap: '8px' }}>
                                        <input type="date" value={globalDate}
                                            onChange={e => setGlobalDate(e.target.value)}
                                            style={{
                                                flex: 1, padding: '8px 10px', borderRadius: '8px',
                                                border: '1px solid var(--border)', fontSize: '13px',
                                                color: 'var(--text-1)', background: 'white',
                                            }}
                                        />
                                        <input type="time" value={globalTime}
                                            onChange={e => setGlobalTime(e.target.value)}
                                            style={{
                                                width: '100px', padding: '8px 10px', borderRadius: '8px',
                                                border: '1px solid var(--border)', fontSize: '13px',
                                                color: 'var(--text-1)', background: 'white',
                                            }}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* ════ STEP 3: Configure Each ════ */}
                    {step === 3 && activeConfig && (
                        <div style={{ display: 'flex', gap: '24px' }}>
                            {/* Left: video list */}
                            <div style={{ width: '220px', flexShrink: 0, display: 'flex', flexDirection: 'column', gap: '6px', maxHeight: '60vh', overflowY: 'auto' }}>
                                {selectedIds.map((id, i) => {
                                    const asset = assets.find(a => a.id === id);
                                    const cfg = configs[id];
                                    return (
                                        <div key={id} onClick={() => { setActiveVideoIdx(i); setAiCaptions([]); }} style={{
                                            padding: '10px 12px', borderRadius: '10px',
                                            background: i === activeVideoIdx ? 'rgba(51,122,255,0.08)' : 'white',
                                            border: `1px solid ${i === activeVideoIdx ? 'var(--blue)' : 'var(--border)'}`,
                                            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '10px',
                                        }}>
                                            <div style={{ width: 40, height: 52, borderRadius: '6px', overflow: 'hidden', background: '#f0f0f0', flexShrink: 0 }}>
                                                {(() => {
                                                    const src = thumbMap[id] || asset?.previewUrl;
                                                    if (!src) return null;
                                                    const isVid = /\.(mp4|webm|mov)(\?|#|$)/i.test(src);
                                                    return isVid ? (
                                                        <video src={src} muted playsInline preload="metadata"
                                                            style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                                                    ) : (
                                                        // eslint-disable-next-line @next/next/no-img-element
                                                        <img src={src} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }} />
                                                    );
                                                })()}
                                            </div>
                                            <div style={{ flex: 1, overflow: 'hidden' }}>
                                                <div style={{ fontSize: '12px', fontWeight: 600, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                    {asset?.label || 'Asset'}
                                                </div>
                                                <div style={{
                                                    fontSize: '10px', fontWeight: 600, marginTop: '4px',
                                                    color: cfg?.ready ? '#34C759' : '#FF9500',
                                                    display: 'flex', alignItems: 'center', gap: '4px',
                                                }}>
                                                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: cfg?.ready ? '#34C759' : '#FF9500' }} />
                                                    {cfg?.ready ? t('scheduleModal.ready') : t('scheduleModal.needsCaption')}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>

                            {/* Right: config form */}
                            <div style={{ flex: 1 }}>
                                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', marginBottom: '8px', display: 'block' }}>{t('scheduleModal.platforms')}</label>
                                <div style={{ display: 'flex', gap: '8px', marginBottom: '20px', flexWrap: 'wrap' }}>
                                    {Object.entries(PLATFORM_META).map(([pid, meta]) => {
                                        const on = activeConfig.platforms.includes(pid);
                                        const connected = connectedPlatforms.includes(pid);
                                        return (
                                            <button key={pid} disabled={!connected}
                                                onClick={() => togglePlatform(activeVideoId, pid)}
                                                style={{
                                                    padding: '8px 16px', borderRadius: '8px',
                                                    border: `1.5px solid ${on ? meta.color : 'var(--border)'}`,
                                                    background: on ? `${meta.color}12` : 'white',
                                                    color: on ? meta.color : connected ? 'var(--text-2)' : 'var(--text-3)',
                                                    fontSize: '13px', fontWeight: 600,
                                                    cursor: connected ? 'pointer' : 'not-allowed',
                                                    opacity: connected ? 1 : 0.4, transition: 'all 0.15s ease',
                                                }}
                                            >
                                                {meta.label}
                                            </button>
                                        );
                                    })}
                                </div>

                                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', marginBottom: '6px', display: 'block' }}>{t('scheduleModal.caption')}</label>
                                <div style={{ position: 'relative', marginBottom: '8px' }}>
                                    <textarea value={activeConfig.caption}
                                        onChange={e => updateConfig(activeVideoId, { caption: e.target.value })}
                                        placeholder={t('scheduleModal.captionPlaceholder')}
                                        rows={4}
                                        style={{
                                            width: '100%', padding: '12px', borderRadius: '10px',
                                            border: '1px solid var(--border)', fontSize: '13px',
                                            resize: 'vertical', fontFamily: 'inherit', color: 'var(--text-1)',
                                        }}
                                    />
                                    <div style={{ position: 'absolute', bottom: '10px', right: '12px', fontSize: '11px', color: 'var(--text-3)' }}>
                                        {activeConfig.caption.length} / {PLATFORM_META[activeConfig.platforms[0]]?.maxCaption ?? 2200}
                                    </div>
                                </div>

                                <button onClick={() => generateCaption(activeVideoId, activeConfig.platforms[0] ?? 'instagram')}
                                    disabled={aiLoading}
                                    style={{
                                        padding: '8px 16px', borderRadius: '8px', border: '1px solid var(--border)',
                                        background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                        color: 'white', fontSize: '12px', fontWeight: 600,
                                        cursor: aiLoading ? 'not-allowed' : 'pointer',
                                        display: 'flex', alignItems: 'center', gap: '6px',
                                        opacity: aiLoading ? 0.6 : 1, marginBottom: '12px',
                                    }}
                                >
                                    <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}>
                                        <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" />
                                    </svg>
                                    {aiLoading ? t('scheduleModal.generating') : t('scheduleModal.aiGenerate')}
                                </button>

                                {aiCaptions.length > 0 && (
                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginBottom: '20px' }}>
                                        {aiCaptions.map((c, i) => (
                                            <div key={i} onClick={() => { updateConfig(activeVideoId, { caption: c }); setAiCaptions([]); }}
                                                style={{
                                                    padding: '12px', borderRadius: '10px', cursor: 'pointer',
                                                    border: '1px solid var(--border)', background: 'var(--surface-hover)',
                                                    fontSize: '13px', color: 'var(--text-1)', transition: 'all 0.15s ease',
                                                }}
                                            >
                                                {c}
                                            </div>
                                        ))}
                                    </div>
                                )}

                                <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', marginBottom: '6px', display: 'block' }}>{t('scheduleModal.hashtags')}</label>
                                <input type="text" value={activeConfig.hashtags.join(' ')}
                                    onChange={e => updateConfig(activeVideoId, { hashtags: e.target.value.split(' ').filter(Boolean) })}
                                    placeholder="#ugc #ai #product"
                                    style={{
                                        width: '100%', padding: '10px 12px', borderRadius: '8px',
                                        border: '1px solid var(--border)', fontSize: '13px', color: 'var(--text-1)',
                                        marginBottom: '20px',
                                    }}
                                />

                                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '8px' }}>
                                    <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: '6px' }}>
                                        <input type="checkbox" checked={activeConfig.useCustomTime}
                                            onChange={e => updateConfig(activeVideoId, { useCustomTime: e.target.checked })}
                                            style={{ accentColor: 'var(--blue)' }} />
                                        {t('scheduleModal.customTime')}
                                    </label>
                                </div>
                                {activeConfig.useCustomTime && (
                                    <input type="datetime-local"
                                        value={toLocalDatetimeString(new Date(activeConfig.scheduledAt))}
                                        onChange={e => updateConfig(activeVideoId, { scheduledAt: new Date(e.target.value).toISOString() })}
                                        style={{
                                            width: '100%', padding: '8px 10px', borderRadius: '8px',
                                            border: '1px solid var(--border)', fontSize: '13px', color: 'var(--text-1)',
                                        }}
                                    />
                                )}
                            </div>
                        </div>
                    )}

                    {/* ════ STEP 4: Review & Schedule ════ */}
                    {step === 4 && (
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '16px' }}>
                            {selectedIds.map(id => {
                                const asset = assets.find(a => a.id === id);
                                const cfg = configs[id];
                                if (!cfg) return null;
                                return (
                                    <div key={id} style={{
                                        background: 'white', border: '1px solid var(--border)', borderRadius: '14px', overflow: 'hidden',
                                        display: 'flex', flexDirection: 'column',
                                    }}>
                                        {/* Preview */}
                                        <div style={{
                                            position: 'relative', paddingTop: '177.78%',
                                            background: 'linear-gradient(135deg, #f0f0f5 0%, #e8e8ee 100%)',
                                        }}>
                                            <VideoThumbnail
                                                previewUrl={asset ? (thumbMap[asset.id] || asset.previewUrl) : undefined}
                                                videoUrl={asset?.type === 'video' ? asset.url : undefined}
                                                alt={asset?.label || 'Asset'}
                                            />
                                        </div>
                                        {/* Card info */}
                                        <div style={{ padding: '12px 14px', flex: 1, display: 'flex', flexDirection: 'column' }}>
                                            <div style={{ fontWeight: 600, fontSize: '13px', marginBottom: '6px' }}>
                                                {asset?.label || 'Asset'}
                                            </div>
                                            <div style={{ display: 'flex', gap: '6px', marginBottom: '8px', flexWrap: 'wrap' }}>
                                                {cfg.platforms.map(p => (
                                                    <span key={p} style={{
                                                        fontSize: '10px', fontWeight: 700, padding: '3px 8px', borderRadius: '6px',
                                                        background: `${PLATFORM_META[p]?.color ?? '#666'}18`,
                                                        color: PLATFORM_META[p]?.color ?? '#666',
                                                    }}>
                                                        {PLATFORM_META[p]?.label ?? p}
                                                    </span>
                                                ))}
                                            </div>
                                            <div style={{ fontSize: '11px', color: 'var(--text-2)', marginBottom: '6px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                                <svg viewBox="0 0 24 24" style={{ width: 12, height: 12, stroke: 'currentColor', fill: 'none', strokeWidth: 2, flexShrink: 0 }}>
                                                    <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
                                                </svg>
                                                {new Date(cfg.useCustomTime ? cfg.scheduledAt : `${globalDate}T${globalTime}`).toLocaleString()}
                                            </div>
                                            <div style={{
                                                fontSize: '11px', color: 'var(--text-3)', overflow: 'hidden', textOverflow: 'ellipsis',
                                                display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical',
                                                flex: 1,
                                            }}>
                                                {cfg.caption || t('scheduleModal.noCaption')}
                                            </div>
                                            <button onClick={() => { setActiveVideoIdx(selectedIds.indexOf(id)); setStep(3); }}
                                                style={{
                                                    marginTop: '10px', width: '100%', padding: '6px 0', borderRadius: '8px',
                                                    border: '1px solid var(--border)', background: 'transparent',
                                                    color: 'var(--blue)', fontSize: '12px', fontWeight: 600, cursor: 'pointer',
                                                }}>
                                                {t('scheduleModal.edit')}
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    )}
                </div>

                {/* ── Footer ───────────────────────────────────────────── */}
                <div style={{
                    padding: '16px 32px', borderTop: '1px solid var(--border)',
                    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                }}>
                    <div style={{ fontSize: '13px', color: 'var(--blue)', fontWeight: 600 }}>
                        {step === 1 && `${projects.length} project${projects.length !== 1 ? 's' : ''}`}
                        {step === 2 && selectedIds.length > 0 && `${selectedIds.length} asset${selectedIds.length !== 1 ? 's' : ''} selected`}
                        {step === 3 && t('scheduleModal.videoOf').replace('{current}', String(activeVideoIdx + 1)).replace('{total}', String(selectedIds.length))}
                    </div>
                    <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
                        {step > 1 && (
                            <button onClick={() => setStep(s => s - 1)} style={{
                                padding: '10px 20px', borderRadius: '10px',
                                border: '1px solid var(--border)', background: 'white',
                                color: 'var(--text-2)', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
                            }}>
                                {t('scheduleModal.back')}
                            </button>
                        )}
                        {step === 1 && (
                            <button onClick={onClose} style={{
                                padding: '10px 20px', borderRadius: '10px',
                                border: '1px solid var(--border)', background: 'white',
                                color: 'var(--text-2)', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
                            }}>
                                {t('common.cancel')}
                            </button>
                        )}
                        {step === 2 && (
                            <button disabled={selectedIds.length === 0}
                                onClick={() => { initConfigs(); setStep(3); }}
                                style={{
                                    padding: '10px 24px', borderRadius: '10px', border: 'none',
                                    background: selectedIds.length > 0 ? 'var(--blue)' : 'var(--border)',
                                    color: 'white', fontSize: '13px', fontWeight: 600,
                                    cursor: selectedIds.length > 0 ? 'pointer' : 'not-allowed',
                                    display: 'flex', alignItems: 'center', gap: '6px',
                                }}>
                                {t('scheduleModal.nextConfigure')}
                                <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, stroke: 'currentColor', fill: 'none', strokeWidth: 2 }}>
                                    <polyline points="9 18 15 12 9 6" />
                                </svg>
                            </button>
                        )}
                        {step === 3 && (
                            <button disabled={!allReady} onClick={() => setStep(4)}
                                style={{
                                    padding: '10px 24px', borderRadius: '10px', border: 'none',
                                    background: allReady ? 'var(--blue)' : 'var(--border)',
                                    color: 'white', fontSize: '13px', fontWeight: 600,
                                    cursor: allReady ? 'pointer' : 'not-allowed',
                                }}>
                                {t('scheduleModal.nextReview')}
                            </button>
                        )}
                        {step === 4 && (
                            <button disabled={submitting} onClick={handleSubmit}
                                style={{
                                    padding: '12px 28px', borderRadius: '10px', border: 'none',
                                    background: submitting ? 'var(--border)' : 'var(--blue)',
                                    color: 'white', fontSize: '14px', fontWeight: 700,
                                    cursor: submitting ? 'not-allowed' : 'pointer',
                                    display: 'flex', alignItems: 'center', gap: '8px',
                                }}>
                                {submitting ? t('scheduleModal.scheduling') : `${t('scheduleModal.confirmSchedule')} ${selectedIds.length} ${t('scheduleModal.posts')}`}
                            </button>
                        )}
                    </div>
                </div>

                {/* Toast notification */}
                {toast && (
                    <div style={{
                        position: 'fixed', bottom: '32px', left: '50%', transform: 'translateX(-50%)',
                        background: toast.includes('Failed') ? '#FF3B30' : '#34C759',
                        color: 'white', padding: '12px 24px', borderRadius: '12px',
                        fontWeight: 600, fontSize: '14px',
                        boxShadow: '0 8px 32px rgba(0,0,0,0.15)', zIndex: 10000,
                    }}>
                        {toast}
                    </div>
                )}
            </div>
        </div>
    );
}
