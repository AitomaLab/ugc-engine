'use client';

/**
 * Analytics module — co-located type re-exports + lightweight fetch hooks.
 *
 * Canonical type definitions live in `@/lib/types`. This file re-exports them
 * so other analytics components can `import { AnalyticsPost } from
 * './analytics-types'` without polluting `lib/types.ts` with React hooks.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch } from '@/lib/utils';
import { clearAllAuthState } from '@/lib/supabaseClient';
import type {
    AccountHealth,
    AnalyticsBreakdown,
    AnalyticsPlatform,
    AnalyticsPost,
    AnalyticsSettings,
    AnalyticsSource,
    ScrapeFrequency,
    SocialConnection,
    TrackedAccount,
    TrackedAccountAggregate,
    TrendPoint,
} from '@/lib/types';

export type {
    AccountHealth,
    AnalyticsBreakdown,
    AnalyticsPlatform,
    AnalyticsPost,
    AnalyticsSettings,
    AnalyticsSource,
    ScrapeFrequency,
    SocialConnection,
    TrackedAccount,
    TrackedAccountAggregate,
    TrendPoint,
};

/**
 * Filter for the Accounts grid:
 *   • all      — every tracked account
 *   • studio   — accounts also linked under `/connections` (i.e. owned by the user)
 *   • external — accounts the user is monitoring but doesn't own
 *
 * Studio classification:
 *   • Primary: server flag `linked_via_connections` (`POST …/sync-studio-connections`).
 *   • Fallback: client-side match of `/api/connections` `(platform,@handle)`
 *     for legacy rows or payloads without a scrape handle yet (Ayrshare
 *     occasionally omits a username until the next `/user` refresh).
 */
export type AccountOwnership = 'all' | 'studio' | 'external';

export const ACCOUNT_OWNERSHIP_OPTIONS: AccountOwnership[] = ['all', 'studio', 'external'];

/** Single source of truth for the orange CTA color used across analytics
 *  v2 surfaces (Add Account, Settings, Scrape Now, Export CSV, etc.).
 *  Matches the spec: "All CTAs must use an orange background with white
 *  text." */
export const ANALYTICS_CTA_ORANGE = '#F97316';
export const ANALYTICS_CTA_ORANGE_HOVER = '#EA580C';

/** Unified primary action color for the Publish / Analytics surface.
 *  Matches the product brand blue (`--blue` = #337AFF) used across the rest
 *  of the UI so every active state (top tabs, time-range pills, chart
 *  toggles, sub-tabs) and the Analyze CTA read as one consistent system.
 *  Semantic colors (positive/negative deltas, success state, platform brand
 *  colors) intentionally stay on their own scales. */
export const ANALYTICS_PRIMARY = '#337AFF';
export const ANALYTICS_PRIMARY_HOVER = '#1A5FD4';
export const ANALYTICS_PRIMARY_SOFT = 'rgba(51,122,255,0.12)';

const VIDEO_URL_RE = /\.(mp4|webm|mov|avi|mkv|m4v)(\?.*)?$/i;

/** True when the URL points at video bytes rather than a poster image. */
export function isVideoMediaUrl(url: string | undefined): boolean {
    if (!url) return false;
    return VIDEO_URL_RE.test(url);
}

const SUPABASE_STORAGE_RE = /\/storage\/v1\/object\/public\//i;

/** True when the post already has a durable Supabase-hosted poster image. */
export function hasStablePostThumbnail(post: AnalyticsPost): boolean {
    const thumb = post.thumbnail_url;
    if (!thumb || isVideoMediaUrl(thumb)) return false;
    return SUPABASE_STORAGE_RE.test(thumb);
}

export function postNeedsThumbnailFetch(post: AnalyticsPost): boolean {
    return !hasStablePostThumbnail(post);
}

/**
 * Best preview source for a post card — prefers a stable image URL and falls
 * back to a playable video URL for `<video preload="metadata">` rendering.
 */
export function resolvePostPreviewUrl(post: AnalyticsPost): {
    previewUrl?: string;
    videoUrl?: string;
} {
    const thumb = post.thumbnail_url;
    if (thumb && !isVideoMediaUrl(thumb)) {
        return { previewUrl: thumb };
    }

    let mediaUrl: string | undefined;
    if (Array.isArray(post.media_urls)) {
        for (const item of post.media_urls) {
            if (typeof item === 'string' && item) {
                mediaUrl = item;
                break;
            }
            if (item && typeof item === 'object' && 'url' in item && item.url) {
                mediaUrl = item.url;
                break;
            }
        }
    }

    if (mediaUrl && !isVideoMediaUrl(mediaUrl)) {
        return { previewUrl: mediaUrl };
    }

    const videoUrl =
        post.storage_video_url
        || (mediaUrl && isVideoMediaUrl(mediaUrl) ? mediaUrl : undefined)
        || (thumb && isVideoMediaUrl(thumb) ? thumb : undefined);

    return videoUrl ? { videoUrl } : {};
}

/** Stable image poster for `<img>` / CSS backgrounds (never a raw .mp4 URL). */
export function resolvePostPosterUrl(post: AnalyticsPost): string | undefined {
    return resolvePostPreviewUrl(post).previewUrl;
}

/**
 * Pick the best preview across multiple platform copies of the same upload.
 * Prefers a stable image poster, then falls back to a playable video URL so
 * `VideoThumbnail` can render the first frame.
 */
export function pickBestPostPreview(
    posts: AnalyticsPost[],
): { previewUrl?: string; videoUrl?: string } {
    let videoFallback: { previewUrl?: string; videoUrl?: string } | undefined;
    for (const p of posts) {
        const resolved = resolvePostPreviewUrl(p);
        if (resolved.previewUrl) return resolved;
        if (!videoFallback?.videoUrl && resolved.videoUrl) {
            videoFallback = resolved;
        }
    }
    return videoFallback ?? {};
}

/**
 * Best-effort view count for display — prefers native views, then IG funnel
 * metrics (impressions / reach) when the platform doesn't expose plays.
 */
export function resolveDisplayViews(post: AnalyticsPost): number | null | undefined {
    if (post.views != null && post.views > 0) return post.views;
    if (post.impressions != null && post.impressions > 0) return post.impressions;
    if (post.reach != null && post.reach > 0) return post.reach;
    return post.views;
}

export const SCRAPE_FREQUENCY_OPTIONS: ScrapeFrequency[] = [
    'manual', 'hourly', '6h', '12h', 'daily', 'weekly',
];

/* ── Auth-aware fetch wrapper ─────────────────────────────────────────────
 * The backend returns 401 ("Authentication required.") when the Supabase JWT
 * is missing or expired. The browser still has a stale `sb-…-auth-token`
 * cookie, so the middleware lets the page render — but every analytics call
 * fails. Detect that case once here and bounce the user to /login with a
 * `redirectTo` so they land back on Publish after re-auth.
 */
let _redirecting = false;
async function _handleAuthError(): Promise<void> {
    if (_redirecting || typeof window === 'undefined') return;
    _redirecting = true;
    const here = window.location.pathname + window.location.search;
    try {
        await clearAllAuthState();
    } finally {
        window.location.replace(`/login?redirectTo=${encodeURIComponent(here)}`);
    }
}

function _isAuthError(err: unknown): boolean {
    const msg = err instanceof Error ? err.message : String(err);
    return /^Authentication required|Invalid or expired token|API error: 401/i.test(msg);
}

export async function analyticsFetch<T>(
    path: string,
    options?: Parameters<typeof apiFetch>[1],
): Promise<T> {
    try {
        return await apiFetch<T>(path, options);
    } catch (err) {
        if (_isAuthError(err)) {
            await _handleAuthError();
            throw new Error('Session expired — redirecting to login.');
        }
        throw err;
    }
}

export interface ScrapeJobPollResponse {
    job_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    posts_found: number;
    error_message?: string | null;
}
export async function pollScrapeJob(
    jobId: string,
    opts?: { maxMs?: number; intervalMs?: number },
): Promise<ScrapeJobPollResponse> {
    const maxMs = opts?.maxMs ?? 10 * 60 * 1000;
    const intervalMs = opts?.intervalMs ?? 3000;
    const start = Date.now();
    while (Date.now() - start < maxMs) {
        const res = await analyticsFetch<ScrapeJobPollResponse>(
            `/api/analytics/scrape-jobs/${jobId}`,
            { skipProjectScope: true },
        );
        if (res.status === 'completed' || res.status === 'failed') {
            return res;
        }
        await new Promise((resolve) => window.setTimeout(resolve, intervalMs));
    }
    throw new Error('Scrape timed out — BrightData is still processing. Try again shortly.');
}

export type Period = '7d' | '30d' | '90d' | 'quarter' | 'all';

/** Aliases mapping `quarter` → backend's existing `90d`. Lets the FE expose
 *  the friendly label without the API needing to learn a new period code. */
export function periodToApiParam(period: Period): string {
    return period === 'quarter' ? '90d' : period;
}

export const DASHBOARD_PERIODS: Period[] = ['7d', '30d', 'quarter'];
export type PlatformFilter = 'all' | AnalyticsPlatform;
export type SourceFilter = 'all' | AnalyticsSource;
/**
 * Full v2 sort set, mirroring the Aitoma reference: highest engagement,
 * most views, most likes, most comments, most recent. `hasBreakdown` is
 * kept as a hidden option for power users / URL deep-links but no longer
 * appears in the sort dropdown.
 */
export type SortKey = 'engagement' | 'views' | 'likes' | 'comments' | 'recent' | 'hasBreakdown';

/** Sort options actually rendered in the dropdown (in display order). */
export const SORT_OPTIONS: SortKey[] = ['engagement', 'views', 'likes', 'comments', 'recent'];

/**
 * Account filter — `null` means "All accounts" (no filter applied). When
 * set, the value carries both username and platform so the backend can
 * scope posts to that exact (platform, username) tuple.
 */
export type AccountFilter = { platform: AnalyticsPlatform; username: string } | null;

export interface DistributionEntry {
    key: string;
    value: number;
    posts: number;
}

export interface AnalyticsStats {
    total_views: number;
    total_engagement: number;
    avg_engagement_rate: number;
    posts_tracked: number;
    posts_total?: number;
    views_delta_pct: number;
    engagement_delta_pct: number;
    posts_delta_pct: number;
    daily_views: number[];
    daily_engagement: number[];
    daily_posts: number[];
    platform_distribution: DistributionEntry[];
    content_type_distribution: DistributionEntry[];
}

export interface CumulativePoint {
    date: string;
    views: number;
    engagement: number;
    posts: number;
}

export interface CumulativeStatsResponse {
    points: CumulativePoint[];
    total_views: number;
    total_engagement: number;
    total_posts: number;
}

export interface PostsListResponse {
    items: AnalyticsPost[];
    next_cursor: string | null;
}

export interface ScrapeResponse {
    job_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
    posts: AnalyticsPost[];
    tracked_account: TrackedAccount | null;
    error_message?: string;
}

export interface TrackedAccountWithJob {
    account: TrackedAccount;
    job_id: string | null;
    status: 'pending' | 'running' | 'completed' | 'failed';
    posts: AnalyticsPost[];
    error_message?: string;
}

export interface PostDetailResponse {
    post: AnalyticsPost;
    breakdown: AnalyticsBreakdown | null;
}

export interface AnalyzeVideoResponse {
    breakdown_id: string;
    status: 'pending' | 'running' | 'completed' | 'failed';
}

/**
 * Lazy-mirror status returned by `POST /api/analytics/posts/{id}/prepare-video`.
 * Anything except `ready` / `failed` is in-progress and the modal should poll.
 */
export type VideoPrepStatus = 'ready' | 'queued' | 'scraping' | 'downloading' | 'failed';

export interface VideoPrepResponse {
    status: VideoPrepStatus;
    progress_pct: number;
    storage_video_url?: string | null;
    error_message?: string | null;
}

/* ── Hooks ────────────────────────────────────────────────────────────── */

export interface UseAnalyticsPostsArgs {
    period: Period;
    platform: PlatformFilter;
    source: SourceFilter;
    sort: SortKey;
    q: string;
    account?: AccountFilter;
}

/**
 * Lists analytics posts with cursor pagination.
 *
 * Page size policy:
 *   • Account chip active → 20 (matches the "latest 20 with Load more" UX
 *     spec for the account-detail view).
 *   • Otherwise           → 60 (overview grid; keeps the initial fetch fast
 *     while still showing enough to feel populated).
 *
 * `loadMore()` appends the next page using `next_cursor` from the backend
 * response. `refetch()` always resets to page 1 — used by the parent after
 * scrape / tracked-account changes.
 */
export function useAnalyticsPosts(args: UseAnalyticsPostsArgs) {
    const [items, setItems] = useState<AnalyticsPost[]>([]);
    const [loading, setLoading] = useState(true);
    const [loadingMore, setLoadingMore] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [nextCursor, setNextCursor] = useState<string | null>(null);

    const accountKey = args.account
        ? `${args.account.platform}:${args.account.username}`
        : '';
    const pageSize = args.account ? 20 : 60;

    const buildParams = useCallback(
        (cursor: string | null) => {
            // When an account chip is active, force-scope platform to that
            // account's platform so the backend filter is internally
            // consistent (the user can never accidentally request "all
            // platforms" + "username=foo" — that shape is meaningless
            // because usernames aren't globally unique).
            const effectivePlatform = args.account ? args.account.platform : args.platform;
            const params = new URLSearchParams({
                period: periodToApiParam(args.period),
                platform: effectivePlatform,
                source: args.source,
                sort: args.sort,
                limit: String(pageSize),
            });
            if (args.account) params.set('username', args.account.username);
            if (args.q.trim()) params.set('q', args.q.trim());
            if (cursor) params.set('cursor', cursor);
            return params;
        },
        [args.period, args.platform, args.source, args.sort, args.q, args.account, pageSize],
    );

    const fetchPosts = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const data = await analyticsFetch<PostsListResponse>(
                `/api/analytics/posts?${buildParams(null).toString()}`,
                { skipProjectScope: true },
            );
            setItems(data.items || []);
            setNextCursor(data.next_cursor || null);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load posts');
            setItems([]);
            setNextCursor(null);
        } finally {
            setLoading(false);
        }
    }, [buildParams]);

    const loadMore = useCallback(async () => {
        if (!nextCursor || loadingMore) return;
        setLoadingMore(true);
        try {
            const data = await analyticsFetch<PostsListResponse>(
                `/api/analytics/posts?${buildParams(nextCursor).toString()}`,
                { skipProjectScope: true },
            );
            // Dedupe by id in case the backend returns an overlapping page
            // (cursor pagination on scraped_at can re-include rows that
            // shifted boundary on a concurrent refresh).
            setItems((prev) => {
                const seen = new Set(prev.map((p) => p.id));
                const merged = [...prev];
                for (const p of data.items || []) {
                    if (!seen.has(p.id)) {
                        seen.add(p.id);
                        merged.push(p);
                    }
                }
                return merged;
            });
            setNextCursor(data.next_cursor || null);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load more posts');
        } finally {
            setLoadingMore(false);
        }
    }, [nextCursor, loadingMore, buildParams]);

    useEffect(() => {
        fetchPosts();
    }, [fetchPosts]);

    /** Optimistically drop a post from the local grid (used by the
     *  PostCard remove action so the card disappears immediately while
     *  the DELETE request is in flight). */
    const removeLocal = useCallback((postId: string) => {
        setItems((prev) => prev.filter((p) => p.id !== postId));
    }, []);

    return {
        items,
        loading,
        loadingMore,
        error,
        refetch: fetchPosts,
        loadMore,
        hasMore: !!nextCursor,
        removeLocal,
    };
}

export function useAnalyticsStats(
    period: Period,
    platform: PlatformFilter,
    source: SourceFilter,
    account?: AccountFilter,
    refreshKey = 0,
) {
    const [data, setData] = useState<AnalyticsStats | null>(null);
    const [loading, setLoading] = useState(true);
    const requestGen = useRef(0);
    const prevAccountKey = useRef('');

    const accountKey = account ? `${account.platform}:${account.username}` : '';
    const scopeKey = `${periodToApiParam(period)}|${platform}|${source}|${accountKey}|${refreshKey}`;

    useEffect(() => {
        let cancelled = false;
        const gen = ++requestGen.current;
        if (prevAccountKey.current !== accountKey) {
            setData(null);
            prevAccountKey.current = accountKey;
        }
        setLoading(true);

        const effectivePlatform = account ? account.platform : platform;
        const params = new URLSearchParams({
            period: periodToApiParam(period),
            platform: effectivePlatform,
            source,
        });
        if (account) params.set('username', account.username);

        (async () => {
            try {
                const res = await analyticsFetch<AnalyticsStats>(
                    `/api/analytics/stats?${params.toString()}`,
                    { skipProjectScope: true },
                );
                if (!cancelled && gen === requestGen.current) setData(res);
            } catch {
                if (!cancelled && gen === requestGen.current) setData(emptyStats());
            } finally {
                if (!cancelled && gen === requestGen.current) setLoading(false);
            }
        })();

        return () => { cancelled = true; };
    // scopeKey encodes period, platform, source, accountKey, refreshKey
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [scopeKey]);

    const reload = useCallback(async () => {
        setLoading(true);
        const effectivePlatform = account ? account.platform : platform;
        const params = new URLSearchParams({
            period: periodToApiParam(period),
            platform: effectivePlatform,
            source,
        });
        if (account) params.set('username', account.username);
        try {
            const res = await analyticsFetch<AnalyticsStats>(
                `/api/analytics/stats?${params.toString()}`,
                { skipProjectScope: true },
            );
            setData(res);
        } catch {
            setData(emptyStats());
        } finally {
            setLoading(false);
        }
    }, [period, platform, source, accountKey, refreshKey, account]);

    return { data, loading, reload };
}

function emptyStats(): AnalyticsStats {
    return {
        total_views: 0,
        total_engagement: 0,
        avg_engagement_rate: 0,
        posts_tracked: 0,
        posts_total: 0,
        views_delta_pct: 0,
        engagement_delta_pct: 0,
        posts_delta_pct: 0,
        daily_views: [],
        daily_engagement: [],
        daily_posts: [],
        platform_distribution: [],
        content_type_distribution: [],
    };
}

/** Cumulative growth — daily running totals fed to the growth chart.
 *  Architecture-reference name. `useCumulativeStats` is kept as an alias
 *  for any in-flight callers that imported the older name. */
export function useAnalyticsCumulative(
    period: Period,
    platform: PlatformFilter,
    source: SourceFilter,
    account?: AccountFilter,
    refreshKey = 0,
) {
    const [data, setData] = useState<CumulativeStatsResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const requestGen = useRef(0);
    const prevAccountKey = useRef('');

    const accountKey = account ? `${account.platform}:${account.username}` : '';
    const scopeKey = `${periodToApiParam(period)}|${platform}|${source}|${accountKey}|${refreshKey}`;

    useEffect(() => {
        let cancelled = false;
        const gen = ++requestGen.current;
        if (prevAccountKey.current !== accountKey) {
            setData(null);
            prevAccountKey.current = accountKey;
        }
        setLoading(true);

        const effectivePlatform = account ? account.platform : platform;
        const params = new URLSearchParams({
            period: periodToApiParam(period),
            platform: effectivePlatform,
            source,
        });
        if (account) params.set('username', account.username);

        (async () => {
            try {
                const res = await analyticsFetch<CumulativeStatsResponse>(
                    `/api/analytics/stats/cumulative?${params.toString()}`,
                    { skipProjectScope: true },
                );
                if (!cancelled && gen === requestGen.current) setData(res);
            } catch {
                if (!cancelled && gen === requestGen.current) {
                    setData({ points: [], total_views: 0, total_engagement: 0, total_posts: 0 });
                }
            } finally {
                if (!cancelled && gen === requestGen.current) setLoading(false);
            }
        })();

        return () => { cancelled = true; };
    // scopeKey encodes period, platform, source, accountKey, refreshKey
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [scopeKey]);

    const reload = useCallback(async () => {
        setLoading(true);
        const effectivePlatform = account ? account.platform : platform;
        const params = new URLSearchParams({
            period: periodToApiParam(period),
            platform: effectivePlatform,
            source,
        });
        if (account) params.set('username', account.username);
        try {
            const res = await analyticsFetch<CumulativeStatsResponse>(
                `/api/analytics/stats/cumulative?${params.toString()}`,
                { skipProjectScope: true },
            );
            setData(res);
        } catch {
            setData({ points: [], total_views: 0, total_engagement: 0, total_posts: 0 });
        } finally {
            setLoading(false);
        }
    }, [period, platform, source, accountKey, refreshKey, account]);

    return { data, loading, reload };
}

/** Backward-compat alias — older callers imported this name. */
export const useCumulativeStats = useAnalyticsCumulative;

/**
 * Subscribes to `/api/analytics/tracked-accounts` and exposes a `bump()` for
 * imperative refetches (e.g. after Add / Refresh / Delete in the manager).
 */
export function useTrackedAccounts() {
    const [accounts, setAccounts] = useState<TrackedAccount[]>([]);
    const [loading, setLoading] = useState(true);

    const reload = useCallback(async () => {
        setLoading(true);
        try {
            const rows = await analyticsFetch<TrackedAccount[]>(
                '/api/analytics/tracked-accounts',
                { skipProjectScope: true },
            );
            setAccounts(rows || []);
        } catch {
            setAccounts([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        reload();
    }, [reload]);

    return { accounts, loading, reload };
}

/* ── v2: accounts dashboard ───────────────────────────────────────────── */

export interface AccountAggregatesResponse {
    accounts: TrackedAccountAggregate[];
    total_accounts: number;
    total_scraped_posts: number;
    avg_health_score: number | null;
}

/**
 * Per-account aggregates for the Accounts view. Uses the same `period` knob
 * as the Posts view so the dashboard tells a consistent story when the user
 * switches between the two tabs.
 */
export function useAccountAggregates(period: Period) {
    const [data, setData] = useState<AccountAggregatesResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const reload = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const res = await analyticsFetch<AccountAggregatesResponse>(
                `/api/analytics/accounts?period=${periodToApiParam(period)}`,
                { skipProjectScope: true },
            );
            setData(res);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load accounts');
            setData({ accounts: [], total_accounts: 0, total_scraped_posts: 0, avg_health_score: null });
        } finally {
            setLoading(false);
        }
    }, [period]);

    useEffect(() => {
        reload();
    }, [reload]);

    return { data, loading, error, reload };
}

export interface AccountTrendResponse {
    account_id: string;
    points: TrendPoint[];
}

/** 30-day (default) engagement / views / posts time-series for one account. */
export function useAccountTrend(accountId: string | null, days = 30, refreshKey = 0) {
    const [data, setData] = useState<AccountTrendResponse | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!accountId) {
            setData(null);
            return;
        }
        let cancelled = false;
        setLoading(true);
        analyticsFetch<AccountTrendResponse>(
            `/api/analytics/accounts/${accountId}/trend?days=${days}`,
            { skipProjectScope: true },
        )
            .then((res) => {
                if (!cancelled) setData(res);
            })
            .catch(() => {
                if (!cancelled) setData({ account_id: accountId, points: [] });
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => { cancelled = true; };
    }, [accountId, days, refreshKey]);

    return { data, loading };
}

export interface AccountTopPostsResponse {
    account_id: string;
    posts: AnalyticsPost[];
    studio_avg_engagement: number | null;
    external_avg_engagement: number | null;
    studio_vs_external_pct: number | null;
}

const topPostsCache = new Map<string, { data: AccountTopPostsResponse; fetchedAt: number }>();
const TOP_POSTS_CACHE_MS = 60_000;

/** Latest posts + Studio-vs-External delta for the account detail modal. */
export function useAccountTopPosts(accountId: string | null, limit = 48, refreshKey = 0) {
    const [data, setData] = useState<AccountTopPostsResponse | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!accountId) {
            setData(null);
            return;
        }
        let cancelled = false;
        const cacheKey = `${accountId}:${limit}`;
        const cached = topPostsCache.get(cacheKey);
        if (cached && refreshKey === 0 && Date.now() - cached.fetchedAt < TOP_POSTS_CACHE_MS) {
            setData(cached.data);
            setLoading(false);
            return;
        }

        setLoading(true);
        analyticsFetch<AccountTopPostsResponse>(
            `/api/analytics/accounts/${accountId}/top-posts?limit=${limit}&sort=recent`,
            { skipProjectScope: true },
        )
            .then((res) => {
                if (!cancelled) {
                    setData(res);
                    topPostsCache.set(cacheKey, { data: res, fetchedAt: Date.now() });
                }
            })
            .catch(() => {
                if (!cancelled) setData({
                    account_id: accountId, posts: [],
                    studio_avg_engagement: null,
                    external_avg_engagement: null,
                    studio_vs_external_pct: null,
                });
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => { cancelled = true; };
    }, [accountId, limit, refreshKey]);

    return { data, loading };
}

export interface EnsureThumbnailsResponse {
    thumbnails: Record<string, string>;
    pending: number;
}

const THUMBNAIL_BATCH_LIMIT = 48;
const THUMBNAIL_RETRY_MS = 10_000;

/**
 * Lazily mirrors / generates stable poster thumbnails for analytics posts
 * whose cards would otherwise show the gray placeholder (expired CDN URLs,
 * video-only reels, missing thumbnail_url rows).
 */
export function useAnalyticsPostThumbnails(posts: AnalyticsPost[]) {
    const [thumbMap, setThumbMap] = useState<Record<string, string>>({});
    const inFlight = useRef<Set<string>>(new Set());
    const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
    const postsRef = useRef(posts);
    postsRef.current = posts;
    const postIdsKey = posts.map((p) => p.id).join(',');

    const fetchThumbnails = useCallback(async (candidates: AnalyticsPost[]) => {
        const need = candidates
            .filter((p) => p.id && postNeedsThumbnailFetch(p) && !inFlight.current.has(p.id))
            .slice(0, THUMBNAIL_BATCH_LIMIT);
        if (!need.length) return;

        need.forEach((p) => inFlight.current.add(p.id));

        try {
            const res = await analyticsFetch<EnsureThumbnailsResponse>(
                '/api/analytics/posts/ensure-thumbnails',
                {
                    method: 'POST',
                    body: JSON.stringify({ post_ids: need.map((p) => p.id) }),
                    skipProjectScope: true,
                },
            );
            if (res?.thumbnails && Object.keys(res.thumbnails).length > 0) {
                setThumbMap((prev) => ({ ...prev, ...res.thumbnails }));
            }
            if (res?.pending > 0) {
                if (retryTimer.current) clearTimeout(retryTimer.current);
                retryTimer.current = setTimeout(() => {
                    need.forEach((p) => inFlight.current.delete(p.id));
                    fetchThumbnails(need);
                }, THUMBNAIL_RETRY_MS);
            }
        } catch {
            need.forEach((p) => inFlight.current.delete(p.id));
        }
    }, []);

    useEffect(() => {
        fetchThumbnails(postsRef.current);
        return () => {
            if (retryTimer.current) clearTimeout(retryTimer.current);
        };
    }, [postIdsKey, fetchThumbnails]);

    return thumbMap;
}

export interface AccountStrategyReportResponse {
    account_id: string;
    report: string | null;
    generated_at: string | null;
}

/** Latest AI "Do More / Do Less" strategy report for the account detail modal.
 *  A null `report` means it hasn't been generated yet (produced async after a
 *  refresh) — callers should treat that as a pending state. */
export function useAccountStrategyReport(accountId: string | null, refreshKey = 0) {
    const [data, setData] = useState<AccountStrategyReportResponse | null>(null);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        if (!accountId) {
            setData(null);
            return;
        }
        let cancelled = false;
        setLoading(true);
        analyticsFetch<AccountStrategyReportResponse>(
            `/api/analytics/tracked-accounts/${accountId}/strategy-report`,
            { skipProjectScope: true },
        )
            .then((res) => {
                if (!cancelled) setData(res);
            })
            .catch(() => {
                if (!cancelled) {
                    setData({ account_id: accountId, report: null, generated_at: null });
                }
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => { cancelled = true; };
    }, [accountId, refreshKey]);

    return { data, loading };
}

/** Remove a single analytics post from the user's tracked set. Best-effort:
 *  swallows the error so the calling component can roll back its
 *  optimistic state without leaking a stack trace. */
export async function deleteAnalyticsPost(postId: string): Promise<boolean> {
    try {
        await analyticsFetch<{ ok: boolean }>(
            `/api/analytics/posts/${postId}`,
            { method: 'DELETE', skipProjectScope: true },
        );
        return true;
    } catch {
        return false;
    }
}

/** Remove a tracked account (and stop scraping it). Mirror of
 *  `deleteAnalyticsPost` so both card types share a single delete
 *  surface. The backend route already exists at
 *  `DELETE /api/analytics/tracked-accounts/{id}`. */
export async function deleteTrackedAccount(accountId: string): Promise<boolean> {
    try {
        await analyticsFetch<{ ok: boolean }>(
            `/api/analytics/tracked-accounts/${accountId}`,
            { method: 'DELETE', skipProjectScope: true },
        );
        return true;
    } catch {
        return false;
    }
}

/**
 * Subscribes to `/api/connections` (Ayrshare) and exposes a memoised
 * `(platform, username)` lookup used by the Accounts view to classify
 * tracked accounts as Studio vs External.
 *
 * `connectionPlatforms` is a separate Set so we can still classify
 * connections that didn't return a username (legacy Ayrshare payloads
 * sometimes do this) — in that case any tracked account on the matching
 * platform is treated as Studio.
 */
interface ConnectionsResponse {
    socials: SocialConnection[];
}

export function useConnections() {
    const [connections, setConnections] = useState<SocialConnection[]>([]);
    const [loading, setLoading] = useState(true);

    const reload = useCallback(async () => {
        setLoading(true);
        try {
            const res = await analyticsFetch<ConnectionsResponse>('/api/connections', {
                skipProjectScope: true,
            });
            setConnections(res?.socials || []);
        } catch {
            setConnections([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        reload();
    }, [reload]);

    const { keyed, platformsOnly } = useMemo(() => {
        const keyed = new Set<string>();
        const platformsOnly = new Set<string>();
        for (const c of connections) {
            const platform = (c.platform || '').trim().toLowerCase();
            if (!platform) continue;
            const username = (c.username || '').trim().replace(/^@/, '').toLowerCase();
            if (username) keyed.add(`${platform}:${username}`);
            else platformsOnly.add(platform);
        }
        return { keyed, platformsOnly };
    }, [connections]);

    const isStudio = useCallback(
        (platform: string, username: string): boolean => {
            const p = (platform || '').trim().toLowerCase();
            const u = (username || '').trim().replace(/^@/, '').toLowerCase();
            if (!p || !u) return false;
            if (keyed.has(`${p}:${u}`)) return true;
            return platformsOnly.has(p);
        },
        [keyed, platformsOnly],
    );

    const profilePicFor = useCallback(
        (platform: string, username: string): string | undefined => {
            const p = (platform || '').trim().toLowerCase();
            const u = (username || '').trim().replace(/^@/, '').toLowerCase();
            if (!p || !u) return undefined;
            const exact = connections.find(
                (c) =>
                    (c.platform || '').trim().toLowerCase() === p
                    && (c.username || '').trim().replace(/^@/, '').toLowerCase() === u
                    && c.profilePic,
            );
            return exact?.profilePic;
        },
        [connections],
    );

    return { connections, isStudio, profilePicFor, loading, reload };
}

/** Tenant-level analytics settings (defaults + cost alerts). */
export function useAnalyticsSettings() {
    const [data, setData] = useState<AnalyticsSettings | null>(null);
    const [loading, setLoading] = useState(true);

    const reload = useCallback(async () => {
        setLoading(true);
        try {
            const res = await analyticsFetch<AnalyticsSettings>(
                '/api/analytics/settings',
                { skipProjectScope: true },
            );
            setData(res);
        } catch {
            setData(null);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        reload();
    }, [reload]);

    return { data, loading, reload };
}

/**
 * Builds a fully-qualified URL to the CSV export endpoint with the current
 * filter state baked in as query params. Used by the "Export CSV" button —
 * we hand the URL to a hidden anchor + click() instead of fetching the
 * blob in JS so the browser handles auth-cookie attachment and the user
 * sees a normal "downloading…" indicator.
 */
export function buildCsvExportUrl(args: UseAnalyticsPostsArgs): string {
    const effectivePlatform = args.account ? args.account.platform : args.platform;
    const params = new URLSearchParams({
        period: periodToApiParam(args.period),
        platform: effectivePlatform,
        source: args.source,
        sort: args.sort,
    });
    if (args.account) params.set('username', args.account.username);
    if (args.q.trim()) params.set('q', args.q.trim());
    // Backend lives under /api — apiFetch prefixes API_URL but for a direct
    // download we need the full URL. Matches the fallback used in lib/utils.
    const base = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    return `${base}/api/analytics/export/csv?${params.toString()}`;
}

/** Fired after a successful studio ↔ analytics sync (login, connect, schedule). */
export const ANALYTICS_STUDIO_SYNCED_EVENT = 'analyticsStudioSynced';

/**
 * Mirror OAuth connections into tracked accounts, sync scheduled/posted Studio
 * content into analytics_posts, refresh metrics, and queue AI breakdowns.
 */
export async function syncStudioConnections(): Promise<void> {
    await analyticsFetch('/api/analytics/sync-studio-connections', {
        method: 'POST',
        skipProjectScope: true,
    });
    if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent(ANALYTICS_STUDIO_SYNCED_EVENT));
    }
}

/* ── Formatting helpers ───────────────────────────────────────────────── */

export function formatCount(n: number | null | undefined): string {
    if (n === null || n === undefined) return '—';
    if (n >= 1_000_000) return (n / 1_000_000).toFixed(n >= 10_000_000 ? 0 : 1) + 'M';
    if (n >= 1_000) return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + 'K';
    return String(n);
}

export function timeAgo(iso: string | null | undefined): string {
    if (!iso) return '—';
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return '—';
    const diff = Math.max(0, Date.now() - then);
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 60) return `${minutes}m ago`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    const months = Math.floor(days / 30);
    if (months < 12) return `${months}mo ago`;
    return `${Math.floor(months / 12)}y ago`;
}

export function timestampToSeconds(ts: string | null | undefined): number {
    if (!ts) return 0;
    const trimmed = ts.trim().split('-')[0].trim();
    const parts = trimmed.split(':').map((p) => parseInt(p, 10));
    if (parts.some((p) => Number.isNaN(p))) return 0;
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    return parts[0] || 0;
}
