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

/** Failed jobs with no media URL are ghost cards — hide from gallery. */
const isGhostAsset = (a: { status?: string; image_url?: string; final_video_url?: string; video_url?: string; is_placeholder?: boolean }, kind: 'images' | 'videos') => {
    if (a.is_placeholder) return false;
    const s = (a.status || '').toLowerCase();
    const hasMedia = kind === 'images'
        ? !!a.image_url
        : !!(a.final_video_url || a.video_url);
    return s.includes('failed') && !hasMedia;
};

const isInFlightStatus = (status?: string) => {
    const s = (status || '').toLowerCase();
    return s.includes('pending') || s.includes('processing') || s.includes('generating');
};

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
    // Always start from the SSR default (true = desktop) so the first client
    // render matches the server-rendered HTML — reading window.matchMedia in
    // the useState initializer caused a React hydration mismatch on narrow
    // viewports. The real viewport check runs in useEffect after mount.
    const [isWide, setIsWide] = useState<boolean>(true);
    useEffect(() => {
        if (typeof window === 'undefined') return;
        const mq = window.matchMedia('(min-width: 1024px)');
        // Sync the actual value once on mount, then keep listening for changes.
        setIsWide(mq.matches);
        const onChange = (e: MediaQueryListEvent) => setIsWide(e.matches);
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
    const reportedFailuresRef = useRef<Set<string>>(new Set()); // dedupe chat error injection
    const seenInPollRef = useRef<Set<string>>(new Set()); // ids confirmed present in jobs-status
    // Background video jobs (edit_video) finish minutes after tool_result — keep
    // polling these ids even if /full missed the initial processing row.
    const watchedVideoJobIdsRef = useRef<Set<string>>(new Set());
    const [watchPollTick, setWatchPollTick] = useState(0);
    // Sync agent panel state to power reactive header elements
    const [agentState, setAgentState] = useState<AgentPanelState>({ useSeedance: false, running: false, turnsCount: 0 });

    // In-flight placeholders for the right-panel gallery. Added when the
    // agent emits `artifact_pending` (right after the user confirms a paid
    // generation), cleared on the next fetchAssets refresh when the real
    // artifact has landed in Supabase.
    const addPendingPlaceholder = useCallback((p: { pending_id: string; kind: 'image' | 'video'; label: string; eta_seconds?: number }) => {
        const placeholder: any = {
            id: p.pending_id,
            is_placeholder: true,
            status: 'generating',
            label: p.label,
            eta_seconds: p.eta_seconds,
            created_at: new Date().toISOString(),
        };
        if (p.kind === 'video') {
            setVideos(prev => [placeholder, ...prev]);
            setActiveTab('videos');
        } else {
            setImages(prev => [placeholder, ...prev]);
            setActiveTab('images');
        }
    }, []);
    const clearPendingPlaceholders = useCallback(() => {
        setVideos(prev => prev.filter(v => !v.is_placeholder));
        setImages(prev => prev.filter(v => !v.is_placeholder));
    }, []);
    // Clear the OLDEST pending placeholder of a given kind. Called when a
    // matching real artifact lands so placeholders shrink one-by-one as
    // generations complete, instead of all-or-nothing on `done`.
    const clearOnePlaceholder = useCallback((kind: 'image' | 'video') => {
        const setter = kind === 'video' ? setVideos : setImages;
        setter(prev => {
            const idx = prev.findIndex(v => v.is_placeholder);
            if (idx === -1) return prev;
            const next = [...prev];
            next.splice(idx, 1);
            return next;
        });
    }, []);

    const registerVideoJobWatch = useCallback((jobId: string, label?: string) => {
        if (!jobId) return;
        watchedVideoJobIdsRef.current.add(jobId);
        setWatchPollTick((t) => t + 1);
        setVideos((prev) => {
            if (prev.some((v) => v.id === jobId)) return prev;
            return [{
                id: jobId,
                status: 'processing',
                progress: 5,
                status_message: 'Generating video',
                campaign_name: label || 'AI edit',
                model_api: 'gemini-omni-video',
                created_at: new Date().toISOString(),
            }, ...prev];
        });
        setActiveTab('videos');
    }, []);

    const fetchAssets = useCallback(async (silent = false) => {
        if (!session || !projectId) return;
        if (!silent) setLoading(true);
        try {
            // Single merged endpoint — builds product/influencer lookup maps
            // once on the backend instead of 3x. Cuts open-project from
            // ~5-10s to ~1-2s on projects with many assets.
            const full = await creativeFetch<{
                project: any;
                images: any[];
                videos: any[];
            }>(`/creative-os/projects/${projectId}/full`);
            setProjectName(full.project?.name || 'Project');
            // Preserve placeholders AND any in-flight processing rows that
            // landed locally (via poll) but aren't in /full yet — fetchAssets
            // used to wipe them on every burst refetch, making the progress
            // card flash for a few seconds then vanish while KIE still ran.
            // Keep local rows that /full hasn't caught up with yet — both
            // in-flight AND just-finished (jobs-status often leads /full by
            // several seconds; dropping success rows here made completed
            // videos vanish until a manual page refresh).
            const mergeFullAssets = <T extends { id?: string; is_placeholder?: boolean; status?: string; image_url?: string; final_video_url?: string; video_url?: string }>(
                prev: T[],
                fullRows: T[],
                hasPlayableMedia: (v: T) => boolean,
            ): T[] => {
                const placeholders = prev.filter(v => v.is_placeholder);
                const fullMap = new Map(fullRows.map(r => [r.id, r]));
                const localOnly = prev.filter(v => {
                    if (v.is_placeholder || !v.id || fullMap.has(v.id)) return false;
                    if (isInFlightStatus(v.status)) return true;
                    if ((v.status || '').toLowerCase() === 'success' && hasPlayableMedia(v)) return true;
                    return false;
                });
                return [...placeholders, ...localOnly, ...fullRows];
            };
            setImages(prev => mergeFullAssets(prev, full.images || [], v => !!v.image_url));
            setVideos(prev => {
                const merged = mergeFullAssets(
                    prev,
                    full.videos || [],
                    v => !!(v.final_video_url || v.video_url),
                );
                // Belt-and-suspenders: any processing row from /full gets watched
                // even if the video_job_started SSE was missed.
                let addedWatch = false;
                for (const v of merged) {
                    if (v.id && isInFlightStatus(v.status) && !watchedVideoJobIdsRef.current.has(v.id)) {
                        watchedVideoJobIdsRef.current.add(v.id);
                        addedWatch = true;
                    }
                }
                if (addedWatch) setWatchPollTick((t) => t + 1);
                return merged;
            });
        } catch (err) {
            console.error('Failed to fetch assets:', err);
        } finally {
            if (!silent) setLoading(false);
        }
    }, [session, projectId]);

    // Lightweight polling: only refresh status/preview for in-flight assets,
    // never re-pull the full project. Merges the small status payload back
    // into the cached lists.
    const pollInFlight = useCallback(async () => {
        if (!session || !projectId) return;
        const imageIds = images.filter(a => !a.is_placeholder && isInFlightStatus(a.status)).map(a => a.id).filter(Boolean);
        const inflightVideoIds = videos.filter(a => !a.is_placeholder && isInFlightStatus(a.status)).map(a => a.id).filter(Boolean);
        const watchedVideoIds = [...watchedVideoJobIdsRef.current];
        const videoIds = [...new Set([...inflightVideoIds, ...watchedVideoIds])];
        if (imageIds.length === 0 && videoIds.length === 0) return;

        const polledImageSet = new Set(imageIds);
        const polledVideoSet = new Set(videoIds);

        try {
            const status = await creativeFetch<{
                images: any[];
                videos: any[];
            }>(`/creative-os/projects/${projectId}/jobs-status`, {
                method: 'POST',
                body: JSON.stringify({ image_ids: imageIds, video_ids: videoIds }),
            });

            const imageMap = new Map((status.images || []).map(u => [u.id, u]));
            const videoMap = new Map((status.videos || []).map(u => [u.id, u]));
            let shouldNotifyFailure = false;
            const fallbackErrors: string[] = [];

            const reconcileList = <T extends { id?: string; status?: string; status_message?: string; image_url?: string; final_video_url?: string; video_url?: string; is_placeholder?: boolean }>(
                prev: T[],
                polled: Set<string>,
                updateMap: Map<string, T>,
                kind: 'images' | 'videos',
                defaultFailMsg: string,
            ): T[] => {
                return prev.flatMap(p => {
                    if (!p.id || !polled.has(p.id)) return [p];
                    const u = updateMap.get(p.id);
                    if (!u) {
                        // Only treat as deleted after we've seen this row in a
                        // prior poll — otherwise a race (row not committed yet,
                        // or /full lag) would flash-remove the progress card.
                        const seenKey = `${kind}:${p.id}`;
                        if (!seenInPollRef.current.has(seenKey)) {
                            return [p];
                        }
                        const key = `${kind}:${p.id}:deleted`;
                        if (!reportedFailuresRef.current.has(key)) {
                            reportedFailuresRef.current.add(key);
                            shouldNotifyFailure = true;
                            fallbackErrors.push(defaultFailMsg);
                        }
                        return [];
                    }
                    seenInPollRef.current.add(`${kind}:${p.id}`);
                    const merged = { ...p, ...u };
                    if (isGhostAsset(merged, kind)) {
                        const key = `${kind}:${p.id}:failed`;
                        if (!reportedFailuresRef.current.has(key)) {
                            reportedFailuresRef.current.add(key);
                            shouldNotifyFailure = true;
                            fallbackErrors.push(merged.status_message || defaultFailMsg);
                        }
                        return [];
                    }
                    return [merged];
                });
            };

            let anyVideoSuccess = false;
            let anyImageSuccess = false;
            for (const v of (status.videos || [])) {
                const polled = polledVideoSet.has(v.id);
                const wasInFlight = videos.some(
                    (p) => p.id === v.id && isInFlightStatus(p.status),
                );
                if (polled && wasInFlight && (v.status || '').toLowerCase() === 'success' && (v.final_video_url || v.video_url)) {
                    anyVideoSuccess = true;
                }
            }
            for (const im of (status.images || [])) {
                const polled = polledImageSet.has(im.id);
                const wasInFlight = images.some(
                    (p) => p.id === im.id && isInFlightStatus(p.status),
                );
                if (polled && wasInFlight && (im.status || '').toLowerCase() === 'success' && im.image_url) {
                    anyImageSuccess = true;
                }
            }

            setImages(prev => reconcileList(prev, polledImageSet, imageMap, 'images', 'Image generation failed — please try again.'));
            setVideos(prev => {
                let next = reconcileList(prev, polledVideoSet, videoMap, 'videos', 'Video generation failed — please try again.');
                // Watched background jobs may land in jobs-status before /full
                // ever returned them — merge those rows into the gallery.
                for (const id of polledVideoSet) {
                    if (next.some((v) => v.id === id)) continue;
                    const row = videoMap.get(id);
                    if (row && !isGhostAsset(row, 'videos')) {
                        next = [row, ...next];
                    }
                }
                return next;
            });

            if (anyVideoSuccess) clearOnePlaceholder('video');
            if (anyImageSuccess) clearOnePlaceholder('image');

            for (const v of (status.videos || [])) {
                const st = (v.status || '').toLowerCase();
                if (st === 'success' || st.includes('failed')) {
                    watchedVideoJobIdsRef.current.delete(String(v.id));
                }
            }
            if (watchedVideoIds.some((id) => {
                const row = videoMap.get(id);
                return row && ((row.status || '').toLowerCase() === 'success' || (row.status || '').toLowerCase().includes('failed'));
            })) {
                setWatchPollTick((t) => t + 1);
            }

            if (shouldNotifyFailure) {
                void (async () => {
                    let hasFailureTurn = await agentRef.current?.refreshThread?.() ?? false;
                    // Background failure append may land slightly after row delete.
                    if (!hasFailureTurn) {
                        await new Promise((r) => setTimeout(r, 2000));
                        hasFailureTurn = await agentRef.current?.refreshThread?.() ?? false;
                    }
                    if (hasFailureTurn) return;
                    // Legacy paths that only mark failed (no thread append) —
                    // inject a fallback error bubble so chat still explains it.
                    for (const msg of fallbackErrors) {
                        agentRef.current?.reportGenerationFailure(msg);
                    }
                })();
            }

            // Enriched metadata (product_name, mode, …) lives on /full only.
            // Delay slightly so /full has the row — mergeFullAssets keeps the
            // poll-merged playable URL visible until then.
            if (anyVideoSuccess || anyImageSuccess) {
                window.setTimeout(() => { fetchAssets(true); }, 1500);
            }
        } catch (err) {
            // Best-effort poll — transient backend/auth timeouts self-heal on
            // the next tick. Warn (not error) so we don't trip the dev error
            // overlay for an expected, recoverable condition.
            console.warn('Status poll failed (will retry next tick):', err);
        }
    }, [session, projectId, images, videos, fetchAssets, watchPollTick, clearOnePlaceholder]);

    // Initial fetch
    useEffect(() => {
        fetchAssets();
    }, [fetchAssets]);

    // Short-term aggressive refetch when an agent-launched job starts.
    // The backend may take 1–8s to insert the "processing" shot/job row
    // (influencer resolution, reference-image prep, product lookups),
    // so we poll every 1.5s for up to 20s to catch it as soon as it lands.
    // Once a pending row is in state, the 5s auto-poll below takes over.
    // Two-stage burst polling triggered by every tool_use (onJobStart):
    //   Stage 1: 1.5s × first 20s — catches the new shot row as soon as the
    //            backend writes it, even before the agent's tool_result.
    //   Stage 2: 5s × next 70s    — guarantees we keep polling for 90s total
    //            so the moment WaveSpeed / Fal / Kie writes status='success'
    //            (typically 30-90s after kick-off) the gallery refreshes
    //            without depending on the in-state auto-poll, which can miss
    //            races on brand-new empty projects (onboarding flow).
    const startJobRefetchBurst = useCallback(() => {
        if (burstRef.current) clearInterval(burstRef.current);
        const startedAt = Date.now();
        const tick = () => {
            fetchAssets(true);
            void pollInFlight();
        };
        tick();
        const FAST_MS = 1500;
        const SLOW_MS = 5000;
        const FAST_UNTIL = 20000;
        // Video edits (Omni) and UGC can run 5–12 min — keep burst alive long enough
        // that fetchAssets catches the processing row even if SSE was delayed.
        const TOTAL_MS = 600000;
        const schedule = (intervalMs: number) => setInterval(() => {
            const elapsed = Date.now() - startedAt;
            if (elapsed > TOTAL_MS) {
                if (burstRef.current) clearInterval(burstRef.current);
                burstRef.current = null;
                return;
            }
            // Swap to slow interval once past the fast window.
            if (intervalMs === FAST_MS && elapsed > FAST_UNTIL) {
                if (burstRef.current) clearInterval(burstRef.current);
                burstRef.current = schedule(SLOW_MS);
                tick();
                return;
            }
            tick();
        }, intervalMs);
        burstRef.current = schedule(FAST_MS);
    }, [fetchAssets, pollInFlight]);

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

    // Kick an immediate status poll when a background video job id is registered.
    useEffect(() => {
        if (watchedVideoJobIdsRef.current.size > 0) {
            void pollInFlight();
        }
    }, [watchPollTick, pollInFlight]);

    // Auto-poll: check for pending/processing assets every 2s (faster finish detection).
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
        const hasWatchedVideos = watchedVideoJobIdsRef.current.size > 0;

        if (hasPending || hasWatchedVideos) {
            void pollInFlight();
            pollRef.current = setInterval(() => {
                if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
                pollInFlight();
            }, 2000);
            const onVisible = () => {
                if (document.visibilityState === 'visible') pollInFlight();
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
    }, [images, videos, pollInFlight, watchPollTick]);

    // Reset filters when switching tabs
    useEffect(() => {
        setFilterProduct('');
        setFilterInfluencer('');
        setFilterMode('');
    }, [activeTab]);

    // ── Derive unique filter values from current tab assets ──
    const visibleImages = useMemo(
        () => images.filter(a => a.is_placeholder || !isGhostAsset(a, 'images')),
        [images],
    );
    const visibleVideos = useMemo(
        () => videos.filter(a => a.is_placeholder || !isGhostAsset(a, 'videos')),
        [videos],
    );
    const currentAssets = activeTab === 'images' ? visibleImages : visibleVideos;

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

            {/*
              Create Bar Toggle — REMOVED FROM UI.
              All creation flows run through the agent chat now. The button JSX
              was previously gated with `{false && isWide && (...)}` which still
              left the SVG/button definition in the parsed component tree and
              caused a React hydration mismatch on this page. Removing the JSX
              entirely eliminates the divergence.

              To re-enable: copy the agent-panel toggle button block right above
              this comment, swap `agentOpen` → `createBarOpen`, the title key to
              `creativeOs.project.bottomPanel{Hide,Show}`, and the SVG to the
              horizontal-line variant (rect + line at y=15).
            */}
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
                // Create Bar hidden — padding-bottom no longer reserves space for it.
                padding: '32px 32px 32px',
                maxWidth: '1200px',
                margin: '0 auto',
            }}>
                {projectHeaderBar}
                {galleryBlock}
                {false && createBarOpen && createBarBlock}
                <AgentPanel ref={agentRef} projectId={projectId} jobId={selectedJobId} onArtifact={() => { fetchAssets(true); }} onArtifactPending={addPendingPlaceholder} onArtifactReady={clearOnePlaceholder} onStateChange={setAgentState} initialBrief={initialBrief || undefined} initialRefs={initialRefs} initialUseSeedance={initialUseSeedance} onJobStart={(kind) => { setActiveTab(kind === 'video' ? 'videos' : 'images'); startJobRefetchBurst(); }} onVideoJobStarted={({ job_id, label }) => registerVideoJobWatch(job_id, label)} />
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
                            onArtifact={() => { fetchAssets(true); }} onArtifactPending={addPendingPlaceholder} onArtifactReady={clearOnePlaceholder}
                            embedded={true}
                            hideHeader={true}
                            onStateChange={setAgentState}
                            initialBrief={initialBrief || undefined}
                            initialRefs={initialRefs}
                            initialUseSeedance={initialUseSeedance}
                            onJobStart={(kind) => { setActiveTab(kind === 'video' ? 'videos' : 'images'); startJobRefetchBurst(); }}
                            onVideoJobStarted={({ job_id, label }) => registerVideoJobWatch(job_id, label)}
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
                        display: 'flex', flexDirection: 'column',
                        // Create Bar hidden — gallery extends to the bottom.
                        padding: '24px 28px 32px',
                    }}>
                        {galleryBlock}
                    </div>
                    {false && createBarOpen && (
                        <div style={{ flexShrink: 0, zIndex: 10 }}>
                            {createBarBlock}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
