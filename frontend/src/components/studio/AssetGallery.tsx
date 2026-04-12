'use client';

import { useState, useEffect, useMemo, useCallback } from 'react';
import { creativeFetch } from '@/lib/creative-os-api';
import { ImageEditModal } from './ImageEditModal';
import { VideoDetailModal } from './VideoDetailModal';

/** Extract file extension from URL path or Content-Type header */
function getFileExtension(url: string, contentType: string | null, fallbackType: 'images' | 'videos'): string {
    // 1. Try to get from URL path (most reliable for Supabase storage)
    const urlPath = new URL(url).pathname;
    const urlExt = urlPath.split('.').pop()?.toLowerCase();
    if (urlExt && ['png', 'jpg', 'jpeg', 'webp', 'gif', 'mp4', 'webm', 'mov'].includes(urlExt)) {
        return urlExt;
    }
    // 2. Try Content-Type header
    if (contentType) {
        const mimeMap: Record<string, string> = {
            'image/png': 'png', 'image/jpeg': 'jpg', 'image/webp': 'webp', 'image/gif': 'gif',
            'video/mp4': 'mp4', 'video/webm': 'webm', 'video/quicktime': 'mov',
        };
        for (const [mime, ext] of Object.entries(mimeMap)) {
            if (contentType.includes(mime)) return ext;
        }
    }
    // 3. Fallback
    return fallbackType === 'images' ? 'png' : 'mp4';
}

interface AssetGalleryProps {
    assets: any[];
    type: 'images' | 'videos';
    loading: boolean;
    projectId: string;
    onRefresh?: () => void;
    onAnimated?: () => void;
    onCreateVideo?: (asset: any) => void;
}

const PAGE_SIZE = 20;

export function AssetGallery({ assets, type, loading, projectId, onRefresh, onAnimated, onCreateVideo }: AssetGalleryProps) {
    const [page, setPage] = useState(0);
    const [selectedImage, setSelectedImage] = useState<any>(null);
    const [selectedVideo, setSelectedVideo] = useState<any>(null);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [bulkLoading, setBulkLoading] = useState(false);
    const [confirmingDeleteId, setConfirmingDeleteId] = useState<string | null>(null);

    // Reset page & selection when switching tabs
    useEffect(() => { setPage(0); setSelectedIds(new Set()); }, [type]);

    const totalPages = Math.ceil(assets.length / PAGE_SIZE);
    const paged = useMemo(() => assets.slice(page * PAGE_SIZE, (page + 1) * PAGE_SIZE), [assets, page]);

    const isSelecting = selectedIds.size > 0;

    const toggleSelect = useCallback((id: string) => {
        setSelectedIds(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    }, []);

    const selectAll = useCallback(() => {
        setSelectedIds(new Set(paged.map(a => a.id)));
    }, [paged]);

    const cancelSelection = useCallback(() => {
        setSelectedIds(new Set());
    }, []);

    const [bulkDeleteConfirm, setBulkDeleteConfirm] = useState(false);

    const handleBulkDelete = useCallback(async () => {
        if (!bulkDeleteConfirm) {
            setBulkDeleteConfirm(true);
            return;
        }
        setBulkLoading(true);
        setBulkDeleteConfirm(false);
        try {
            const body = type === 'images'
                ? { image_ids: Array.from(selectedIds), video_ids: [] }
                : { image_ids: [], video_ids: Array.from(selectedIds) };
            await creativeFetch(`/creative-os/projects/${projectId}/assets/bulk-delete`, {
                method: 'POST',
                body: JSON.stringify(body),
            });
            setSelectedIds(new Set());
            onRefresh?.();
        } catch (err) {
            console.error('Bulk delete failed:', err);
            alert('Failed to delete some items. Please try again.');
        } finally {
            setBulkLoading(false);
        }
    }, [selectedIds, type, projectId, onRefresh, bulkDeleteConfirm]);

    const handleBulkDownload = useCallback(async () => {
        const selected = assets.filter(a => selectedIds.has(a.id));
        for (const a of selected) {
            const url = type === 'images'
                ? (a.image_url || a.result_url)
                : (a.final_video_url || a.video_url);
            if (url) {
                try {
                    const resp = await fetch(url);
                    const blob = await resp.blob();
                    const blobUrl = URL.createObjectURL(blob);
                    const ext = getFileExtension(url, resp.headers.get('content-type'), type);
                    const filename = `${a.product_name || a.campaign_name || 'asset'}_${a.id?.slice(0, 8) || Date.now()}.${ext}`;
                    const link = document.createElement('a');
                    link.href = blobUrl;
                    link.download = filename;
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                    URL.revokeObjectURL(blobUrl);
                } catch (err) {
                    console.error('Download failed for asset:', a.id, err);
                }
            }
        }
    }, [selectedIds, assets, type]);

    const handleDeleteClick = useCallback((id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setConfirmingDeleteId(id);
    }, []);

    const handleConfirmDelete = useCallback(async (id: string) => {
        setConfirmingDeleteId(null);
        try {
            const endpoint = type === 'images'
                ? `/creative-os/projects/${projectId}/assets/images/${id}`
                : `/creative-os/projects/${projectId}/assets/videos/${id}`;
            await creativeFetch(endpoint, { method: 'DELETE' });
            onRefresh?.();
        } catch (err) {
            console.error('Delete failed:', err);
            alert('Failed to delete. Please try again.');
        }
    }, [type, projectId, onRefresh]);

    const handleCancelDelete = useCallback(() => {
        setConfirmingDeleteId(null);
    }, []);

    if (loading) {
        return (
            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: '16px',
            }}>
                {[0, 1, 2, 3, 4, 5].map(i => (
                    <div key={i} suppressHydrationWarning style={{
                        aspectRatio: '9 / 16',
                        borderRadius: '12px',
                        background: 'linear-gradient(90deg, rgba(51,122,255,0.04) 25%, rgba(51,122,255,0.08) 50%, rgba(51,122,255,0.04) 75%)',
                        backgroundSize: '200% 100%',
                        animation: `shimmer 1.5s infinite linear ${(i * 150)}ms`,
                    }} />
                ))}
                <style>{`
                    @keyframes shimmer {
                        0% { background-position: 200% 0; }
                        100% { background-position: -200% 0; }
                    }
                `}</style>
            </div>
        );
    }

    if (assets.length === 0) {
        return (
            <div style={{
                textAlign: 'center',
                padding: '80px 20px',
                borderRadius: '16px',
                background: 'rgba(255,255,255,0.5)',
                border: '1px dashed rgba(51,122,255,0.15)',
            }}>
                <svg viewBox="0 0 24 24" style={{
                    width: '48px',
                    height: '48px',
                    fill: 'none',
                    stroke: '#8A93B0',
                    strokeWidth: '1.2',
                    margin: '0 auto 16px',
                    display: 'block',
                }}>
                    {type === 'images' ? (
                        <path d="M4 16l4.586-4.586a2 2 0 0 1 2.828 0L16 16m-2-2l1.586-1.586a2 2 0 0 1 2.828 0L20 14m-6-6h.01M6 20h12a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2z" />
                    ) : (
                        <>
                            <rect x="2" y="3" width="20" height="14" rx="2" />
                            <path d="M8 21h8M12 17v4" />
                        </>
                    )}
                </svg>
                <p style={{ color: '#4A5578', fontSize: '15px', fontWeight: 500, margin: '0 0 4px' }}>
                    No {type} yet
                </p>
                <p style={{ color: '#8A93B0', fontSize: '13px', margin: 0 }}>
                    Use the Create Bar below to generate your first {type === 'images' ? 'image' : 'video'}
                </p>
            </div>
        );
    }

    return (
        <div>
            {/* ── Bulk Actions Bar ── */}
            {isSelecting && (
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '10px 16px',
                    marginBottom: '16px',
                    borderRadius: '12px',
                    background: 'rgba(51,122,255,0.05)',
                    border: '1px solid rgba(51,122,255,0.12)',
                    animation: 'slideDown 0.2s ease',
                }}>
                    <span style={{
                        fontSize: '13px',
                        fontWeight: 600,
                        color: '#337AFF',
                        marginRight: 'auto',
                    }}>
                        {selectedIds.size} selected
                    </span>

                    <BulkButton label="Select All" onClick={selectAll} />
                    <BulkButton
                        label="Download"
                        onClick={handleBulkDownload}
                        icon={<svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2' }}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>}
                    />
                    {bulkDeleteConfirm ? (
                        <>
                            <span style={{ fontSize: '13px', fontWeight: 600, color: '#DC3545' }}>Confirm delete?</span>
                            <BulkButton label="Yes, Delete" onClick={handleBulkDelete} danger disabled={bulkLoading} />
                            <BulkButton label="No" onClick={() => setBulkDeleteConfirm(false)} muted />
                        </>
                    ) : (
                        <BulkButton
                            label="Delete"
                            onClick={handleBulkDelete}
                            danger
                            disabled={bulkLoading}
                            icon={<svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2' }}><polyline points="3 6 5 6 21 6" /><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>}
                        />
                    )}
                    <BulkButton label="Cancel" onClick={cancelSelection} muted />
                </div>
            )}

            <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
                gap: '16px',
            }}>
                {paged.map((asset, i) => (
                    <AssetCard
                        key={asset.id || i}
                        asset={asset}
                        type={type}
                        projectId={projectId}
                        isSelected={selectedIds.has(asset.id)}
                        isSelecting={isSelecting}
                        isConfirmingDelete={confirmingDeleteId === asset.id}
                        onToggleSelect={() => toggleSelect(asset.id)}
                        onDeleteClick={(e) => handleDeleteClick(asset.id, e)}
                        onConfirmDelete={() => handleConfirmDelete(asset.id)}
                        onCancelDelete={handleCancelDelete}
                        onClick={type === 'images' ? () => setSelectedImage(asset) : () => setSelectedVideo(asset)}
                    />
                ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
                <div style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '8px',
                    marginTop: '24px',
                    paddingBottom: '8px',
                }}>
                    <button
                        onClick={() => setPage(p => Math.max(0, p - 1))}
                        disabled={page === 0}
                        style={{
                            padding: '6px 14px', borderRadius: '8px', border: '1px solid rgba(51,122,255,0.15)',
                            background: page === 0 ? 'rgba(51,122,255,0.03)' : 'white',
                            color: page === 0 ? '#8A93B0' : '#337AFF',
                            cursor: page === 0 ? 'default' : 'pointer', fontSize: '13px', fontWeight: 500,
                        }}
                    >← Prev</button>
                    <span style={{ fontSize: '13px', color: '#4A5578', fontWeight: 500 }}>
                        {page + 1} / {totalPages}
                    </span>
                    <button
                        onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
                        disabled={page >= totalPages - 1}
                        style={{
                            padding: '6px 14px', borderRadius: '8px', border: '1px solid rgba(51,122,255,0.15)',
                            background: page >= totalPages - 1 ? 'rgba(51,122,255,0.03)' : 'white',
                            color: page >= totalPages - 1 ? '#8A93B0' : '#337AFF',
                            cursor: page >= totalPages - 1 ? 'default' : 'pointer', fontSize: '13px', fontWeight: 500,
                        }}
                    >Next →</button>
                </div>
            )}

            {/* Image Edit Modal */}
            {selectedImage && (
                <ImageEditModal
                    asset={selectedImage}
                    projectId={projectId}
                    onClose={() => setSelectedImage(null)}
                    onGenerated={() => {
                        setSelectedImage(null);
                        onRefresh?.();
                    }}
                    onAnimated={() => {
                        setSelectedImage(null);
                        onAnimated?.();
                    }}
                    onCreateVideo={(asset) => {
                        setSelectedImage(null);
                        onCreateVideo?.(asset);
                    }}
                />
            )}

            {/* Video Detail Modal */}
            {selectedVideo && (
                <VideoDetailModal
                    asset={selectedVideo}
                    projectId={projectId}
                    onClose={() => setSelectedVideo(null)}
                    onRefresh={() => {
                        setSelectedVideo(null);
                        onRefresh?.();
                    }}
                />
            )}

            <style>{`
                @keyframes slideDown {
                    from { opacity: 0; transform: translateY(-8px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `}</style>
        </div>
    );
}


/* ── BulkButton ────────────────────────────────────────────────── */

function BulkButton({
    label, onClick, icon, danger, muted, disabled,
}: {
    label: string;
    onClick: () => void;
    icon?: React.ReactNode;
    danger?: boolean;
    muted?: boolean;
    disabled?: boolean;
}) {
    return (
        <button
            onClick={onClick}
            disabled={disabled}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '6px 14px',
                borderRadius: '8px',
                border: danger
                    ? '1px solid rgba(220,53,69,0.2)'
                    : '1px solid rgba(0,0,0,0.08)',
                background: danger
                    ? 'rgba(220,53,69,0.06)'
                    : 'white',
                color: danger
                    ? '#DC3545'
                    : muted ? '#8A93B0' : '#5A6178',
                fontSize: '13px',
                fontWeight: 600,
                cursor: disabled ? 'wait' : 'pointer',
                opacity: disabled ? 0.5 : 1,
                transition: 'all 0.15s',
            }}
        >
            {icon}
            {label}
        </button>
    );
}


/* ── AssetCard ─────────────────────────────────────────────────── */

function AssetCard({ asset, type, projectId, isSelected, isSelecting, isConfirmingDelete, onToggleSelect, onDeleteClick, onConfirmDelete, onCancelDelete, onClick }: {
    asset: any;
    type: 'images' | 'videos';
    projectId: string;
    isSelected: boolean;
    isSelecting: boolean;
    isConfirmingDelete: boolean;
    onToggleSelect: () => void;
    onDeleteClick: (e: React.MouseEvent) => void;
    onConfirmDelete: () => void;
    onCancelDelete: () => void;
    onClick?: () => void;
}) {
    const [hovered, setHovered] = useState(false);
    const [elapsed, setElapsed] = useState(0);
    const imageUrl = type === 'images' ? asset.image_url : null;
    const videoUrl = type === 'videos' ? (asset.final_video_url || asset.video_url) : asset.video_url;
    const status = asset.status || 'success';
    const isProcessing = status.includes('pending') || status.includes('processing') || status.includes('generating');

    // Track elapsed time for pending assets
    useEffect(() => {
        if (!isProcessing || !asset.created_at) return;
        const created = new Date(asset.created_at).getTime();
        const tick = () => setElapsed(Math.floor((Date.now() - created) / 1000));
        tick();
        const id = setInterval(tick, 1000);
        return () => clearInterval(id);
    }, [isProcessing, asset.created_at]);

    const estimatedTotal = type === 'images' ? 90 : 180;
    const remaining = Math.max(0, estimatedTotal - elapsed);
    const formatTime = (s: number) => s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`;

    const handleCardClick = () => {
        if (isProcessing) return;
        if (isSelecting) {
            onToggleSelect();
        } else {
            onClick?.();
        }
    };

    return (
        <div
            onClick={isConfirmingDelete ? undefined : handleCardClick}
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => { if (!isConfirmingDelete) setHovered(false); }}
            style={{
                position: 'relative',
                aspectRatio: '9/16',
                borderRadius: '12px',
                overflow: 'hidden',
                background: '#0D1B3E',
                cursor: isProcessing ? 'default' : 'pointer',
                transition: 'all 0.25s ease',
                transform: hovered && !isProcessing ? 'scale(1.02)' : 'none',
                boxShadow: isSelected
                    ? '0 0 0 3px #337AFF, 0 8px 24px rgba(51,122,255,0.25)'
                    : hovered
                        ? '0 8px 24px rgba(0,0,0,0.2)'
                        : '0 2px 8px rgba(0,0,0,0.1)',
            }}
        >
            {/* Content */}
            {imageUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                    src={imageUrl}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                    }}
                />
            )}
            {videoUrl && !isProcessing && (
                <video
                    src={videoUrl}
                    muted
                    loop
                    playsInline
                    preload="metadata"
                    onMouseEnter={e => (e.target as HTMLVideoElement).play().catch(() => {})}
                    onMouseLeave={e => { (e.target as HTMLVideoElement).pause(); (e.target as HTMLVideoElement).currentTime = 0; }}
                    style={{
                        width: '100%',
                        height: '100%',
                        objectFit: 'cover',
                    }}
                />
            )}

            {/* Selection checkbox — top right */}
            {(hovered || isSelecting) && !isProcessing && (
                <button
                    onClick={(e) => { e.stopPropagation(); onToggleSelect(); }}
                    style={{
                        position: 'absolute',
                        top: '8px',
                        right: '8px',
                        width: '24px',
                        height: '24px',
                        borderRadius: '6px',
                        border: isSelected ? 'none' : '2px solid rgba(255,255,255,0.7)',
                        background: isSelected ? '#337AFF' : 'rgba(0,0,0,0.3)',
                        backdropFilter: 'blur(4px)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: 0,
                        transition: 'all 0.15s',
                        zIndex: 3,
                    }}
                >
                    {isSelected && (
                        <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'white', strokeWidth: '3', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                            <polyline points="20 6 9 17 4 12" />
                        </svg>
                    )}
                </button>
            )}

            {/* Delete icon — top left */}
            {(hovered || isConfirmingDelete) && !isProcessing && !isSelecting && !isConfirmingDelete && (
                <button
                    onClick={onDeleteClick}
                    style={{
                        position: 'absolute',
                        top: '8px',
                        left: '8px',
                        width: '26px',
                        height: '26px',
                        borderRadius: '7px',
                        border: 'none',
                        background: 'rgba(0,0,0,0.45)',
                        backdropFilter: 'blur(4px)',
                        cursor: 'pointer',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: 0,
                        transition: 'all 0.15s',
                        zIndex: 3,
                    }}
                    onMouseEnter={e => (e.currentTarget.style.background = 'rgba(220,53,69,0.8)')}
                    onMouseLeave={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.45)')}
                >
                    <svg viewBox="0 0 24 24" style={{
                        width: '13px', height: '13px',
                        fill: 'none', stroke: 'white', strokeWidth: '2',
                        strokeLinecap: 'round', strokeLinejoin: 'round',
                    }}>
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                </button>
            )}

            {/* Delete confirmation overlay */}
            {isConfirmingDelete && (
                <div
                    onClick={e => e.stopPropagation()}
                    style={{
                        position: 'absolute',
                        inset: 0,
                        background: 'rgba(0,0,0,0.75)',
                        backdropFilter: 'blur(4px)',
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '12px',
                        zIndex: 10,
                    }}
                >
                    <svg viewBox="0 0 24 24" style={{
                        width: '28px', height: '28px',
                        fill: 'none', stroke: '#DC3545', strokeWidth: '1.5',
                        strokeLinecap: 'round', strokeLinejoin: 'round',
                    }}>
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                    <span style={{ color: 'white', fontSize: '13px', fontWeight: 600 }}>Delete this {type === 'images' ? 'image' : 'video'}?</span>
                    <div style={{ display: 'flex', gap: '8px' }}>
                        <button
                            onClick={(e) => { e.stopPropagation(); onConfirmDelete(); }}
                            style={{
                                padding: '6px 16px',
                                borderRadius: '8px',
                                border: 'none',
                                background: '#DC3545',
                                color: 'white',
                                fontSize: '12px',
                                fontWeight: 600,
                                cursor: 'pointer',
                            }}
                        >Delete</button>
                        <button
                            onClick={(e) => { e.stopPropagation(); onCancelDelete(); }}
                            style={{
                                padding: '6px 16px',
                                borderRadius: '8px',
                                border: '1px solid rgba(255,255,255,0.3)',
                                background: 'transparent',
                                color: 'white',
                                fontSize: '12px',
                                fontWeight: 600,
                                cursor: 'pointer',
                            }}
                        >Cancel</button>
                    </div>
                </div>
            )}

            {/* Processing overlay with progressive preview */}
            {isProcessing && (() => {
                const previewUrl = asset.preview_url;
                const previewType = asset.preview_type;
                const statusMsg = asset.status_message || '';
                const progress = asset.progress || 0;
                const hasPreview = !!previewUrl;

                // Map status_message to user-friendly step labels
                const stepLabel = (() => {
                    if (!statusMsg) return status.includes('pending') ? 'Queued' : 'Generating...';
                    if (statusMsg.includes('Composite Image')) return hasPreview ? 'Influencer image ready' : 'Generating image...';
                    if (statusMsg.includes('Animating')) return hasPreview ? 'Animating scene' : 'Animating scene...';
                    if (statusMsg.includes('Building scenes')) return 'Preparing scenes...';
                    if (statusMsg.includes('Generating scenes')) return 'Generating scenes...';
                    if (statusMsg.includes('Analyzing Product')) return 'Analyzing product...';
                    if (statusMsg.includes('Adding Music')) return 'Adding music...';
                    if (statusMsg.includes('Assembling')) return 'Assembling video...';
                    if (statusMsg.includes('Subtitling')) return 'Adding captions...';
                    if (statusMsg.includes('Voiceover')) return 'Generating voiceover...';
                    if (statusMsg.includes('Preparing')) return 'Preparing UGC clip...';
                    if (statusMsg.includes('Generating video')) return 'Generating video...';
                    if (statusMsg.includes('Extend:') || statusMsg.includes('Gen:')) {
                        const match = statusMsg.match(/\((\d+)\/(\d+)\)/);
                        return match ? `Generating scene ${match[1]}/${match[2]}...` : 'Generating scene...';
                    }
                    return statusMsg;
                })();

                // Estimated time — use real progress if available, else compute from elapsed
                const estMinutes = type === 'images' ? 1.5 : 3;
                const elapsedMin = elapsed / 60;
                const remainingMin = Math.max(0, estMinutes - elapsedMin);
                const remainingLabel = progress > 85 ? 'finishing...' :
                    remainingMin >= 1 ? `~${Math.ceil(remainingMin)}m left` :
                    remainingMin > 0 ? `~${Math.ceil(remainingMin * 60)}s left` : 'finishing...';

                return (
                    <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
                        {/* Preview image or video when available */}
                        {previewUrl && previewType === 'video' ? (
                            <video
                                key={previewUrl}
                                src={previewUrl}
                                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
                                autoPlay muted loop playsInline
                                onError={(e) => { (e.target as HTMLVideoElement).style.display = 'none'; }}
                            />
                        ) : previewUrl && previewType === 'image' ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                                key={previewUrl}
                                src={previewUrl}
                                alt="Preview"
                                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }}
                                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                            />
                        ) : null}

                        {/* Gradient overlay for readability (darker when preview shown) */}
                        <div style={{
                            position: 'absolute', inset: 0,
                            background: hasPreview
                                ? 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.3) 40%, transparent 70%)'
                                : 'rgba(13,27,62,0.85)',
                            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'flex-end',
                            paddingBottom: '16px', gap: '6px',
                        }}>
                            {/* Spinner only when no preview */}
                            {!hasPreview && (
                                <div style={{
                                    width: '36px', height: '36px',
                                    border: '3px solid rgba(51,122,255,0.2)',
                                    borderTopColor: '#337AFF',
                                    borderRadius: '50%',
                                    animation: 'spin 0.8s linear infinite',
                                    marginBottom: 'auto', marginTop: 'auto',
                                }} />
                            )}

                            {/* Status badge */}
                            <div style={{
                                background: 'rgba(0,0,0,0.6)',
                                backdropFilter: 'blur(8px)',
                                borderRadius: '20px',
                                padding: '5px 14px',
                                display: 'flex', alignItems: 'center', gap: '6px',
                            }}>
                                <div style={{
                                    width: '6px', height: '6px', borderRadius: '50%',
                                    backgroundColor: '#337AFF',
                                    animation: 'pulse 1.5s ease-in-out infinite',
                                }} />
                                <span style={{ fontSize: '12px', fontWeight: 600, color: 'white' }}>
                                    {stepLabel}
                                </span>
                            </div>

                            {/* Progress bar */}
                            {(progress > 0 || elapsed > 5) && (
                                <div style={{ width: '70%', height: '4px', borderRadius: '2px', backgroundColor: 'rgba(255,255,255,0.2)', overflow: 'hidden' }}>
                                    <div style={{
                                        width: `${progress > 0 ? progress : Math.min(95, (elapsed / estimatedTotal) * 100)}%`,
                                        height: '100%',
                                        borderRadius: '2px',
                                        background: 'linear-gradient(90deg, #337AFF, #6C5CE7)',
                                        transition: 'width 0.5s ease',
                                    }} />
                                </div>
                            )}

                            {/* Time remaining */}
                            <span style={{ fontSize: '11px', color: 'white', opacity: 0.7 }}>
                                {remainingLabel}
                            </span>
                        </div>

                        <style>{`
                            @keyframes spin { to { transform: rotate(360deg); } }
                            @keyframes pulse {
                                0%, 100% { opacity: 1; }
                                50% { opacity: 0.4; }
                            }
                        `}</style>
                    </div>
                );
            })()}

            {/* Hover overlay (only when not in selection mode) */}
            {!isProcessing && hovered && !isSelecting && (
                <div style={{
                    position: 'absolute',
                    inset: 0,
                    background: 'linear-gradient(transparent 40%, rgba(0,0,0,0.6))',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'flex-end',
                    padding: '12px',
                    zIndex: 1,
                }}>
                    {type === 'images' && (
                        <div style={{
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            position: 'absolute',
                            top: '50%',
                            left: '50%',
                            transform: 'translate(-50%, -50%)',
                        }}>
                            <div style={{
                                width: '40px',
                                height: '40px',
                                borderRadius: '50%',
                                background: 'rgba(255,255,255,0.2)',
                                backdropFilter: 'blur(8px)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}>
                                <svg viewBox="0 0 24 24" style={{
                                    width: '18px', height: '18px',
                                    fill: 'none', stroke: 'white', strokeWidth: '2',
                                }}>
                                    <path d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 1 1 3.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                                </svg>
                            </div>
                        </div>
                    )}
                    {type === 'videos' && (
                        <div style={{
                            display: 'flex',
                            justifyContent: 'center',
                            alignItems: 'center',
                            position: 'absolute',
                            top: '50%',
                            left: '50%',
                            transform: 'translate(-50%, -50%)',
                        }}>
                            <div style={{
                                width: '40px',
                                height: '40px',
                                borderRadius: '50%',
                                background: 'rgba(255,255,255,0.2)',
                                backdropFilter: 'blur(8px)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}>
                                <svg viewBox="0 0 24 24" style={{
                                    width: '18px', height: '18px',
                                    fill: 'white', marginLeft: '2px',
                                }}>
                                    <polygon points="5,3 19,12 5,21" />
                                </svg>
                            </div>
                        </div>
                    )}
                    <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        width: '100%',
                        alignItems: 'center',
                    }}>
                        <span style={{ color: 'white', fontSize: '11px', fontWeight: 500, opacity: 0.8 }}>
                            {asset.product_name || asset.campaign_name || ''}
                        </span>
                        <span style={{
                            color: 'rgba(255,255,255,0.7)',
                            fontSize: '10px',
                            fontWeight: 500,
                        }}>
                            {type === 'images' ? 'Click to edit' : 'Click to view'}
                        </span>
                    </div>
                </div>
            )}

            {/* Selected dim overlay */}
            {isSelected && (
                <div style={{
                    position: 'absolute',
                    inset: 0,
                    background: 'rgba(51,122,255,0.15)',
                    zIndex: 1,
                    pointerEvents: 'none',
                }} />
            )}
        </div>
    );
}
