'use client';

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslation } from '@/lib/i18n';
import HookBreakdownPanel from './HookBreakdownPanel';
import {
    analyticsFetch,
    formatCount,
    isVideoAnalyticsPost,
    resolveDisplayViews,
    resolvePostPosterUrl,
    timeAgo,
    type AnalyticsBreakdown,
    type AnalyticsPost,
    type AnalyzeVideoResponse,
    type PostDetailResponse,
    type VideoPrepResponse,
} from './analytics-types';
import { resolveInstagramEmbedShortcode } from './instagramPermalink';
import { exportPostAnalysisPdf } from './exportPostAnalysisPdf';
import { launchCreativeOsProject } from '@/lib/launchCreativeOsProject';
import type { AgentRef } from '@/lib/creative-os-api';
import { buildVideoTemplateBrief } from './buildVideoTemplateBrief';
import TemplateCreatorPicker from './TemplateCreatorPicker';

const PLATFORM_COLORS: Record<string, string> = {
    instagram: '#E1306C',
    tiktok:    '#000000',
    youtube:   '#FF0000',
    facebook:  '#1877F2',
};

interface Props {
    postId: string;
    onClose: () => void;
    /** Bumped by the analytics page Refresh button — restarts prep polling. */
    refreshKey?: number;
}

type PrepPollSession = {
    cancelled: boolean;
    elapsed: number;
    stuckQueuedMs: number;
    timerId: number | null;
    postId: string;
    needsKickoff: boolean;
};

function formatAnalyzeError(err: unknown, t: (key: string) => string): string {
    const raw = err instanceof Error ? err.message : String(err);
    const m = raw.toLowerCase();
    if (
        m === 'failed to fetch'
        || m.includes('networkerror')
        || m.includes('load failed')
        || m.includes('network request failed')
    ) {
        return t('analytics.detail.error.network');
    }
    if (/^api error: 5\d\d/.test(m)) {
        return t('analytics.detail.error.server');
    }
    return raw || t('analytics.detail.error.startFailed');
}

function MetricCell({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
    return (
        <div
            style={{
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: '10px',
                padding: '10px 12px',
                display: 'flex',
                flexDirection: 'column',
                gap: '2px',
                minWidth: 0,
            }}
        >
            <span style={{ fontSize: '15px', fontWeight: 700, color: accent ? 'var(--blue)' : 'var(--text-1)' }}>
                {value}
            </span>
            <span style={{ fontSize: '10px', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: 0.4 }}>
                {label}
            </span>
        </div>
    );
}

/** Full-page post detail (video left, metrics right). Kept filename for import stability. */
export default function PostDetailView({ postId, onClose, refreshKey = 0 }: Props) {
    const { t, lang } = useTranslation();
    const router = useRouter();
    const [post, setPost] = useState<AnalyticsPost | null>(null);
    const [breakdown, setBreakdown] = useState<AnalyticsBreakdown | null>(null);
    const [loading, setLoading] = useState(true);
    const [generating, setGenerating] = useState(false);
    /**
     * Lazy video-prep state. The backend's POST /prepare-video does the
     * heavy lifting (per-post BrightData scrape if needed, then mirror to
     * Supabase Storage). The modal polls until `ready` / `failed`.
     *
     * IG and TikTok iframe embeds *don't actually play inline* outside a
     * logged-in session — they just show a thumbnail with a "Watch on …"
     * button that deep-links out. The mirrored Storage URL is the only way
     * to (a) preview the video inside the modal and (b) feed Gemini for the
     * AI breakdown.
     */
    const [prep, setPrep] = useState<VideoPrepResponse | null>(null);
    const videoRef = useRef<HTMLVideoElement | null>(null);
    /**
     * Live duration derived from the `<video>` element. We persist it back
     * to the DB via POST /posts/{id}/duration on first load so future opens
     * (and the AI breakdown) see it without re-derivation. BrightData often
     * omits this field for IG account-scrape responses, which is why the
     * metric was reading "—" even on video posts.
     */
    const [derivedDuration, setDerivedDuration] = useState<number | undefined>(undefined);
    const [exportingPdf, setExportingPdf] = useState(false);
    const [showTemplatePicker, setShowTemplatePicker] = useState(false);
    const [templateLaunching, setTemplateLaunching] = useState(false);
    const [templateError, setTemplateError] = useState<string | null>(null);
    const persistedDurationRef = useRef<boolean>(false);
    const autoBreakdownRef = useRef(false);
    const breakdownPollElapsedRef = useRef(0);
    const lastPollBreakdownIdRef = useRef<string | null>(null);
    const initialLocaleSyncRef = useRef(false);
    const prepPollRef = useRef<PrepPollSession | null>(null);

    const stopPrepPolling = useCallback(() => {
        const session = prepPollRef.current;
        if (!session) return;
        session.cancelled = true;
        if (session.timerId != null) {
            window.clearTimeout(session.timerId);
        }
        prepPollRef.current = null;
    }, []);

    /* Fetch post + existing breakdown */
    const reload = useCallback(async () => {
        setLoading(true);
        // Reset duration-derivation state so re-opening a different post
        // doesn't reuse the previous post's persisted-flag.
        persistedDurationRef.current = false;
        setDerivedDuration(undefined);
        try {
            const data = await analyticsFetch<PostDetailResponse>(
                `/api/analytics/posts/${postId}`,
                { skipProjectScope: true },
            );
            setPost(data.post);
            setBreakdown(data.breakdown);
        } catch {
            setPost(null);
            setBreakdown(null);
        } finally {
            setLoading(false);
        }
    }, [postId]);

    /** Re-fetch breakdown when UI language changes (sync translate on server). */
    const reloadBreakdown = useCallback(async (opts?: { syncLocale?: boolean }) => {
        try {
            const data = await analyticsFetch<PostDetailResponse>(
                `/api/analytics/posts/${postId}`,
                {
                    skipProjectScope: true,
                    headers: opts?.syncLocale ? { 'X-Ui-Language-Sync': '1' } : undefined,
                },
            );
            setPost(data.post);
            setBreakdown(data.breakdown);
        } catch {
            /* Keep existing content visible on transient refetch failure. */
        }
    }, [postId]);

    const startPrepPolling = useCallback((opts?: { force?: boolean }) => {
        if (!post || post.storage_video_url) {
            if (post?.storage_video_url) {
                setPrep({
                    status: 'ready',
                    progress_pct: 100,
                    storage_video_url: post.storage_video_url,
                });
            }
            return;
        }
        if (!isVideoAnalyticsPost(post)) {
            setPrep({
                status: 'skipped',
                progress_pct: 0,
                error_message: t('analytics.detail.prep.videoOnly'),
            });
            return;
        }

        stopPrepPolling();
        const session: PrepPollSession = {
            cancelled: false,
            elapsed: 0,
            stuckQueuedMs: 0,
            timerId: null,
            postId: post.id,
            needsKickoff: true,
        };
        prepPollRef.current = session;

        const pollInterval = 2000;
        const maxPrepMs = 5 * 60 * 1000;
        const stuckThresholdMs = 25_000;

        const schedule = (fn: () => void, delay: number) => {
            session.timerId = window.setTimeout(fn, delay);
        };

        const finishReady = (res: VideoPrepResponse) => {
            setPrep(res);
            if (res.storage_video_url) {
                setPost((prev) =>
                    prev ? { ...prev, storage_video_url: res.storage_video_url ?? undefined } : prev,
                );
            } else {
                reloadBreakdown();
            }
        };

        const tick = async (force = false) => {
            if (session.cancelled || prepPollRef.current !== session) return;
            if (session.elapsed >= maxPrepMs) {
                setPrep({
                    status: 'failed',
                    progress_pct: 0,
                    error_message: 'Video prep timed out — try again or refresh the post.',
                });
                stopPrepPolling();
                return;
            }

            try {
                let res: VideoPrepResponse;
                if (session.needsKickoff || force) {
                    const path = force
                        ? `/api/analytics/posts/${session.postId}/prepare-video?force=true`
                        : `/api/analytics/posts/${session.postId}/prepare-video`;
                    res = await analyticsFetch<VideoPrepResponse>(path, {
                        method: 'POST',
                        skipProjectScope: true,
                    });
                    session.needsKickoff = false;
                } else {
                    res = await analyticsFetch<VideoPrepResponse>(
                        `/api/analytics/posts/${session.postId}/prepare-video/status`,
                        { skipProjectScope: true },
                    );
                    if (res.status === 'idle') {
                        session.needsKickoff = true;
                        schedule(() => tick(false), 0);
                        return;
                    }
                }

                if (session.cancelled || prepPollRef.current !== session) return;
                setPrep(res);

                if (res.status === 'ready') {
                    finishReady(res);
                    stopPrepPolling();
                    return;
                }
                if (res.status === 'failed' || res.status === 'skipped') {
                    stopPrepPolling();
                    return;
                }

                if (
                    (res.status === 'queued' || res.status === 'scraping')
                    && (res.progress_pct ?? 0) <= 5
                ) {
                    session.stuckQueuedMs += pollInterval;
                    if (session.stuckQueuedMs >= stuckThresholdMs && !force) {
                        session.stuckQueuedMs = 0;
                        schedule(() => tick(true), 0);
                        return;
                    }
                } else {
                    session.stuckQueuedMs = 0;
                }

                session.elapsed += pollInterval;
                schedule(() => tick(false), pollInterval);
            } catch (e) {
                if (session.cancelled || prepPollRef.current !== session) return;
                setPrep({
                    status: 'failed',
                    progress_pct: 0,
                    error_message: e instanceof Error ? e.message : 'Video prep failed',
                });
                stopPrepPolling();
            }
        };

        tick(opts?.force ?? false);
    }, [post, stopPrepPolling, reloadBreakdown, t]);

    const retryPrep = useCallback(() => {
        if (!post) return;
        startPrepPolling({ force: true });
    }, [post, startPrepPolling]);

    const retryLocale = useCallback(() => {
        reloadBreakdown({ syncLocale: true });
    }, [reloadBreakdown]);

    const prevLangRef = useRef(lang);
    useEffect(() => {
        if (prevLangRef.current === lang) return;
        prevLangRef.current = lang;
        reloadBreakdown({ syncLocale: true });
    }, [lang, reloadBreakdown]);

    /* Reset prep + auto-analyze when switching posts. */
    useEffect(() => {
        setPrep(null);
        stopPrepPolling();
        autoBreakdownRef.current = false;
    }, [postId, stopPrepPolling]);

    useEffect(() => {
        reload();
    }, [reload]);

    /* Sync-translate on open when UI language differs from breakdown content. */
    useEffect(() => {
        initialLocaleSyncRef.current = false;
    }, [postId, lang]);

    useEffect(() => {
        if (loading || initialLocaleSyncRef.current || !breakdown) return;
        if (breakdown.status !== 'completed') return;
        const contentLoc = breakdown.content_locale;
        if (!contentLoc || contentLoc === lang) return;
        initialLocaleSyncRef.current = true;
        reloadBreakdown({ syncLocale: true });
    }, [loading, breakdown, lang, reloadBreakdown]);

    /* Reset auto-analyze guard when video prep completes. */
    useEffect(() => {
        if (prep?.status === 'ready') {
            autoBreakdownRef.current = false;
        }
    }, [prep?.status]);

    /* Lazy video prep — POST once to kick off, then poll GET status until ready/failed. */
    useEffect(() => {
        if (!post || loading) return;
        if (!isVideoAnalyticsPost(post)) {
            setPrep({
                status: 'skipped',
                progress_pct: 0,
                error_message: t('analytics.detail.prep.videoOnly'),
            });
            return;
        }
        if (post.storage_video_url) {
            setPrep({
                status: 'ready',
                progress_pct: 100,
                storage_video_url: post.storage_video_url,
            });
            return;
        }
        startPrepPolling();
        return () => {
            stopPrepPolling();
        };
    }, [post?.id, post?.storage_video_url, post?.media_type, post?.video_job_id, loading, startPrepPolling, stopPrepPolling, t]);

    /* Restart prep when the analytics page Refresh button fires. */
    const prevRefreshKeyRef = useRef(refreshKey);
    useEffect(() => {
        if (prevRefreshKeyRef.current === refreshKey) return;
        prevRefreshKeyRef.current = refreshKey;
        if (!refreshKey || !post || loading || post.storage_video_url || !isVideoAnalyticsPost(post)) return;
        startPrepPolling({ force: true });
    }, [refreshKey, post, loading, startPrepPolling]);

    /* Poll while a breakdown is running */
    const breakdownId = breakdown?.id;
    const breakdownStatus = breakdown?.status;

    useEffect(() => {
        if (!breakdownId || (breakdownStatus !== 'pending' && breakdownStatus !== 'running')) {
            return;
        }
        if (lastPollBreakdownIdRef.current !== breakdownId) {
            breakdownPollElapsedRef.current = 0;
            lastPollBreakdownIdRef.current = breakdownId;
        }
        let cancelled = false;
        let delay = 3000;
        let pollErrors = 0;
        const maxTotal = 5 * 60 * 1000;

        const tick = async () => {
            if (cancelled) return;
            try {
                const next = await analyticsFetch<AnalyticsBreakdown>(
                    `/api/analytics/breakdowns/${breakdownId}`,
                    { skipProjectScope: true },
                );
                if (cancelled) return;
                pollErrors = 0;
                setBreakdown(next);
                if (next.status === 'completed' || next.status === 'failed') return;
            } catch (e) {
                pollErrors += 1;
                if (pollErrors >= 5) {
                    setBreakdown((prev) =>
                        prev
                            ? {
                                ...prev,
                                status: 'failed',
                                error_message: formatAnalyzeError(e, t),
                            }
                            : prev,
                    );
                    return;
                }
            }
            breakdownPollElapsedRef.current += delay;
            if (breakdownPollElapsedRef.current >= maxTotal) {
                setBreakdown((prev) =>
                    prev
                        ? {
                            ...prev,
                            status: 'failed',
                            error_message: 'AI analysis timed out — try again.',
                        }
                        : prev,
                );
                return;
            }
            delay = Math.min(delay * 1.4, 30_000);
            window.setTimeout(tick, delay);
        };

        const timer = window.setTimeout(tick, delay);
        return () => {
            cancelled = true;
            window.clearTimeout(timer);
        };
    }, [breakdownId, breakdownStatus, t]);

    /* Poll while a locale translation is pending (async path on first open). */
    const localePending = breakdown?.locale_pending === true;

    useEffect(() => {
        if (!breakdownId || breakdownStatus !== 'completed' || !localePending) {
            return;
        }
        let cancelled = false;
        let elapsed = 0;
        const interval = 2500;
        const maxMs = 60_000;

        const tick = async () => {
            if (cancelled) return;
            try {
                const next = await analyticsFetch<AnalyticsBreakdown>(
                    `/api/analytics/breakdowns/${breakdownId}`,
                    {
                        skipProjectScope: true,
                        headers: elapsed >= 15_000 ? { 'X-Ui-Language-Sync': '1' } : undefined,
                    },
                );
                if (cancelled) return;
                setBreakdown(next);
                if (!next.locale_pending && next.content_locale === lang) return;
            } catch {
                /* retry */
            }
            elapsed += interval;
            if (elapsed >= maxMs) {
                reloadBreakdown({ syncLocale: true });
                return;
            }
            window.setTimeout(tick, interval);
        };

        const timer = window.setTimeout(tick, interval);
        return () => {
            cancelled = true;
            window.clearTimeout(timer);
        };
    }, [breakdownId, breakdownStatus, localePending, lang, reloadBreakdown]);

    /* Close on Escape */
    useEffect(() => {
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [onClose]);

    /* Capture real duration from the playing `<video>` and persist it back
     * to the DB so it's available even before the user runs AI breakdown.
     *
     * Fires once on first `loadedmetadata`. We:
     *   1. Cache locally so the metric cell updates instantly.
     *   2. POST to /posts/{id}/duration *only* if the row didn't already
     *      have one — best-effort, swallowed on failure.
     */
    const handleVideoLoadedMetadata = useCallback(
        (e: React.SyntheticEvent<HTMLVideoElement>) => {
            const dur = e.currentTarget.duration;
            if (!Number.isFinite(dur) || dur <= 0) return;
            setDerivedDuration(dur);
            if (!post || persistedDurationRef.current || post.duration_seconds) return;
            persistedDurationRef.current = true;
            analyticsFetch(`/api/analytics/posts/${post.id}/duration`, {
                method: 'POST',
                body: JSON.stringify({ duration_seconds: dur }),
                skipProjectScope: true,
            })
                .then(() => {
                    // Patch the post in-place so the in-memory row matches
                    // the DB and we don't accidentally re-POST on re-render.
                    setPost((prev) => (prev ? { ...prev, duration_seconds: dur } : prev));
                })
                .catch(() => {
                    persistedDurationRef.current = false;
                });
        },
        [post],
    );

    const triggerGenerate = useCallback(async () => {
        if (!post) return;
        setGenerating(true);
        try {
            const body: Record<string, string> = { analytics_post_id: post.id };
            if (post.video_job_id) {
                body.video_job_id = post.video_job_id;
            }
            const res = await analyticsFetch<AnalyzeVideoResponse>('/api/analytics/analyze-video', {
                method: 'POST',
                body: JSON.stringify(body),
                skipProjectScope: true,
            });
            setBreakdown({
                id: res.breakdown_id,
                status: res.status,
            });
        } catch (e) {
            // Surface the failure to the user via a synthetic "failed"
            // breakdown so the HookBreakdownPanel renders the error + retry
            // button instead of silently doing nothing. Reuses the existing
            // failed-state UI — no extra branches needed.
            const message = formatAnalyzeError(e, t);
            setBreakdown({
                id: breakdown?.id || 'pending-error',
                status: 'failed',
                error_message: message,
            });
        } finally {
            setGenerating(false);
        }
    }, [post, breakdown?.id, t]);

    const videoReadyForAnalysis = useMemo(
        () =>
            !!post
            && isVideoAnalyticsPost(post)
            && (
                !!post.storage_video_url
                || (post.source === 'internal' && !!post.video_job_id)
                || prep?.status === 'ready'
            ),
        [post, prep?.status],
    );

    /* Auto-start AI breakdown when video is ready and no analysis is in flight. */
    useEffect(() => {
        if (autoBreakdownRef.current || loading || generating || !post) return;
        const bs = breakdown?.status;
        if (bs === 'completed' || bs === 'pending' || bs === 'running') return;
        if (!videoReadyForAnalysis) return;
        autoBreakdownRef.current = true;
        triggerGenerate();
    }, [post, breakdown, loading, generating, prep?.status, videoReadyForAnalysis, triggerGenerate]);

    /* Resolve the best video URL.
     *
     * Priority:
     *   1. Supabase-mirrored URL (always playable — set by the scraper's
     *      background mirror thread for external posts, set directly for
     *      internal/UGC posts via video_jobs).
     *   2. media_urls[0].url (BrightData CDN — only useful while fresh).
     *   3. null → caller falls through to platform-embed iframe.
     */
    const directVideoUrl: string | null = (() => {
        if (!post) return null;
        if (post.storage_video_url) return post.storage_video_url;
        const media = post.media_urls && post.media_urls.length > 0 ? post.media_urls[0] : null;
        if (media && typeof media === 'object' && 'url' in media) {
            const u = (media as { url?: string }).url;
            // Skip the BrightData CDN URL — it expires + blocks CORS, so the
            // <video> tag will never play it. The iframe embed always works.
            if (u && !/cdninstagram\.com|fbcdn\.net|tiktokcdn|fbsbx\.com/i.test(u)) {
                return u;
            }
        }
        return null;
    })();

    /* Per-platform embed URL — used when no direct video URL is available.
     * These are the official, public embed endpoints documented by each
     * platform and require no JS shim.
     *
     * Note: we deliberately use Instagram's *non-captioned* `/embed/` (not
     * `/embed/captioned/`) because the modal already renders the caption
     * separately below the video — including it twice both wastes vertical
     * space and forces the iframe to scroll internally. */
    const embedUrl: string | null = (() => {
        if (!post) return null;
        const platform = (post.platform || '').toLowerCase();
        const postUrl = post.post_url || '';
        if (platform === 'instagram') {
            const shortcode = resolveInstagramEmbedShortcode(post);
            if (shortcode) {
                return `https://www.instagram.com/p/${encodeURIComponent(shortcode)}/embed/`;
            }
            return null;
        }
        const pid = post.external_post_id || '';
        if (platform === 'tiktok' && pid) {
            return `https://www.tiktok.com/embed/v2/${encodeURIComponent(pid)}`;
        }
        if (platform === 'youtube' && pid) {
            return `https://www.youtube.com/embed/${encodeURIComponent(pid)}`;
        }
        if (platform === 'facebook' && postUrl) {
            return `https://www.facebook.com/plugins/post.php?href=${encodeURIComponent(postUrl)}&show_text=false`;
        }
        return null;
    })();

    const status: AnalyticsBreakdown['status'] | 'none' = breakdown ? breakdown.status : 'none';
    const canGenerate = !!post && videoReadyForAnalysis;
    const platformAccent = post ? PLATFORM_COLORS[post.platform] || 'var(--text-2)' : 'var(--text-2)';

    const handleExportPdf = useCallback(async () => {
        if (!post || exportingPdf) return;
        setExportingPdf(true);
        try {
            await exportPostAnalysisPdf({
                post,
                breakdown,
                derivedDuration,
                labels: {
                    reportTitle: t('analytics.detail.export.reportTitle'),
                    metrics: t('analytics.detail.metrics'),
                    views: t('analytics.detail.export.views'),
                    likes: t('analytics.detail.export.likes'),
                    comments: t('analytics.detail.export.comments'),
                    shares: t('analytics.detail.export.shares'),
                    engagement: t('analytics.detail.export.engagement'),
                    duration: t('analytics.detail.export.duration'),
                    hidden: t('analytics.detail.hidden'),
                    measuring: t('analytics.detail.measuring'),
                    caption: t('analytics.detail.export.caption'),
                    aiBreakdown: t('analytics.detail.aiBreakdown'),
                    hook: t('analytics.detail.hook'),
                    scenes: t('analytics.detail.scenes'),
                    audio: t('analytics.detail.audio'),
                    visualDetails: t('analytics.detail.visualDetails'),
                    keyMoments: t('analytics.detail.keyMoments'),
                    takeaways: t('analytics.detail.takeaways'),
                    summary: t('analytics.detail.export.summary'),
                    onScreen: t('analytics.detail.export.onScreen'),
                    whyItWorks: t('analytics.detail.export.whyItWorks'),
                    noAudio: t('analytics.detail.export.noAudio'),
                    analysisPending: t('analytics.detail.export.analysisPending'),
                    analysisRunning: t('analytics.detail.export.analysisRunning'),
                    analysisFailed: t('analytics.detail.export.analysisFailed'),
                    analysisNone: t('analytics.detail.export.analysisNone'),
                    generatedOn: t('analytics.detail.export.generatedOn'),
                    postUrl: t('analytics.detail.export.postUrl'),
                    posted: t('analytics.detail.export.posted'),
                    exporting: t('analytics.detail.export.exporting'),
                },
            });
        } catch {
            // Best-effort — user can retry
        } finally {
            setExportingPdf(false);
        }
    }, [post, breakdown, derivedDuration, exportingPdf, t]);

    const templateReady = breakdown?.status === 'completed';

    const handleOpenTemplatePicker = useCallback(() => {
        if (!post || !templateReady || templateLaunching) return;
        setTemplateError(null);
        setShowTemplatePicker(true);
    }, [post, templateReady, templateLaunching]);

    const handleTemplateConfirm = useCallback(async (selectedCreator: AgentRef | null) => {
        if (!post || !breakdown) return;
        setTemplateLaunching(true);
        setTemplateError(null);
        try {
            const durationSec = derivedDuration ?? post.duration_seconds;
            const { brief, refs } = buildVideoTemplateBrief(
                post,
                breakdown,
                durationSec,
                selectedCreator,
            );
            const projectId = await launchCreativeOsProject(router, { brief, refs });
            if (!projectId) {
                throw new Error(t('analytics.detail.template.error'));
            }
            // Hard navigation in progress — do not close modals or touch /schedule router.
            return;
        } catch (e) {
            const msg = e instanceof Error ? e.message : t('analytics.detail.template.error');
            setTemplateError(msg);
            setTemplateLaunching(false);
        }
    }, [post, breakdown, derivedDuration, router, t]);

    const mediaBlock = !loading && post ? (() => {
        const posterUrl = resolvePostPosterUrl(post);
        const platform = (post.platform || '').toLowerCase();
        const isVertical = platform === 'tiktok' || platform === 'instagram';
        const videoAspect = isVertical ? '9 / 16' : '16 / 9';
        const embedAspect =
            platform === 'instagram' ? '9 / 20' :
            platform === 'tiktok'    ? '9 / 20' :
            platform === 'facebook'  ? '1 / 1'  :
            '16 / 9';

        // Fit inside the viewport under the app header + detail toolbar so
        // play controls stay visible without scrolling.
        const viewportMediaMax: CSSProperties = {
            maxHeight: 'calc(100vh - var(--header-h) - 120px)',
            maxWidth: isVertical ? 'min(100%, 380px)' : '100%',
            width: '100%',
            height: 'auto',
            margin: '0 auto',
        };

        const baseWrapper: CSSProperties = {
            position: 'relative',
            background: 'black',
            borderRadius: 12,
            overflow: 'hidden',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            ...viewportMediaMax,
        };

        if (directVideoUrl) {
            return (
                <div
                    className="analytics-post-media-frame"
                    style={{ ...baseWrapper, aspectRatio: videoAspect }}
                >
                    <video
                        ref={videoRef}
                        src={directVideoUrl}
                        controls
                        playsInline
                        poster={posterUrl}
                        crossOrigin="anonymous"
                        onLoadedMetadata={handleVideoLoadedMetadata}
                        style={{ width: '100%', height: '100%', maxHeight: 'inherit', objectFit: 'contain' }}
                    />
                </div>
            );
        }

        const prepInProgress =
            prep?.status === 'queued' ||
            prep?.status === 'scraping' ||
            prep?.status === 'downloading';

        if (prepInProgress) {
            const pct = Math.max(5, Math.min(100, prep?.progress_pct ?? 5));
            const stageLabel =
                prep?.status === 'scraping'    ? t('analytics.detail.prep.scraping')
              : prep?.status === 'downloading' ? t('analytics.detail.prep.downloading')
              :                                  t('analytics.detail.prep.queued');
            return (
                <div
                    className="analytics-post-media-frame"
                    style={{
                        ...baseWrapper,
                        aspectRatio: videoAspect,
                        background: `center / cover no-repeat ${posterUrl ? `url(${JSON.stringify(posterUrl)})` : 'black'}`,
                    }}
                >
                    <div style={{ position: 'absolute', inset: 0, background: 'rgba(13,27,62,0.55)', backdropFilter: 'blur(2px)' }} />
                    <div style={{ position: 'relative', zIndex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14, padding: '0 24px', width: '100%', maxWidth: 320 }}>
                        <div style={{ color: 'white', fontSize: 13, fontWeight: 600, textAlign: 'center' }}>{stageLabel}</div>
                        <div style={{ width: '100%', height: 6, borderRadius: 999, background: 'rgba(255,255,255,0.18)', overflow: 'hidden' }}>
                            <div style={{ width: `${pct}%`, height: '100%', background: 'linear-gradient(90deg, #5B9CFF 0%, #337AFF 100%)', borderRadius: 999, transition: 'width 0.4s ease' }} />
                        </div>
                        <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 11, textAlign: 'center' }}>
                            {t('analytics.detail.prep.takes')}
                        </div>
                    </div>
                </div>
            );
        }

        if (embedUrl) {
            return (
                <div
                    className="analytics-post-media-frame"
                    style={{
                        ...baseWrapper,
                        background: 'var(--blue-light)',
                        aspectRatio: embedAspect,
                    }}
                >
                    <iframe
                        src={embedUrl}
                        title={`${post.platform} post preview`}
                        allow="autoplay; encrypted-media; picture-in-picture; clipboard-write"
                        allowFullScreen
                        scrolling="no"
                        referrerPolicy="strict-origin-when-cross-origin"
                        style={{ width: '100%', height: '100%', border: 0, display: 'block' }}
                    />
                </div>
            );
        }

        return (
            <div className="analytics-post-media-frame" style={{ ...baseWrapper, aspectRatio: videoAspect }}>
                <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 13 }}>No media URL captured.</div>
            </div>
        );
    })() : null;

    const metricsBlock = !loading && post ? (() => {
        const platformLc = (post.platform || '').toLowerCase();
        const sharesHiddenByPlatform =
            post.shares == null &&
            (platformLc === 'instagram' || platformLc === 'youtube');
        const sharesValue = sharesHiddenByPlatform
            ? t('analytics.detail.hidden')
            : formatCount(post.shares);
        const isStaticPost =
            post.media_type === 'image' ||
            post.media_type === 'carousel';
        const effectiveDuration = post.duration_seconds ?? derivedDuration;
        const durationValue = effectiveDuration
            ? `${Math.round(effectiveDuration)}s`
            : t('analytics.detail.measuring');

        return (
            <div>
                <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.6, color: 'var(--text-3)', marginBottom: 8 }}>
                    {t('analytics.detail.metrics')}
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))', gap: 8 }}>
                    <MetricCell label={t('analytics.detail.export.views')} value={formatCount(resolveDisplayViews(post))} />
                    <MetricCell label={t('analytics.detail.export.likes')} value={formatCount(post.likes)} />
                    <MetricCell label={t('analytics.detail.export.comments')} value={formatCount(post.comments)} />
                    <MetricCell label={t('analytics.detail.export.shares')} value={sharesValue} />
                    <MetricCell label={t('analytics.detail.export.engagement')} value={formatCount(post.total_engagement)} accent />
                    {!isStaticPost && (
                        <MetricCell label={t('analytics.detail.export.duration')} value={durationValue} />
                    )}
                </div>
            </div>
        );
    })() : null;

    return (
        <div className="analytics-post-detail">
            {/* Sticky toolbar */}
            <div
                className="analytics-post-detail-bar"
                style={{
                    position: 'sticky',
                    top: 0,
                    zIndex: 5,
                    background: 'rgba(255,255,255,0.96)',
                    backdropFilter: 'blur(8px)',
                    border: '1px solid var(--border)',
                    borderRadius: 12,
                    padding: '8px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    gap: 12,
                    flexWrap: 'wrap',
                    marginBottom: 12,
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
                    <button
                        type="button"
                        onClick={onClose}
                        aria-label="Back"
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: 6,
                            padding: '7px 12px',
                            borderRadius: 8,
                            border: '1px solid var(--border)',
                            background: 'white',
                            color: 'var(--text-1)',
                            fontSize: 13,
                            fontWeight: 600,
                            cursor: 'pointer',
                            flexShrink: 0,
                        }}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} aria-hidden>
                            <path d="M15 18l-6-6 6-6" />
                        </svg>
                        Back
                    </button>
                    <span
                        style={{
                            fontSize: 11,
                            fontWeight: 700,
                            padding: '3px 10px',
                            borderRadius: 999,
                            background: `${platformAccent}1F`,
                            color: platformAccent,
                            textTransform: 'uppercase',
                        }}
                    >
                        {post?.platform || '—'}
                    </span>
                    <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-1)', whiteSpace: 'nowrap' }}>
                        @{post?.username || '—'}
                    </span>
                    <span style={{ fontSize: 12, color: 'var(--text-3)' }}>
                        {post && timeAgo(post.posted_at || post.scraped_at)}
                    </span>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    {post && !loading && (
                        <button
                            type="button"
                            onClick={handleOpenTemplatePicker}
                            disabled={!templateReady || templateLaunching}
                            title={templateReady
                                ? t('analytics.detail.template.hint')
                                : t('analytics.detail.template.needsAnalysis')}
                            style={{
                                fontSize: 12,
                                fontWeight: 700,
                                color: 'white',
                                padding: '6px 12px',
                                borderRadius: 8,
                                border: '1px solid #34D399',
                                background: templateReady && !templateLaunching
                                    ? 'linear-gradient(135deg, #34D399 0%, #2DD4BF 100%)'
                                    : 'rgba(138,147,176,0.45)',
                                cursor: templateReady && !templateLaunching ? 'pointer' : 'not-allowed',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                                opacity: templateReady ? 1 : 0.85,
                            }}
                        >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} aria-hidden>
                                <path d="M9 11l3 3L22 4" />
                                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
                            </svg>
                            {t('analytics.detail.template.cta')}
                        </button>
                    )}
                    {post && !loading && (
                        <button
                            type="button"
                            onClick={handleExportPdf}
                            disabled={exportingPdf}
                            title={t('analytics.detail.export.hint')}
                            style={{
                                fontSize: 12,
                                fontWeight: 600,
                                color: 'var(--text-1)',
                                padding: '6px 12px',
                                borderRadius: 8,
                                border: '1px solid var(--border)',
                                background: 'white',
                                cursor: exportingPdf ? 'wait' : 'pointer',
                                display: 'flex',
                                alignItems: 'center',
                                gap: 6,
                                opacity: exportingPdf ? 0.7 : 1,
                            }}
                        >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} aria-hidden>
                                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                                <polyline points="14 2 14 8 20 8" />
                                <line x1="12" y1="18" x2="12" y2="12" />
                                <polyline points="9 15 12 18 15 15" />
                            </svg>
                            {exportingPdf
                                ? t('analytics.detail.export.exporting')
                                : t('analytics.detail.export.pdf')}
                        </button>
                    )}
                    {post?.post_url && (
                        <a
                            href={post.post_url}
                            target="_blank"
                            rel="noreferrer"
                            style={{
                                fontSize: 12,
                                fontWeight: 600,
                                color: 'var(--blue)',
                                textDecoration: 'none',
                                padding: '6px 12px',
                                borderRadius: 8,
                                border: '1px solid var(--border)',
                                background: 'white',
                            }}
                        >
                            {t('analytics.detail.viewOriginal')}
                        </a>
                    )}
                </div>
            </div>

            {loading || !post ? (
                <div style={{ color: 'var(--text-3)', fontSize: 13, padding: 48, textAlign: 'center' }}>
                    {t('common.loading')}
                </div>
            ) : (
                <div className="analytics-post-detail-grid">
                    <aside className="analytics-post-detail-media">
                        {mediaBlock}
                    </aside>
                    <section className="analytics-post-detail-metrics">
                        {metricsBlock}
                        {post.caption && (
                            <div
                                style={{
                                    background: 'var(--blue-light)',
                                    borderRadius: 10,
                                    padding: '10px 12px',
                                    fontSize: 12,
                                    color: 'var(--text-2)',
                                    lineHeight: 1.5,
                                }}
                            >
                                {post.caption}
                            </div>
                        )}
                        <div>
                            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.6, color: 'var(--text-3)', marginBottom: 8 }}>
                                {t('analytics.detail.aiBreakdown')}
                            </div>
                            <HookBreakdownPanel
                                breakdown={breakdown}
                                status={status}
                                videoRef={videoRef}
                                onGenerate={triggerGenerate}
                                canGenerate={canGenerate}
                                generating={generating}
                                prepStatus={prep?.status}
                                prepProgressPct={prep?.progress_pct}
                                prepError={prep?.error_message ?? undefined}
                                videoOnly={prep?.status === 'skipped' || !isVideoAnalyticsPost(post)}
                                targetLang={lang}
                                onRetryPrep={retryPrep}
                                onRetryLocale={retryLocale}
                            />
                        </div>
                    </section>
                </div>
            )}

            <style>{`
                .analytics-post-detail-grid {
                    display: grid;
                    grid-template-columns: minmax(240px, 38%) minmax(0, 1fr);
                    gap: 16px;
                    align-items: start;
                }
                .analytics-post-detail-media {
                    position: sticky;
                    top: 56px;
                    align-self: start;
                    display: flex;
                    justify-content: center;
                }
                /* When max-height binds, shrink width to keep aspect ratio so
                   native video controls stay inside the viewport. */
                .analytics-post-media-frame {
                    max-height: calc(100vh - var(--header-h) - 120px) !important;
                    width: auto !important;
                    max-width: min(100%, 380px) !important;
                }
                .analytics-post-media-frame video,
                .analytics-post-media-frame iframe {
                    max-height: calc(100vh - var(--header-h) - 120px);
                    width: 100%;
                    height: 100%;
                    object-fit: contain;
                }
                .analytics-post-detail-metrics {
                    display: flex;
                    flex-direction: column;
                    gap: 14px;
                    min-width: 0;
                }
                @media (max-width: 900px) {
                    .analytics-post-detail-grid {
                        grid-template-columns: 1fr;
                    }
                    .analytics-post-detail-media {
                        position: static;
                    }
                    .analytics-post-media-frame {
                        max-height: min(70vh, calc(100vh - var(--header-h) - 160px)) !important;
                        max-width: min(100%, 320px) !important;
                    }
                }
            `}</style>

            {showTemplatePicker && (
                <TemplateCreatorPicker
                    onClose={() => {
                        if (!templateLaunching) setShowTemplatePicker(false);
                    }}
                    onConfirm={handleTemplateConfirm}
                    launching={templateLaunching}
                    error={templateError}
                />
            )}
        </div>
    );
}
