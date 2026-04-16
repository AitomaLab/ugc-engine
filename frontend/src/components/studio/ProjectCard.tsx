'use client';

import Link from 'next/link';
import { useState } from 'react';

interface PreviewAsset {
    url: string;
    type: 'image' | 'video';
}

interface ProjectCardProps {
    project: {
        id: string;
        name: string;
        is_default?: boolean;
        created_at?: string;
        recent_previews?: PreviewAsset[];
        asset_counts?: {
            images?: number;
            videos?: number;
            influencers?: number;
            products?: number;
        };
    };
}

/* ── Soft gradient palette for empty projects ────────────────────── */
const EMPTY_GRADIENTS = [
    ['linear-gradient(135deg, #C3D4F7 0%, #D5DCFA 100%)', 'linear-gradient(135deg, #D1C4F9 0%, #E0D5FA 100%)'],
    ['linear-gradient(135deg, #FBC2D0 0%, #F5D0DA 100%)', 'linear-gradient(135deg, #B8E8D0 0%, #C5EDD8 100%)'],
];

export function ProjectCard({ project }: ProjectCardProps) {
    const [hovered, setHovered] = useState(false);
    const [failedUrls, setFailedUrls] = useState<Set<string>>(new Set());
    const counts = project.asset_counts || {};
    const totalAssets = (counts.images || 0) + (counts.videos || 0);

    // Filter out failed image URLs
    const previews = (project.recent_previews || []).filter(p => !failedUrls.has(p.url));
    const previewCount = previews.length;

    const handleImgError = (url: string) => {
        setFailedUrls(prev => new Set(prev).add(url));
    };

    /* Relative time formatting */
    const timeAgo = (() => {
        if (!project.created_at) return '';
        const diff = Date.now() - new Date(project.created_at).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 60) return `${mins}m ago`;
        const hrs = Math.floor(mins / 60);
        if (hrs < 24) return `${hrs}h ago`;
        const days = Math.floor(hrs / 24);
        if (days === 1) return 'Yesterday';
        if (days < 30) return `${days} days ago`;
        return new Date(project.created_at).toLocaleDateString('en-US', {
            month: 'short', day: 'numeric', year: 'numeric',
        });
    })();

    /* Adaptive grid: 1→full, 2→1×2, 3→1 top + 2 bottom, 4→2×2 */
    const renderPreviewGrid = () => {
        if (previewCount === 0) {
            // Empty project — show soft gradient placeholder
            return (
                <div style={{
                    width: '100%',
                    height: '100%',
                    background: 'linear-gradient(135deg, #E3ECFF 0%, #D5DCFA 50%, #EDE3FA 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}>
                    <svg viewBox="0 0 24 24" style={{
                        width: '36px', height: '36px',
                        fill: 'none', stroke: 'rgba(51,122,255,0.25)',
                        strokeWidth: '1.5',
                    }}>
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                    </svg>
                </div>
            );
        }

        if (previewCount === 1) {
            return (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr', height: '100%' }}>
                    {renderThumb(previews[0], 0)}
                </div>
            );
        }

        if (previewCount === 2) {
            return (
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px', height: '100%' }}>
                    {renderThumb(previews[0], 0)}
                    {renderThumb(previews[1], 1)}
                </div>
            );
        }

        if (previewCount === 3) {
            return (
                <div style={{ display: 'grid', gridTemplateRows: '1fr 1fr', gap: '2px', height: '100%' }}>
                    <div style={{ overflow: 'hidden' }}>
                        {renderThumb(previews[0], 0)}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '2px' }}>
                        {renderThumb(previews[1], 1)}
                        {renderThumb(previews[2], 2)}
                    </div>
                </div>
            );
        }

        // 4+ previews → 2×2 grid
        return (
            <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gridTemplateRows: '1fr 1fr',
                gap: '2px',
                height: '100%',
            }}>
                {previews.slice(0, 4).map((p, i) => renderThumb(p, i))}
            </div>
        );
    };

    const renderThumb = (asset: PreviewAsset, index: number) => (
        <div
            key={index}
            style={{
                position: 'relative',
                overflow: 'hidden',
                background: '#E8ECF4',
                transition: 'transform 0.35s ease',
                transform: hovered ? 'scale(1.03)' : 'scale(1)',
            }}
        >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
                src={asset.url}
                alt=""
                loading="lazy"
                onError={() => handleImgError(asset.url)}
                style={{
                    width: '100%',
                    height: '100%',
                    objectFit: 'cover',
                    display: 'block',
                }}
            />
            {asset.type === 'video' && (
                <div style={{
                    position: 'absolute',
                    bottom: '4px',
                    right: '4px',
                    width: '18px',
                    height: '18px',
                    borderRadius: '4px',
                    background: 'rgba(0,0,0,0.55)',
                    backdropFilter: 'blur(4px)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                }}>
                    <svg viewBox="0 0 24 24" style={{
                        width: '10px', height: '10px',
                        fill: 'white', stroke: 'none',
                    }}>
                        <polygon points="5,3 19,12 5,21" />
                    </svg>
                </div>
            )}
        </div>
    );

    return (
        <Link
            href={`/projects/${project.id}`}
            id={`project-card-${project.id}`}
            style={{
                display: 'flex',
                flexDirection: 'column',
                borderRadius: '16px',
                background: '#FFF',
                border: hovered
                    ? '1px solid rgba(51,122,255,0.22)'
                    : '1px solid rgba(0,0,0,0.06)',
                boxShadow: hovered
                    ? '0 12px 40px rgba(51,122,255,0.14), 0 0 0 1px rgba(51,122,255,0.06)'
                    : '0 1px 4px rgba(0,0,0,0.04)',
                transition: 'all 0.28s cubic-bezier(0.4, 0, 0.2, 1)',
                cursor: 'pointer',
                textDecoration: 'none',
                color: 'inherit',
                overflow: 'hidden',
                transform: hovered ? 'translateY(-3px)' : 'none',
            }}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
        >
            {/* ── Preview Grid ──────────────────────────────── */}
            <div style={{
                aspectRatio: '16 / 10',
                overflow: 'hidden',
                background: 'rgba(0,0,0,0.02)',
            }}>
                {renderPreviewGrid()}
            </div>

            {/* ── Info Footer ───────────────────────────────── */}
            <div style={{
                padding: '14px 16px 16px',
                display: 'flex',
                flexDirection: 'column',
                gap: '4px',
            }}>
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                }}>
                    <h3 style={{
                        margin: 0,
                        fontSize: '15px',
                        fontWeight: 650,
                        color: '#0D1B3E',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        flex: 1,
                        letterSpacing: '-0.2px',
                    }}>
                        {project.name}
                    </h3>
                    {project.is_default && (
                        <span style={{
                            fontSize: '10px',
                            fontWeight: 700,
                            color: '#337AFF',
                            background: 'rgba(51,122,255,0.08)',
                            padding: '2px 7px',
                            borderRadius: '4px',
                            letterSpacing: '0.5px',
                            flexShrink: 0,
                        }}>
                            DEFAULT
                        </span>
                    )}
                </div>

                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                    fontSize: '12px',
                    color: '#8A93B0',
                    fontWeight: 500,
                }}>
                    {(counts.images || 0) > 0 && (
                        <span>{counts.images} Image{(counts.images || 0) !== 1 ? 's' : ''}</span>
                    )}
                    {(counts.images || 0) > 0 && (counts.videos || 0) > 0 && (
                        <span style={{ opacity: 0.5 }}>·</span>
                    )}
                    {(counts.videos || 0) > 0 && (
                        <span>{counts.videos} Video{(counts.videos || 0) !== 1 ? 's' : ''}</span>
                    )}
                    {totalAssets === 0 && (
                        <span>No assets yet</span>
                    )}
                    {timeAgo && (
                        <>
                            <span style={{ opacity: 0.5 }}>·</span>
                            <span>{timeAgo}</span>
                        </>
                    )}
                </div>
            </div>
        </Link>
    );
}
