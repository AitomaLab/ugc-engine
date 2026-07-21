'use client';

import { useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import PostCard from '../PostCard';
import type { AnalyticsPost } from '../analytics-types';
import { Section } from './AccountUiKit';

interface Props {
    posts: AnalyticsPost[];
    loading: boolean;
    isRefreshing: boolean;
    thumbMap: Record<string, string>;
    onOpenPost: (postId: string) => void;
}

const GRID_STEP = 16;

/** Account-scope "Videos" tab — the account's posts as full-size clickable cards. */
export default function AccountVideosGrid({ posts, loading, isRefreshing, thumbMap, onOpenPost }: Props) {
    const { t } = useTranslation();
    const [visibleCount, setVisibleCount] = useState(GRID_STEP);

    const visiblePosts = posts.slice(0, visibleCount);
    const hasMore = posts.length > visiblePosts.length;

    return (
        <Section
            title={t('analytics.accounts.topPosts.title')}
            subtitle={
                posts.length > 0
                    ? t('analytics.accounts.topPosts.loadedCount')
                        .replace('{shown}', String(visiblePosts.length))
                        .replace('{total}', String(posts.length))
                    : undefined
            }
        >
            {loading && posts.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                    {isRefreshing ? t('analytics.accounts.refreshingPosts') : t('common.loading')}
                </div>
            ) : posts.length === 0 ? (
                <div style={{ fontSize: 12, color: 'var(--text-3)' }}>
                    {isRefreshing ? t('analytics.accounts.refreshingPosts') : t('analytics.accounts.topPosts.empty')}
                </div>
            ) : (
                <>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 12 }}>
                        {visiblePosts.map((p) => (
                            <PostCard key={p.id} post={p} thumbnailUrl={thumbMap[p.id]} onOpen={onOpenPost} />
                        ))}
                    </div>
                    {hasMore && (
                        <button
                            type="button"
                            onClick={() => setVisibleCount((n) => n + GRID_STEP)}
                            style={{
                                alignSelf: 'center',
                                marginTop: 4,
                                padding: '7px 16px',
                                borderRadius: 8,
                                border: '1px solid var(--border)',
                                background: 'white',
                                color: 'var(--text-2)',
                                fontSize: 12,
                                fontWeight: 600,
                                cursor: 'pointer',
                            }}
                        >
                            {t('analytics.accounts.topPosts.loadMore')}
                        </button>
                    )}
                </>
            )}
        </Section>
    );
}
