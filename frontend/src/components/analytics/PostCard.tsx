'use client';

import { useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import VideoThumbnail from '@/components/ui/VideoThumbnail';
import { formatCount, timeAgo, resolvePostPreviewUrl, resolveDisplayViews, type AnalyticsPost, type TrackedAccount } from './analytics-types';

const PLATFORM_COLORS: Record<string, string> = {
    instagram: '#E1306C',
    tiktok:    '#000000',
    youtube:   '#FF0000',
    facebook:  '#1877F2',
};

interface Props {
    post: AnalyticsPost;
    onOpen: (postId: string) => void;
    /** Server-mirrored poster URL — merged over `post.thumbnail_url` when set. */
    thumbnailUrl?: string;
    /**
     * Optional — passed by AnalyticsTab so we can derive a virality score
     * (`total_engagement / follower_count * 100`) for any post whose
     * @username matches a tracked account with a known follower count.
     * Posts without a matching account simply omit the badge.
     */
    trackedAccounts?: TrackedAccount[];
    /**
     * Optional remove handler. When provided, a subtle trash icon
     * appears in the top-right of the card. The parent is expected to
     * optimistically drop the post from its list before/while the API
     * call resolves so the card disappears immediately.
     */
    onDelete?: (postId: string) => void;
    /** Denser layout for account Latest Posts grid. */
    compact?: boolean;
}

const PLATFORM_SHORT: Record<string, string> = {
    instagram: 'IG',
    tiktok: 'TT',
    youtube: 'YT',
    facebook: 'FB',
};

/**
 * Looks up the tracked account that owns `post` (matched by `platform` +
 * `username`). Returns the row when present so callers can pull both the
 * follower count (for the virality score) AND the avatar (for the small
 * identity puck) out of a single lookup, instead of two.
 */
function findOwner(
    post: AnalyticsPost,
    accounts: TrackedAccount[] | undefined,
): TrackedAccount | undefined {
    if (!accounts || !post.username) return undefined;
    return accounts.find(
        (a) => a.platform === post.platform && a.username.toLowerCase() === post.username!.toLowerCase(),
    );
}

function followerCountFromOwner(owner: TrackedAccount | undefined): number | undefined {
    if (!owner) return undefined;
    const followers = owner.follower_count ?? owner.followers;
    return followers && followers > 0 ? followers : undefined;
}

function virialityScore(post: AnalyticsPost, followers: number | undefined): number | null {
    if (!followers) return null;
    const score = (post.total_engagement / followers) * 100;
    return Math.round(score * 10) / 10;
}

export default function PostCard({ post, onOpen, thumbnailUrl, trackedAccounts, onDelete, compact = false }: Props) {
    const { t } = useTranslation();
    const accent = PLATFORM_COLORS[post.platform] || 'var(--text-3)';
    const hasBreakdown = post.breakdown_status === 'completed';
    const owner = findOwner(post, trackedAccounts);
    const followers = followerCountFromOwner(owner);
    const virality = virialityScore(post, followers);
    const avatarUrl = owner?.avatar_url || undefined;
    const [removeHover, setRemoveHover] = useState(false);
    const preview = resolvePostPreviewUrl(
        thumbnailUrl ? { ...post, thumbnail_url: thumbnailUrl } : post,
    );
    const displayViews = resolveDisplayViews(post);
    const platformShort = PLATFORM_SHORT[post.platform] || post.platform.slice(0, 2).toUpperCase();

    const handleRemove = (e: React.MouseEvent) => {
        e.preventDefault();
        e.stopPropagation();
        if (!onDelete) return;
        const handle = post.username ? `@${post.username}` : t('analytics.posts.thisPost');
        const ok = typeof window === 'undefined'
            ? true
            : window.confirm(t('analytics.posts.removeConfirm').replace('{name}', handle));
        if (ok) onDelete(post.id);
    };

    return (
        <button
            onClick={() => onOpen(post.id)}
            style={{
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: compact ? 12 : 'var(--radius)',
                padding: 0,
                cursor: 'pointer',
                textAlign: 'left',
                display: 'flex',
                flexDirection: 'column',
                overflow: 'hidden',
                transition: compact ? 'border-color 0.15s ease' : 'transform 0.18s ease, box-shadow 0.18s ease',
                boxShadow: compact ? 'none' : '0 1px 2px rgba(13,27,62,0.04)',
            }}
            onMouseEnter={(e) => {
                if (compact) {
                    e.currentTarget.style.borderColor = '#D5DEE8';
                    return;
                }
                e.currentTarget.style.transform = 'translateY(-2px)';
                e.currentTarget.style.boxShadow = 'var(--shadow)';
            }}
            onMouseLeave={(e) => {
                if (compact) {
                    e.currentTarget.style.borderColor = '';
                    return;
                }
                e.currentTarget.style.transform = 'translateY(0)';
                e.currentTarget.style.boxShadow = '0 1px 2px rgba(13,27,62,0.04)';
            }}
        >
            {/* Thumbnail */}
            <div
                style={{
                    position: 'relative',
                    width: '100%',
                    paddingTop: compact ? undefined : '56.25%',
                    height: compact ? 112 : undefined,
                    background: 'var(--blue-light)',
                }}
            >
                <VideoThumbnail
                    previewUrl={preview.previewUrl}
                    videoUrl={preview.videoUrl}
                    alt={post.caption || ''}
                />
                {!compact && post.media_type === 'video' && (
                    <div
                        style={{
                            position: 'absolute', top: 10, left: 10,
                            width: 28, height: 28, borderRadius: '50%',
                            background: 'rgba(0,0,0,0.55)',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}
                    >
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
                            <path d="M8 5.14v13.72a1 1 0 001.5.86l11.24-6.86a1 1 0 000-1.72L9.5 4.28A1 1 0 008 5.14z" />
                        </svg>
                    </div>
                )}
                {compact ? (
                    <span
                        title={post.platform}
                        style={{
                            position: 'absolute', left: 8, bottom: 8,
                            display: 'inline-flex', alignItems: 'center', gap: 4,
                            fontSize: 10, fontWeight: 700,
                            padding: '3px 7px', borderRadius: 999,
                            background: 'rgba(15, 23, 42, 0.72)',
                            color: '#FFFFFF',
                            backdropFilter: 'blur(6px)',
                        }}
                    >
                        <span style={{ width: 6, height: 6, borderRadius: 2, background: accent }} aria-hidden />
                        {platformShort}
                    </span>
                ) : (
                    <span
                        style={{
                            position: 'absolute', top: 10, right: 10,
                            fontSize: '10px', fontWeight: 700,
                            padding: '3px 8px', borderRadius: '999px',
                            background: `${accent}1F`,
                            color: accent,
                            textTransform: 'uppercase',
                            backdropFilter: 'blur(4px)',
                        }}
                    >
                        {post.platform}
                    </span>
                )}
                {hasBreakdown && (
                    <span
                        style={{
                            position: 'absolute',
                            bottom: compact ? 8 : 10,
                            right: compact ? 8 : 10,
                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                            fontSize: '10px', fontWeight: 700,
                            padding: '3px 8px', borderRadius: '999px',
                            background: compact ? 'rgba(15,23,42,0.72)' : 'rgba(51,122,255,0.12)',
                            color: compact ? '#FFFFFF' : 'var(--blue)',
                            backdropFilter: 'blur(4px)',
                        }}
                    >
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={3}>
                            <polyline points="20 6 9 17 4 12" />
                        </svg>
                        AI
                    </span>
                )}
                {!compact && post.source === 'internal' && (
                    <span
                        style={{
                            position: 'absolute', bottom: 10, left: 10,
                            fontSize: '10px', fontWeight: 700,
                            padding: '3px 8px', borderRadius: '999px',
                            background: 'rgba(52,199,89,0.16)',
                            color: '#1f7a3a',
                            backdropFilter: 'blur(4px)',
                        }}
                    >
                        UGC
                    </span>
                )}
                {!compact && (displayViews ?? 0) > 0 && (
                    <span
                        style={{
                            position: 'absolute', bottom: 10, right: hasBreakdown ? 72 : 10,
                            fontSize: '10px', fontWeight: 700,
                            padding: '3px 8px', borderRadius: '999px',
                            background: 'rgba(13,27,62,0.72)',
                            color: 'white',
                            backdropFilter: 'blur(4px)',
                        }}
                    >
                        {formatCount(displayViews)} views
                    </span>
                )}
                {!compact && virality !== null && (
                    <span
                        title={`Engagement ${post.total_engagement.toLocaleString()} vs ${followers!.toLocaleString()} followers`}
                        style={{
                            position: 'absolute', top: 38, right: 10,
                            display: 'inline-flex', alignItems: 'center', gap: '4px',
                            fontSize: '10px', fontWeight: 700,
                            padding: '3px 8px', borderRadius: '999px',
                            background: virality >= 10
                                ? 'rgba(255,69,58,0.18)'
                                : virality >= 3
                                ? 'rgba(255,159,10,0.18)'
                                : 'rgba(13,27,62,0.10)',
                            color: virality >= 10
                                ? '#b3261e'
                                : virality >= 3
                                ? '#a35a00'
                                : 'var(--text-2)',
                            backdropFilter: 'blur(4px)',
                        }}
                    >
                        {virality >= 10 ? '🔥' : virality >= 3 ? '✨' : '•'}
                        {virality}%
                    </span>
                )}
            </div>

            {/* Body.
             *
             * `flex: 1` on the body + `marginTop: auto` on the metrics row
             * makes the metrics block sit flush with the bottom of every
             * card, regardless of whether the caption is missing, 1 line,
             * or 2 lines. The caption slot itself is given a fixed two-line
             * height (`minHeight: 34px` ≈ 2 × 17px line-height) — empty
             * captions render an invisible spacer so card heights stay
             * identical across a grid of mixed-caption posts.
             */}
            <div
                style={{
                    flex: 1,
                    padding: compact ? '10px 10px 12px' : '12px 14px 14px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: compact ? 6 : 8,
                }}
            >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 6 }}>
                    {!compact && (
                        avatarUrl ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                                src={avatarUrl}
                                alt=""
                                loading="lazy"
                                style={{
                                    width: 22, height: 22, borderRadius: '50%',
                                    objectFit: 'cover', flexShrink: 0,
                                    border: '1px solid var(--border)',
                                    background: 'var(--blue-light)',
                                }}
                            />
                        ) : post.username ? (
                            <span
                                aria-hidden
                                style={{
                                    width: 22, height: 22, borderRadius: '50%',
                                    display: 'inline-flex', alignItems: 'center',
                                    justifyContent: 'center',
                                    fontSize: 10, fontWeight: 800,
                                    background: `${accent}1F`, color: accent,
                                    border: '1px solid var(--border)',
                                    flexShrink: 0,
                                }}
                            >
                                {post.username.slice(0, 1).toUpperCase()}
                            </span>
                        ) : null
                    )}
                    <span
                        style={{
                            fontSize: compact ? 12 : 13,
                            fontWeight: 700,
                            color: compact ? '#64748B' : 'var(--text-1)',
                            whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
                            flex: 1, minWidth: 0,
                        }}
                    >
                        {compact
                            ? (post.caption?.trim() || `@${post.username || '—'}`)
                            : `@${post.username || '—'}`}
                    </span>
                    <span style={{ fontSize: 11, color: 'var(--text-3)', whiteSpace: 'nowrap', flexShrink: 0 }}>
                        {timeAgo(post.posted_at || post.scraped_at)}
                    </span>
                    {onDelete && (
                        <span
                            role="button"
                            tabIndex={0}
                            aria-label={t('analytics.posts.removeAria')}
                            title={t('analytics.posts.removeAria')}
                            onClick={handleRemove}
                            onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                    e.preventDefault();
                                    handleRemove(e as unknown as React.MouseEvent);
                                }
                            }}
                            onMouseEnter={() => setRemoveHover(true)}
                            onMouseLeave={() => setRemoveHover(false)}
                            style={{
                                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                width: 22, height: 22, borderRadius: '6px',
                                color: removeHover ? '#b3261e' : 'var(--text-3)',
                                background: removeHover ? 'rgba(255,59,48,0.10)' : 'transparent',
                                cursor: 'pointer',
                                transition: 'background 0.15s ease, color 0.15s ease',
                                flexShrink: 0,
                            }}
                        >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="3 6 5 6 21 6" />
                                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                                <path d="M10 11v6" />
                                <path d="M14 11v6" />
                                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2" />
                            </svg>
                        </span>
                    )}
                </div>

                {!compact && (
                    <p
                        style={{
                            margin: 0,
                            fontSize: '12px',
                            color: 'var(--text-2)',
                            lineHeight: 1.45,
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                            minHeight: '34px',
                        }}
                    >
                        {post.caption || '\u00A0'}
                    </p>
                )}

                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(3, 1fr)',
                        gap: compact ? 4 : 6,
                        marginTop: 'auto',
                        paddingTop: compact ? 8 : 10,
                        borderTop: '1px solid #E8EEF4',
                    }}
                >
                    <Metric label="Views" value={formatCount(displayViews)} compact={compact} />
                    <Metric label="Likes" value={formatCount(post.likes)} compact={compact} />
                    <Metric label="Eng." value={formatCount(post.total_engagement)} accent compact={compact} />
                </div>
            </div>
        </button>
    );
}

function Metric({
    label,
    value,
    accent,
    compact,
}: {
    label: string;
    value: string;
    accent?: boolean;
    compact?: boolean;
}) {
    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 1, minWidth: 0 }}>
            <span
                style={{
                    fontSize: compact ? 12 : 13,
                    fontWeight: 700,
                    color: accent ? '#5B86D6' : compact ? '#64748B' : 'var(--text-1)',
                }}
            >
                {value}
            </span>
            <span style={{ fontSize: 9.5, color: '#A0AEC0', textTransform: 'uppercase', letterSpacing: 0.3 }}>
                {label}
            </span>
        </div>
    );
}
