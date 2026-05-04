'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useParams, usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useApp } from '@/providers/AppProvider';
import { creativeFetch } from '@/lib/creative-os-api';
import { useTranslation } from '@/lib/i18n';
import { AssetGallery } from '@/components/studio/AssetGallery';
import { CreateBar } from '@/components/studio/CreateBar';
import dynamic from 'next/dynamic';
import type { AgentPanelHandle, AgentPanelState } from '@/components/studio/AgentPanel';

const AgentPanel = dynamic(
    () => import('@/components/studio/AgentPanel').then(m => m.AgentPanel),
    {
        ssr: false,
        loading: () => (
            <div style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-3)', fontSize: 13 }}>
                Loading agent…
            </div>
        ),
    }
);
import Select from '@/components/ui/Select';

type TabId = 'images' | 'videos';

/* ── Mode label helper (mirrors VideoDetailModal) ─────────────── */
function modeLabel(api?: string): string {
    if (!api) return '';
    const map: Record<string, string> = {
        kling: 'UGC', kie: 'UGC', wavespeed: 'UGC',
        veo: 'Cinematic', cinematic: 'Cinematic',
    };
    const lower = api.toLowerCase();
    for (const [key, label] of Object.entries(map)) {
        if (lower.includes(key)) return label;
    }
    return '';
}

/* ── Responsive hook: split layout only on >=1024px viewports ─── */
function useIsWide(): boolean {
    const [isWide, setIsWide] = useState<boolean>(() => {
        if (typeof window === 'undefined') return true; // SSR: assume desktop
        return window.matchMedia('(min-width: 1024px)').matches;
    });
    useEffect(() => {
        if (typeof window === 'undefined') return;
        const mq = window.matchMedia('(min-width: 1024px)');
        const onChange = (e: MediaQueryListEvent) => setIsWide(e.matches);
        // matchMedia listeners use addEventListener in modern browsers.
        mq.addEventListener('change', onChange);
        return () => mq.removeEventListener('change', onChange);
    }, []);
    return isWide;
}


/* ── Main Page Component ─────────────────────────────────────── */

export default function ProjectContainerPage() {
    const { t } = useTranslation();
    const params = useParams();
    const searchParams = useSearchParams();
    const pathname = usePathname();
    const router = useRouter();
    const projectId = params.id as string;
    // Capture the auto-submit params ONCE at mount. We immediately strip them
    // from the URL so a browser refresh doesn't re-trigger the initial
    // message send.
    const initialParamsRef = useRef<{ brief: string | null; refs: any; seedance: boolean } | null>(null);
    if (initialParamsRef.current === null) {
        const refsParamRaw = searchParams.get('refs');
        let parsedRefs: any = undefined;
        if (refsParamRaw) {
            try { parsedRefs = JSON.parse(refsParamRaw); } catch { parsedRefs = undefined; }
        }
        initialParamsRef.current = {
            brief: searchParams.get('brief'),
            refs: parsedRefs,
            seedance: searchParams.get('seedance') === '1',
        };
    }
    const initialBrief = initialParamsRef.current.brief;
    const initialRefs = initialParamsRef.current.refs;
    const initialUseSeedance = initialParamsRef.current.seedance;

    useEffect(() => {
        if (!pathname) return;
        const hasAutoSubmitParams =
            searchParams.get('brief') || searchParams.get('refs') || searchParams.get('seedance');
        if (hasAutoSubmitParams) {
            router.replace(pathname, { scroll: false });
        }
        // Only run once on mount — we want the cleanup to happen exactly once.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);
    const { session } = useApp();

    const [activeTab, setActiveTab] = useState<TabId>('images');
    const [projectName, setProjectName] = useState('');
    const [isEditing, setIsEditing] = useState(false);
    const [editName, setEditName] = useState('');
    const [images, setImages] = useState<any[]>([]);
    const [videos, setVideos] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [createVideoImage, setCreateVideoImage] = useState<any>(null);
    const pollRef = useRef<NodeJS.Timeout | null>(null);
    const burstRef = useRef<NodeJS.Timeout | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // ── Filter state ──
    const [filterProduct, setFilterProduct] = useState('');
    const [filterInfluencer, setFilterInfluencer] = useState('');
    const [filterMode, setFilterMode] = useState('');

    // Most recent completed video in this project — used as the jobId the
    // agent panel can edit via the Phase 2 editor-AI route. When null, the
    // agent panel falls back to the managed-agent stream for all prompts.
    const selectedJobId = useMemo<string | null>(() => {
        const completed = videos.find((v) => {
            const s = (v?.status || '').toString().toLowerCase();
            return s === 'success' || s === 'complete' || s === 'completed' || s === 'done';
        });
        return completed?.id ? String(completed.id) : null;
    }, [videos]);

    // ── Agent panel visibility (split-panel layout only) ──
    const [agentOpen, setAgentOpen] = useState(true);
    const [createBarOpen, setCreateBarOpen] = useState(true);
    const agentRef = useRef<AgentPanelHandle>(null);
    // Sync agent panel state to power reactive header elements
    const [agentState, setAgentState] = useState<AgentPanelState>({ useSeedance: false, running: false, turnsCount: 0 });

    const fetchAssets = useCallback(async (silent = false) => {
        if (!session || !projectId) return;
        if (!silent) setLoading(true);
        try {
            const [project, imgs, vids] = await Promise.all([
                creativeFetch<any>(`/creative-os/projects/${projectId}`),
                creativeFetch<any[]>(`/creative-os/projects/${projectId}/assets/images`),
                creativeFetch<any[]>(`/creative-os/projects/${projectId}/assets/videos`),
            ]);
            setProjectName(project.name || 'Project');
            setImages(imgs);
            setVideos(vids);
        } catch (err) {
            console.error('Failed to fetch assets:', err);
        } finally {
            if (!silent) setLoading(false);
        }
    }, [session, projectId]);

    // Initial fetch
    useEffect(() => {
        fetchAssets();
    }, [fetchAssets]);

    // Short-term aggressive refetch when an agent-launched job starts.
    // The backend may take 1–8s to insert the "processing" shot/job row
    // (influencer resolution, reference-image prep, product lookups),
    // so we poll every 1.5s for up to 20s to catch it as soon as it lands.
    // Once a pending row is in state, the 5s auto-poll below takes over.
    const startJobRefetchBurst = useCallback(() => {
        if (burstRef.current) clearInterval(burstRef.current);
        const startedAt = Date.now();
        const tick = () => { fetchAssets(true); };
        tick();
        burstRef.current = setInterval(() => {
            if (Date.now() - startedAt > 20000) {
                if (burstRef.current) clearInterval(burstRef.current);
                burstRef.current = null;
                return;
            }
            tick();
        }, 1500);
    }, [fetchAssets]);

    // Stop the burst early once any pending row appears — auto-poll takes over.
    useEffect(() => {
        if (!burstRef.current) return;
        const hasPending = [...images, ...videos].some(a => {
            const s = (a.status || '').toLowerCase();
            return s.includes('pending') || s.includes('processing') || s.includes('generating');
        });
        if (hasPending) {
            clearInterval(burstRef.current);
            burstRef.current = null;
        }
    }, [images, videos]);

    useEffect(() => () => {
        if (burstRef.current) clearInterval(burstRef.current);
    }, []);

    // Auto-poll: check for pending/processing assets every 5s.
    // Pauses while the tab is hidden to avoid burning cycles for users
    // who switched away, and fires an immediate refetch when they return.
    useEffect(() => {
        const hasPending = [
            ...images,
            ...videos,
        ].some(a => {
            const s = (a.status || '').toLowerCase();
            return s.includes('pending') || s.includes('processing') || s.includes('generating');
        });

        if (hasPending) {
            pollRef.current = setInterval(() => {
                if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
                fetchAssets(true);
            }, 5000);
            const onVisible = () => {
                if (document.visibilityState === 'visible') fetchAssets(true);
            };
            document.addEventListener('visibilitychange', onVisible);
            return () => {
                if (pollRef.current) clearInterval(pollRef.current);
                pollRef.current = null;
                document.removeEventListener('visibilitychange', onVisible);
            };
        }

        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = null;
        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, [images, videos, fetchAssets]);

    // Reset filters when switching tabs
    useEffect(() => {
        setFilterProduct('');
        setFilterInfluencer('');
        setFilterMode('');
    }, [activeTab]);

    // ── Derive unique filter values from current tab assets ──
    const currentAssets = activeTab === 'images' ? images : videos;

    const productOptions = useMemo(() => {
        const names = new Set<string>();
        currentAssets.forEach(a => {
            const n = a.product_name;
            if (n) names.add(n);
        });
        return Array.from(names).sort();
    }, [currentAssets]);

    const influencerOptions = useMemo(() => {
        const names = new Set<string>();
        currentAssets.forEach(a => {
            // Backend now enriches influencer_name from influencer_id lookup
            const n = a.influencer_name;
            if (n) names.add(n);
        });
        return Array.from(names).sort();
    }, [currentAssets]);

    const modeOptions = useMemo(() => {
        const modes = new Set<string>();
        currentAssets.forEach(a => {
            // Backend now enriches mode from shot_type (images) or model_api (videos)
            const m = a.mode || modeLabel(a.model_api);
            if (m) modes.add(m);
        });
        return Array.from(modes).sort();
    }, [currentAssets]);

    // ── Apply filters ──
    const filteredAssets = useMemo(() => {
        let result = currentAssets;
        if (filterProduct) {
            result = result.filter(a => a.product_name === filterProduct);
        }
        if (filterInfluencer) {
            result = result.filter(a => a.influencer_name === filterInfluencer);
        }
        if (filterMode) {
            result = result.filter(a =>
                (a.mode || modeLabel(a.model_api)) === filterMode
            );
        }
        return result;
    }, [currentAssets, filterProduct, filterInfluencer, filterMode]);

    const hasActiveFilters = !!(filterProduct || filterInfluencer || filterMode);

    const startEditing = () => {
        setEditName(projectName);
        setIsEditing(true);
        setTimeout(() => inputRef.current?.focus(), 50);
    };

    const saveRename = async () => {
        const name = editName.trim();
        if (!name || name === projectName) {
            setIsEditing(false);
            return;
        }
        try {
            await creativeFetch(`/creative-os/projects/${projectId}`, {
                method: 'PUT',
                body: JSON.stringify({ name }),
            });
            setProjectName(name);
        } catch (err) {
            console.error('Rename failed:', err);
        }
        setIsEditing(false);
    };

    const isWide = useIsWide();

    /* ── Unified Project Header Bar (always visible) ─────── */
    const projectHeaderBar = (
        <div style={{
            display: 'flex',
            borderBottom: '1px solid rgba(13,27,62,0.06)',
            background: '#FFFFFF',
            flexShrink: 0,
            flexWrap: isWide ? 'nowrap' : 'wrap',
            overflow: 'hidden',
        }}>
            {/* Left Header Box (Agent Panel) */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '16px',
                padding: '16px 28px',
                ...(isWide && agentOpen ? {
                    width: '38%',
                    minWidth: '360px',
                    maxWidth: '520px',
                    borderRight: '1px solid rgba(13,27,62,0.07)',
                } : {}),
                minWidth: 0,
                overflow: 'hidden',
            }}>
            {/* Project Title */}
            {isEditing ? (
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <input
                        ref={inputRef}
                        value={editName}
                        onChange={e => setEditName(e.target.value)}
                        onKeyDown={e => {
                            if (e.key === 'Enter') saveRename();
                            if (e.key === 'Escape') setIsEditing(false);
                        }}
                        onBlur={saveRename}
                        style={{
                            fontSize: '20px',
                            fontWeight: 700,
                            color: '#0D1B3E',
                            letterSpacing: '-0.3px',
                            border: '1.5px solid #337AFF',
                            borderRadius: '8px',
                            padding: '4px 10px',
                            outline: 'none',
                            background: 'rgba(51,122,255,0.03)',
                            fontFamily: 'inherit',
                            minWidth: '160px',
                        }}
                    />
                </div>
            ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', minWidth: 0, flexShrink: 1 }}>
                    <h1 style={{
                        fontSize: '20px',
                        fontWeight: 700,
                        color: '#0D1B3E',
                        margin: 0,
                        letterSpacing: '-0.3px',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                    }}>
                        {projectName}
                    </h1>
                    <button
                        onClick={startEditing}
                        title="Rename project"
                        style={{
                            width: '26px', height: '26px', borderRadius: '6px', border: 'none',
                            background: 'transparent', cursor: 'pointer', display: 'flex',
                            alignItems: 'center', justifyContent: 'center', transition: 'background 0.15s',
                            flexShrink: 0,
                        }}
                        onMouseEnter={e => (e.currentTarget.style.background = 'rgba(51,122,255,0.08)')}
                        onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}
                    >
                        <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: '#8A93B0', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                            <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
                        </svg>
                    </button>
                </div>
            )}

            {/* Spacer to right-align controls when agent panel is open */}
            {isWide && agentOpen && <div style={{ flex: 1 }} />}




            {/* Clear Chat (only when agent panel is open) */}
            {isWide && agentOpen && (
                <button
                    onClick={() => agentRef.current?.reset()}
                    title={t('creativeOs.project.clearChat')}
                    disabled={agentState.running || agentState.turnsCount === 0}
                    style={{
                        width: '26px', height: '26px', borderRadius: '6px', border: 'none',
                        background: 'transparent',
                        cursor: (agentState.running || agentState.turnsCount === 0) ? 'not-allowed' : 'pointer',
                        color: '#8A93B0', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        opacity: (agentState.running || agentState.turnsCount === 0) ? 0.4 : 1,
                        transition: 'all 0.15s', flexShrink: 0,
                    }}
                >
                    {/* Refresh/reset icon instead of trash */}
                    <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                        <polyline points="1 4 1 10 7 10" />
                        <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
                    </svg>
                </button>
            )}

            {/* Agent Panel Toggle */}
            {isWide && (
                <button
                    onClick={() => setAgentOpen(!agentOpen)}
                    title={agentOpen ? t('creativeOs.project.agentPanelHide') : t('creativeOs.project.agentPanelShow')}
                    style={{
                        width: '26px', height: '26px', borderRadius: '6px', border: 'none',
                        background: agentOpen ? 'rgba(51,122,255,0.08)' : 'transparent',
                        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        transition: 'all 0.15s', color: agentOpen ? '#337AFF' : '#8A93B0', flexShrink: 0,
                    }}
                    onMouseEnter={e => { if (!agentOpen) e.currentTarget.style.background = 'rgba(51,122,255,0.08)'; }}
                    onMouseLeave={e => { if (!agentOpen) e.currentTarget.style.background = 'transparent'; }}
                >
                    <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                        <rect x="3" y="4" width="18" height="16" rx="2" />
                        <line x1="9" y1="4" x2="9" y2="20" />
                    </svg>
                </button>
            )}

            {/* Create Bar Toggle */}
            {isWide && (
                <button
                    onClick={() => setCreateBarOpen(!createBarOpen)}
                    title={createBarOpen ? t('creativeOs.project.bottomPanelHide') : t('creativeOs.project.bottomPanelShow')}
                    style={{
                        width: '26px', height: '26px', borderRadius: '6px', border: 'none',
                        background: createBarOpen ? 'rgba(51,122,255,0.08)' : 'transparent',
                        cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center',
                        transition: 'all 0.15s', color: createBarOpen ? '#337AFF' : '#8A93B0', flexShrink: 0,
                    }}
                    onMouseEnter={e => { if (!createBarOpen) e.currentTarget.style.background = 'rgba(51,122,255,0.08)'; }}
                    onMouseLeave={e => { if (!createBarOpen) e.currentTarget.style.background = 'transparent'; }}
                >
                    <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                        <rect x="3" y="4" width="18" height="16" rx="2" />
                        <line x1="3" y1="15" x2="21" y2="15" />
                    </svg>
                </button>
            )}
            </div>

            {/* Right section: Tabs and filters (Gallery column header) */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '12px',
                padding: '16px 28px',
                flex: 1,
                flexWrap: 'wrap',
                minWidth: 0,
            }}>
            {/* Tab Switcher */}
            <div style={{
                display: 'flex', gap: '4px', padding: '3px',
                borderRadius: '10px', background: 'rgba(51,122,255,0.06)',
                flexShrink: 0,
            }}>
                {(['images', 'videos'] as TabId[]).map(tab => (
                    <button
                        key={tab}
                        onClick={() => setActiveTab(tab)}
                        style={{
                            padding: '6px 16px', borderRadius: '7px', border: 'none',
                            cursor: 'pointer', fontSize: '13px', fontWeight: 600,
                            transition: 'all 0.2s ease',
                            background: activeTab === tab ? 'white' : 'transparent',
                            color: activeTab === tab ? '#337AFF' : '#8A93B0',
                            boxShadow: activeTab === tab ? '0 1px 4px rgba(51,122,255,0.12)' : 'none',
                        }}
                    >
                        {tab === 'images' ? t('creativeOs.project.tabImages') : t('creativeOs.project.tabVideos')}
                        <span style={{ marginLeft: '5px', fontSize: '11px', opacity: 0.6 }}>
                            {tab === 'images' ? images.length : videos.length}
                        </span>
                    </button>
                ))}
            </div>

            {/* Filter Divider */}
            <div style={{ width: '1px', height: '24px', background: 'rgba(0,0,0,0.08)', flexShrink: 0 }} />

            {/* Filters */}
            <Select className="filter-select" value={filterProduct} onChange={setFilterProduct} placeholder={t('creativeOs.project.filterProduct')} style={{ width: '150px', flexShrink: 0 }}
                options={[{ value: '', label: t('creativeOs.project.filterAllProducts') }, ...productOptions.map(p => ({ value: p, label: p }))]} />
            <Select className="filter-select" value={filterInfluencer} onChange={setFilterInfluencer} placeholder={t('creativeOs.project.filterInfluencer')} style={{ width: '160px', flexShrink: 0 }}
                options={[{ value: '', label: t('creativeOs.project.filterAllInfluencers') }, ...influencerOptions.map(i => ({ value: i, label: i }))]} />
            <Select className="filter-select" value={filterMode} onChange={setFilterMode} placeholder={t('creativeOs.project.filterMode')} style={{ width: '130px', flexShrink: 0 }}
                options={[{ value: '', label: t('creativeOs.project.filterAllModes') }, ...modeOptions.map(m => ({ value: m, label: m }))]} />

            {hasActiveFilters && (
                <button
                    onClick={() => { setFilterProduct(''); setFilterInfluencer(''); setFilterMode(''); }}
                    style={{
                        padding: '4px 8px', borderRadius: '6px', border: 'none',
                        background: 'rgba(220,53,69,0.06)', color: '#DC3545',
                        fontSize: '11px', fontWeight: 600, cursor: 'pointer',
                        display: 'flex', alignItems: 'center', gap: '3px', flexShrink: 0,
                    }}
                >
                    <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
                        <line x1="1" y1="1" x2="11" y2="11" /><line x1="11" y1="1" x2="1" y2="11" />
                    </svg>
                    Clear
                </button>
            )}
            {hasActiveFilters && (
                <span style={{ fontSize: '11px', color: '#8A93B0', fontWeight: 500, flexShrink: 0 }}>
                    {filteredAssets.length} of {currentAssets.length}
                </span>
            )}
            </div>
        </div>
    );

    const galleryBlock = (
        <AssetGallery
            assets={filteredAssets}
            type={activeTab}
            loading={loading}
            projectId={projectId}
            onRefresh={() => fetchAssets(true)}
            onAnimated={() => {
                setActiveTab('videos');
                fetchAssets(true);
            }}
            onCreateVideo={(asset) => {
                setCreateVideoImage(asset);
                setActiveTab('videos');
            }}
        />
    );

    const createBarBlock = (
        <CreateBar
            activeTab={activeTab}
            projectId={projectId}
            onGenerated={() => fetchAssets(true)}
            preloadImage={createVideoImage}
            onPreloadConsumed={() => setCreateVideoImage(null)}
        />
    );

    // Narrow viewports (<1024px): single-column layout with floating AgentPanel.
    if (!isWide) {
        return (
            <div style={{
                padding: `32px 32px ${createBarOpen ? '140px' : '32px'}`,
                maxWidth: '1200px',
                margin: '0 auto',
            }}>
                {projectHeaderBar}
                {galleryBlock}
                {createBarOpen && createBarBlock}
                <AgentPanel ref={agentRef} projectId={projectId} jobId={selectedJobId} onArtifact={() => fetchAssets(true)} onStateChange={setAgentState} initialBrief={initialBrief || undefined} initialRefs={initialRefs} initialUseSeedance={initialUseSeedance} onJobStart={(kind) => { setActiveTab(kind === 'video' ? 'videos' : 'images'); startJobRefetchBurst(); }} />
            </div>
        );
    }

    // Desktop (>=1024px): unified header bar spanning full width,
    // then a split-panel below: agent on left, gallery on right.
    return (
        <div style={{
            display: 'flex',
            flexDirection: 'column',
            position: 'fixed',
            top: 'var(--header-h, 60px)',
            left: 0, right: 0, bottom: 0,
            overflow: 'hidden',
            background: '#F8FAFC',
        }}>
            {/* Unified header bar */}
            {projectHeaderBar}

            {/* Split panel below the header */}
            <div style={{ display: 'flex', flex: 1, overflow: 'hidden' }}>
                {/* Left column: Agent panel (collapsible) */}
                {agentOpen && (
                    <div style={{
                        width: '38%', minWidth: '360px', maxWidth: '520px',
                        borderRight: '1px solid rgba(13,27,62,0.07)',
                        display: 'flex', flexDirection: 'column',
                        background: '#FFFFFF', flexShrink: 0, overflow: 'hidden',
                    }}>
                        <AgentPanel
                            ref={agentRef}
                            projectId={projectId}
                            jobId={selectedJobId}
                            onArtifact={() => fetchAssets(true)}
                            embedded={true}
                            hideHeader={true}
                            onStateChange={setAgentState}
                            initialBrief={initialBrief || undefined}
                            initialRefs={initialRefs}
                            initialUseSeedance={initialUseSeedance}
                            onJobStart={(kind) => { setActiveTab(kind === 'video' ? 'videos' : 'images'); startJobRefetchBurst(); }}
                        />
                    </div>
                )}

                {/* Right column: gallery */}
                <div style={{
                    flex: 1, display: 'flex', flexDirection: 'column',
                    overflow: 'hidden', minWidth: 0, position: 'relative',
                    transform: 'translateZ(0)',
                }}>
                    <div style={{
                        flex: 1, overflowY: 'auto',
                        padding: `24px 28px ${createBarOpen ? '160px' : '32px'}`,
                    }}>
                        {galleryBlock}
                    </div>
                    {createBarOpen && (
                        <div style={{ flexShrink: 0, zIndex: 10 }}>
                            {createBarBlock}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
