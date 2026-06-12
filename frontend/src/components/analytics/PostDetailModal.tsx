'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTranslation } from '@/lib/i18n';
import HookBreakdownPanel from './HookBreakdownPanel';
import {
    analyticsFetch,
    formatCount,
    resolveDisplayViews,
    resolvePostPosterUrl,
    timeAgo,
    type AnalyticsBreakdown,
    type AnalyticsPost,
    type AnalyzeVideoResponse,
    type PostDetailResponse,
    type VideoPrepResponse,
    type VideoPrepStatus,
} from './analytics-types';
import { exportPostAnalysisPdf } from './exportPostAnalysisPdf';

const PLATFORM_COLORS: Record<string, string> = {
    instagram: '#E1306C',
    tiktok:    '#000000',
    youtube:   '#FF0000',
    facebook:  '#1877F2',
};

interface Props {
    postId: string;
    onClose: () => void;
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

export default function PostDetailModal({ postId, onClose }: Props) {
    const { t } = useTranslation();
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
    const persistedDurationRef = useRef<boolean>(false);
    const autoStudioBreakdownRef = useRef(false);

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

    useEffect(() => {
        reload();
    }, [reload]);

    /* Lazy video prep — fire on mount once the post is loaded and we don't
     * already have a Storage URL. Polls every 2s; backoff is unnecessary
     * because prep typically settles in < 30s (one BrightData scrape + one
     * Supabase upload).
     */
    useEffect(() => {
        if (!post) return;
        // Already mirrored / internal job with a stable URL — skip entirely.
        if (post.storage_video_url) {
            setPrep({
                status: 'ready',
                progress_pct: 100,
                storage_video_url: post.storage_video_url,
            });
            return;
        }
        let cancelled = false;
        let elapsed = 0;
        const pollInterval = 2000;
        const maxPrepMs = 5 * 60 * 1000;

        const poll = async () => {
            if (cancelled) return;
            if (elapsed >= maxPrepMs) {
                setPrep({
                    status: 'failed',
                    progress_pct: 0,
                    error_message: 'Video prep timed out — try again or refresh the post.',
                });
                return;
            }
            try {
                const res = await analyticsFetch<VideoPrepResponse>(
                    `/api/analytics/posts/${post.id}/prepare-video`,
                    { method: 'POST', skipProjectScope: true },
                );
                if (cancelled) return;
                setPrep(res);
                if (res.status === 'ready' && res.storage_video_url) {
                    // Patch the post in-place so directVideoUrl below picks
                    // up the mirrored URL and the iframe is replaced.
                    setPost((prev) =>
                        prev ? { ...prev, storage_video_url: res.storage_video_url ?? undefined } : prev,
                    );
                    return;
                }
                if (res.status === 'failed') return;
                elapsed += pollInterval;
                window.setTimeout(poll, pollInterval);
            } catch (e) {
                if (cancelled) return;
                setPrep({
                    status: 'failed',
                    progress_pct: 0,
                    error_message: e instanceof Error ? e.message : 'Video prep failed',
                });
            }
        };

        // Kick off the first call immediately so the spinner is responsive.
        poll();
        return () => {
            cancelled = true;
        };
    }, [post?.id]);  // eslint-disable-line react-hooks/exhaustive-deps

    /* Poll while a breakdown is running */
    useEffect(() => {
        if (!breakdown || (breakdown.status !== 'pending' && breakdown.status !== 'running')) return;
        let cancelled = false;
        let delay = 3000;
        let elapsed = 0;
        const maxTotal = 5 * 60 * 1000;

        const tick = async () => {
            if (cancelled) return;
            try {
                const next = await analyticsFetch<AnalyticsBreakdown>(
                    `/api/analytics/breakdowns/${breakdown.id}`,
                    { skipProjectScope: true },
                );
                if (cancelled) return;
                setBreakdown(next);
                if (next.status === 'completed' || next.status === 'failed') return;
            } catch {
                // swallow; we'll retry next tick
            }
            elapsed += delay;
            if (elapsed >= maxTotal) {
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
    }, [breakdown]);

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

    useEffect(() => {
        autoStudioBreakdownRef.current = false;
    }, [postId]);

    const triggerGenerate = useCallback(async () => {
        if (!post) return;
        setGenerating(true);
        try {
            const body: Record<string, string> = {};
            if (post.source === 'internal' && post.video_job_id) {
                body.video_job_id = post.video_job_id;
            } else {
                body.analytics_post_id = post.id;
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
            const message = e instanceof Error ? e.message : 'Failed to start AI breakdown.';
            setBreakdown({
                id: breakdown?.id || 'pending-error',
                status: 'failed',
                error_message: message,
            });
        } finally {
            setGenerating(false);
        }
    }, [post, breakdown?.id]);

    /* Studio-published videos — kick off AI breakdown automatically when
     * the modal opens and no completed analysis exists yet. */
    useEffect(() => {
        if (autoStudioBreakdownRef.current || loading || generating) return;
        if (!post || post.source !== 'internal' || !post.video_job_id) return;
        if (
            breakdown?.status === 'completed'
            || breakdown?.status === 'pending'
            || breakdown?.status === 'running'
        ) return;
        const ready =
            !!post.storage_video_url
            || !!post.video_job_id
            || prep?.status === 'ready';
        if (!ready) return;
        autoStudioBreakdownRef.current = true;
        triggerGenerate();
    }, [post, breakdown, loading, generating, prep?.status, triggerGenerate]);

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
        const pid = post.external_post_id || '';
        const postUrl = post.post_url || '';
        if (platform === 'instagram' && pid) {
            return `https://www.instagram.com/p/${encodeURIComponent(pid)}/embed/`;
        }
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
    // Internal/UGC posts can be analyzed via video_job_id directly (no mirror
    // required). External posts must wait for the prep pipeline to populate a
    // downloadable URL — otherwise Gemini will 422.
    const videoReadyForAnalysis =
        !!post && (
            (post.source === 'internal' && !!post.video_job_id) ||
            !!post.storage_video_url ||
            prep?.status === 'ready'
        );
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

    /**
     * Route the user to the Create flow with the analyzed post's content
     * surfaced as a starting point. We forward:
     *   • caption — pre-fills the custom-script textarea
     *   • hook    — passed separately so future iterations can use it as
     *               a script-generation seed
     *   • platform / source — for analytics attribution on the new draft
     *   • templatePostId — server-side hook for richer prefill (we only
     *                      consume `customScript` today, but keeping the
     *                      ID around lets us upgrade without changing
     *                      callers later).
     *
     * The caption alone is rarely enough to pre-fill a script, so we also
     * concatenate the AI hook + summary + takeaways when present — gives
     * the user a richer brief to riff off in the Create wizard.
     */
    const handleUseAsTemplate = useCallback(() => {
        if (!post) return;
        const sections: string[] = [];
        if (breakdown?.hook?.on_screen_text) {
            sections.push(`Hook:\n${breakdown.hook.on_screen_text}`);
        } else if (breakdown?.hook?.visual) {
            sections.push(`Hook:\n${breakdown.hook.visual}`);
        }
        if (post.caption) {
            sections.push(`Caption:\n${post.caption}`);
        }
        if (breakdown?.summary) {
            sections.push(`Summary:\n${breakdown.summary}`);
        }
        if (breakdown?.takeaways?.length) {
            sections.push(`Takeaways:\n${breakdown.takeaways.map((t) => `• ${t}`).join('\n')}`);
        }
        const customScript = sections.join('\n\n').trim();

        const params = new URLSearchParams();
        if (customScript) params.set('customScript', customScript);
        params.set('templatePostId', post.id);
        if (post.platform) params.set('templatePlatform', post.platform);
        if (post.source) params.set('templateSource', post.source);
        router.push(`/create?${params.toString()}`);
        onClose();
    }, [post, breakdown, router, onClose]);

    return (
        <div
            onClick={onClose}
            style={{
                position: 'fixed', inset: 0,
                background: 'rgba(13,27,62,0.55)',
                backdropFilter: 'blur(6px)',
                // 10000 — must sit above AccountDetailModal (9999, via
                // shared `Modal` primitive). When a user drills down from
                // the account modal into a post, the post needs to win
                // the stacking battle regardless of render order.
                zIndex: 10000,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                padding: '24px',
                animation: 'analytics-modal-fade 0.18s ease-out',
            }}
        >
            <div
                onClick={(e) => e.stopPropagation()}
                className="analytics-modal-shell"
                style={{
                    background: 'white',
                    borderRadius: 'var(--radius)',
                    boxShadow: 'var(--shadow-lg)',
                    width: '100%',
                    maxWidth: 980,
                    maxHeight: '92vh',
                    display: 'flex',
                    flexDirection: 'column',
                    overflow: 'hidden',
                }}
            >
                {/* Header */}
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
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
                        <span
                            style={{
                                fontSize: '11px', fontWeight: 700,
                                padding: '3px 10px', borderRadius: '999px',
                                background: `${platformAccent}1F`,
                                color: platformAccent,
                                textTransform: 'uppercase',
                            }}
                        >
                            {post?.platform || '—'}
                        </span>
                        <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-1)', whiteSpace: 'nowrap' }}>
                            @{post?.username || '—'}
                        </span>
                        <span style={{ fontSize: '12px', color: 'var(--text-3)' }}>
                            {post && timeAgo(post.posted_at || post.scraped_at)}
                        </span>
                    </div>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                        {post && !loading && (
                            <button
                                type="button"
                                onClick={handleUseAsTemplate}
                                title={t('analytics.detail.template.hint')}
                                style={{
                                    fontSize: '12px',
                                    fontWeight: 700,
                                    color: 'white',
                                    padding: '6px 12px',
                                    borderRadius: '8px',
                                    border: '1px solid #34D399',
                                    background: 'linear-gradient(135deg, #34D399 0%, #2DD4BF 100%)',
                                    cursor: 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
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
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    color: 'var(--text-1)',
                                    padding: '6px 12px',
                                    borderRadius: '8px',
                                    border: '1px solid var(--border)',
                                    background: 'white',
                                    cursor: exportingPdf ? 'wait' : 'pointer',
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
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
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    color: 'var(--blue)',
                                    textDecoration: 'none',
                                    padding: '6px 12px',
                                    borderRadius: '8px',
                                    border: '1px solid var(--border)',
                                    background: 'white',
                                }}
                            >
                                {t('analytics.detail.viewOriginal')}
                            </a>
                        )}
                        <button
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
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                                <line x1="18" y1="6" x2="6" y2="18" />
                                <line x1="6" y1="6" x2="18" y2="18" />
                            </svg>
                        </button>
                    </div>
                </div>

                {/* Body.
                 *
                 * `flex: 1, minHeight: 0` is the classic flex+scroll pattern:
                 * the body claims the remaining height inside the
                 * column-flex shell, and `minHeight: 0` lets it shrink below
                 * its intrinsic content height (without that, `overflowY:
                 * auto` does nothing because the body just keeps growing).
                 *
                 * The `analytics-modal-body` class pairs with a global
                 * `> * { flex-shrink: 0 }` rule below — that stops the
                 * aspect-ratio video wrapper from getting compressed when
                 * the AI breakdown content arrives and pushes total height
                 * past 92vh. Without it, flex column distributes the
                 * overflow across all children proportionally, which is
                 * what was cropping the video to a thin strip.
                 */}
                <div
                    className="analytics-modal-body"
                    style={{
                        flex: 1,
                        minHeight: 0,
                        overflowY: 'auto',
                        padding: '18px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '18px',
                    }}
                >
                    {loading || !post ? (
                        <div style={{ color: 'var(--text-3)', fontSize: '13px', padding: '40px', textAlign: 'center' }}>
                            {t('common.loading')}
                        </div>
                    ) : (
                        <>
                            {/* Hero video / embed.
                             *
                             * Two very different sizing regimes:
                             *
                             *  • <video> (mirrored / internal): pure video,
                             *    use the natural 9:16 / 16:9 aspect ratio.
                             *
                             *  • <iframe> (platform embed): includes header
                             *    (profile + audio) AND footer (action bar)
                             *    on top of the video — using 9:16 here cuts
                             *    off the bottom and forces an internal
                             *    scrollbar. Each platform gets its own
                             *    chrome-aware ratio so the entire post fits
                             *    without scrolling.
                             *
                             *  We also clamp the wrapper height to the
                             *  available modal body height (`92vh` minus
                             *  approx. header/metrics/caption/breakdown) so
                             *  even the tallest embed never exceeds the
                             *  viewport.
                             */}
                            {(() => {
                                const posterUrl = resolvePostPosterUrl(post);
                                const platform = (post.platform || '').toLowerCase();
                                const isVertical = platform === 'tiktok' || platform === 'instagram';
                                const videoAspect = isVertical ? '9 / 16' : '16 / 9';
                                // Embed aspect ratios account for chrome the
                                // platform injects above/below the video.
                                const embedAspect =
                                    platform === 'instagram' ? '9 / 20' :
                                    platform === 'tiktok'    ? '9 / 20' :
                                    platform === 'facebook'  ? '1 / 1'  :
                                    '16 / 9';

                                const baseWrapper: React.CSSProperties = {
                                    position: 'relative',
                                    background: 'black',
                                    borderRadius: '12px',
                                    overflow: 'hidden',
                                    width: '100%',
                                    margin: isVertical ? '0 auto' : undefined,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                };

                                // 1. Best case: we have a Supabase-mirrored
                                //    URL (or a fresh BrightData CDN URL).
                                //    Play it inline with <video>. This is
                                //    the only way IG/TikTok previews work
                                //    *inside* the app — the platform iframes
                                //    refuse to play outside a logged-in
                                //    session and just deep-link out.
                                if (directVideoUrl) {
                                    return (
                                        <div
                                            style={{
                                                ...baseWrapper,
                                                maxWidth: isVertical ? 380 : '100%',
                                                aspectRatio: videoAspect,
                                            }}
                                        >
                                            <video
                                                ref={videoRef}
                                                src={directVideoUrl}
                                                controls
                                                playsInline
                                                poster={posterUrl}
                                                crossOrigin="anonymous"
                                                onLoadedMetadata={handleVideoLoadedMetadata}
                                                style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                                            />
                                        </div>
                                    );
                                }

                                // 2. Prep in progress — show a thumbnail +
                                //    progress bar instead of an iframe that
                                //    would just deep-link to Instagram.
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
                                            style={{
                                                ...baseWrapper,
                                                maxWidth: isVertical ? 380 : '100%',
                                                aspectRatio: videoAspect,
                                                background: `center / cover no-repeat ${posterUrl ? `url(${JSON.stringify(posterUrl)})` : 'black'}`,
                                            }}
                                        >
                                            {/* Scrim so the progress UI is
                                                always readable over the
                                                poster image. */}
                                            <div
                                                style={{
                                                    position: 'absolute',
                                                    inset: 0,
                                                    background: 'rgba(13,27,62,0.55)',
                                                    backdropFilter: 'blur(2px)',
                                                }}
                                            />
                                            <div
                                                style={{
                                                    position: 'relative',
                                                    zIndex: 1,
                                                    display: 'flex',
                                                    flexDirection: 'column',
                                                    alignItems: 'center',
                                                    gap: '14px',
                                                    padding: '0 24px',
                                                    width: '100%',
                                                    maxWidth: 320,
                                                }}
                                            >
                                                <div
                                                    style={{
                                                        color: 'white',
                                                        fontSize: '13px',
                                                        fontWeight: 600,
                                                        textAlign: 'center',
                                                    }}
                                                >
                                                    {stageLabel}
                                                </div>
                                                <div
                                                    style={{
                                                        width: '100%',
                                                        height: 6,
                                                        borderRadius: 999,
                                                        background: 'rgba(255,255,255,0.18)',
                                                        overflow: 'hidden',
                                                    }}
                                                >
                                                    <div
                                                        style={{
                                                            width: `${pct}%`,
                                                            height: '100%',
                                                            background: 'linear-gradient(90deg, #5B9CFF 0%, #337AFF 100%)',
                                                            borderRadius: 999,
                                                            transition: 'width 0.4s ease',
                                                        }}
                                                    />
                                                </div>
                                                <div
                                                    style={{
                                                        color: 'rgba(255,255,255,0.7)',
                                                        fontSize: '11px',
                                                        textAlign: 'center',
                                                    }}
                                                >
                                                    {t('analytics.detail.prep.takes')}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                }

                                // 3. Prep failed *or* we don't even have a
                                //    post URL to scrape from — fall back to
                                //    the official platform embed so the
                                //    user can at least open the original.
                                if (embedUrl) {
                                    return (
                                        <div
                                            style={{
                                                ...baseWrapper,
                                                background: 'var(--blue-light)',
                                                maxWidth: isVertical ? 340 : '100%',
                                                aspectRatio: embedAspect,
                                                maxHeight: isVertical ? '78vh' : undefined,
                                            }}
                                        >
                                            <iframe
                                                src={embedUrl}
                                                title={`${post.platform} post preview`}
                                                allow="autoplay; encrypted-media; picture-in-picture; clipboard-write"
                                                allowFullScreen
                                                scrolling="no"
                                                referrerPolicy="strict-origin-when-cross-origin"
                                                style={{
                                                    width: '100%',
                                                    height: '100%',
                                                    border: 0,
                                                    display: 'block',
                                                }}
                                            />
                                        </div>
                                    );
                                }
                                return (
                                    <div
                                        style={{
                                            ...baseWrapper,
                                            maxWidth: isVertical ? 380 : '100%',
                                            aspectRatio: videoAspect,
                                        }}
                                    >
                                        <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: '13px' }}>
                                            No media URL captured.
                                        </div>
                                    </div>
                                );
                            })()}

                            {/* Metrics.
                             *
                             * Per-platform quirks baked in:
                             *   • Shares — IG + YouTube don't expose share
                             *     counts at all (BrightData returns null);
                             *     render "Hidden" instead of "—" so users
                             *     understand it's a platform limitation,
                             *     not missing data on our end. TikTok and
                             *     Facebook *do* expose them.
                             *   • Duration — hidden for `image` / `carousel`
                             *     posts since "0s" or "—" is meaningless on
                             *     a static post. For video posts we prefer
                             *     `post.duration_seconds` (from BrightData
                             *     or our backfill endpoint), falling back
                             *     to the value derived locally from the
                             *     `<video>` element's loadedmetadata event.
                             *   • Saves — removed entirely from the grid
                             *     (still contributes to total_engagement
                             *     server-side).
                             */}
                            {(() => {
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
                                const effectiveDuration =
                                    post.duration_seconds ?? derivedDuration;
                                const durationValue = effectiveDuration
                                    ? `${Math.round(effectiveDuration)}s`
                                    : t('analytics.detail.measuring');

                                return (
                                    <div>
                                        <div
                                            style={{
                                                fontSize: '11px',
                                                fontWeight: 700,
                                                textTransform: 'uppercase',
                                                letterSpacing: 0.6,
                                                color: 'var(--text-3)',
                                                marginBottom: '8px',
                                            }}
                                        >
                                            {t('analytics.detail.metrics')}
                                        </div>
                                        <div
                                            style={{
                                                display: 'grid',
                                                gridTemplateColumns: 'repeat(auto-fill, minmax(110px, 1fr))',
                                                gap: '8px',
                                            }}
                                        >
                                            <MetricCell label="Views" value={formatCount(resolveDisplayViews(post))} />
                                            <MetricCell label="Likes" value={formatCount(post.likes)} />
                                            <MetricCell label="Comments" value={formatCount(post.comments)} />
                                            <MetricCell label="Shares" value={sharesValue} />
                                            <MetricCell label="Engagement" value={formatCount(post.total_engagement)} accent />
                                            {!isStaticPost && (
                                                <MetricCell label="Duration" value={durationValue} />
                                            )}
                                        </div>
                                    </div>
                                );
                            })()}

                            {/* Caption */}
                            {post.caption && (
                                <div
                                    style={{
                                        background: 'var(--blue-light)',
                                        borderRadius: '10px',
                                        padding: '10px 12px',
                                        fontSize: '12px',
                                        color: 'var(--text-2)',
                                        lineHeight: 1.5,
                                    }}
                                >
                                    {post.caption}
                                </div>
                            )}

                            {/* AI Breakdown */}
                            <div>
                                <div
                                    style={{
                                        fontSize: '11px',
                                        fontWeight: 700,
                                        textTransform: 'uppercase',
                                        letterSpacing: 0.6,
                                        color: 'var(--text-3)',
                                        marginBottom: '8px',
                                    }}
                                >
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
                                />
                            </div>
                        </>
                    )}
                </div>
            </div>

            <style>{`
                @keyframes analytics-modal-fade {
                    from { opacity: 0; transform: scale(0.98); }
                    to { opacity: 1; transform: scale(1); }
                }
                /* Keep every direct child of the scroll container at its
                   natural height. Without this, flex column would shrink
                   children (including the aspect-ratio video wrapper) when
                   total content exceeds the body's bounded height, which
                   was cropping the video to ~80px once the breakdown
                   loaded. */
                .analytics-modal-body > * {
                    flex-shrink: 0;
                }
                /* Smaller, more polished scrollbar on the body */
                .analytics-modal-body::-webkit-scrollbar { width: 8px; }
                .analytics-modal-body::-webkit-scrollbar-thumb {
                    background: rgba(13,27,62,0.18);
                    border-radius: 999px;
                }
                .analytics-modal-body::-webkit-scrollbar-track {
                    background: transparent;
                }
                @media (max-width: 768px) {
                    .analytics-modal-shell {
                        max-height: 100vh !important;
                        border-radius: 0 !important;
                    }
                }
            `}</style>
        </div>
    );
}
