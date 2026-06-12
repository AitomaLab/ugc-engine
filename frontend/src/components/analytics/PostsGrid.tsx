'use client';

import { useTranslation } from '@/lib/i18n';
import PostCard from './PostCard';
import { useAnalyticsPostThumbnails, type AnalyticsPost, type TrackedAccount } from './analytics-types';

interface Props {
    posts: AnalyticsPost[];
    loading: boolean;
    onOpen: (postId: string) => void;
    /**
     * Optional cursor-pagination controls. When `hasMore` is true the grid
     * renders a "Load more" button beneath the cards; clicking it calls
     * `onLoadMore`. `loadingMore` toggles the button into its busy state.
     * Omit all three to render a simple, non-paginating grid.
     */
    hasMore?: boolean;
    loadingMore?: boolean;
    onLoadMore?: () => void;
    /** Passed through to PostCard so each card can derive a virality score. */
    trackedAccounts?: TrackedAccount[];
    /** Optional remove handler — forwarded to each PostCard. */
    onDelete?: (postId: string) => void;
}

function GridSkeleton() {
    return (
        <div
            style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
                gap: '16px',
            }}
        >
            {Array.from({ length: 8 }).map((_, i) => (
                <div
                    key={i}
                    style={{
                        background: 'white',
                        border: '1px solid var(--border)',
                        borderRadius: 'var(--radius)',
                        overflow: 'hidden',
                    }}
                >
                    <div
                        style={{
                            width: '100%',
                            paddingTop: '56.25%',
                            background:
                                'linear-gradient(90deg, rgba(51,122,255,0.06) 0%, rgba(51,122,255,0.14) 50%, rgba(51,122,255,0.06) 100%)',
                            backgroundSize: '200% 100%',
                            animation: 'shimmer 1.6s ease-in-out infinite',
                        }}
                    />
                    <div style={{ padding: '12px 14px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <div style={{ height: 12, width: '50%', background: 'var(--blue-light)', borderRadius: 4 }} />
                        <div style={{ height: 10, width: '85%', background: 'var(--blue-light)', borderRadius: 4 }} />
                        <div style={{ height: 28, width: '100%', background: 'var(--blue-light)', borderRadius: 4, marginTop: 4 }} />
                    </div>
                </div>
            ))}
        </div>
    );
}

function EmptyState() {
    const { t } = useTranslation();
    return (
        <div
            style={{
                background: 'white',
                border: '1px dashed var(--border)',
                borderRadius: 'var(--radius)',
                padding: '60px 24px',
                textAlign: 'center',
                color: 'var(--text-3)',
            }}
        >
            <svg
                viewBox="0 0 24 24"
                style={{
                    width: 38, height: 38,
                    stroke: 'var(--text-3)', fill: 'none', strokeWidth: 1.5,
                    marginBottom: '12px',
                }}
            >
                <circle cx="11" cy="11" r="7" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '6px' }}>
                {t('analytics.empty.title')}
            </div>
            <div style={{ fontSize: '13px', maxWidth: 380, margin: '0 auto' }}>
                {t('analytics.empty.body')}
            </div>
        </div>
    );
}

export default function PostsGrid({
    posts, loading, onOpen,
    hasMore, loadingMore, onLoadMore,
    trackedAccounts, onDelete,
}: Props) {
    const { t } = useTranslation();
    const thumbMap = useAnalyticsPostThumbnails(posts);
    if (loading) return <GridSkeleton />;
    if (!posts.length) return <EmptyState />;
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))',
                    gap: '16px',
                }}
            >
                {posts.map((p) => (
                    <PostCard
                        key={p.id}
                        post={p}
                        thumbnailUrl={thumbMap[p.id]}
                        onOpen={onOpen}
                        trackedAccounts={trackedAccounts}
                        onDelete={onDelete}
                    />
                ))}
            </div>
            {onLoadMore && (
                <div style={{ display: 'flex', justifyContent: 'center' }}>
                    {hasMore ? (
                        <button
                            type="button"
                            onClick={onLoadMore}
                            disabled={loadingMore}
                            style={{
                                padding: '10px 22px',
                                borderRadius: '999px',
                                border: '1px solid var(--border)',
                                background: 'white',
                                color: loadingMore ? 'var(--text-3)' : 'var(--blue)',
                                fontSize: '13px',
                                fontWeight: 700,
                                cursor: loadingMore ? 'not-allowed' : 'pointer',
                                transition: 'background 0.15s ease, color 0.15s ease',
                            }}
                            onMouseEnter={(e) => {
                                if (loadingMore) return;
                                e.currentTarget.style.background = 'var(--blue-light)';
                            }}
                            onMouseLeave={(e) => {
                                e.currentTarget.style.background = 'white';
                            }}
                        >
                            {loadingMore
                                ? t('analytics.posts.loadingMore')
                                : t('analytics.posts.loadMore')}
                        </button>
                    ) : (
                        // Subtle "no more posts" hint only after the user has
                        // explicitly paginated at least once (i.e. the grid
                        // already has more than the initial page worth of
                        // results). Suppresses the message for users whose
                        // first page already covers everything.
                        posts.length > 20 && (
                            <span style={{ fontSize: '12px', color: 'var(--text-3)' }}>
                                {t('analytics.posts.allLoaded')}
                            </span>
                        )
                    )}
                </div>
            )}
        </div>
    );
}
