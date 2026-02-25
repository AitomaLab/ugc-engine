'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { apiFetch } from '@/lib/utils';
import type { ProductShot } from '@/lib/types';

// ---------------------------------------------------------------------------
// Lightbox — fullscreen preview for images and videos
// ---------------------------------------------------------------------------

function Lightbox({ shot, onClose }: { shot: ProductShot; onClose: () => void }) {
    return (
        <div className="fixed inset-0 z-[60] flex items-center justify-center p-4" onClick={onClose}>
            <div className="absolute inset-0 bg-black/80 backdrop-blur-md" />
            <div className="relative max-w-4xl w-full max-h-[90vh] flex flex-col items-center" onClick={e => e.stopPropagation()}>
                {/* Close */}
                <button onClick={onClose} className="absolute -top-2 -right-2 z-10 bg-slate-800 hover:bg-slate-700 text-white rounded-full p-2 shadow-xl transition-colors">
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                </button>

                {/* Media */}
                {shot.video_url && shot.status === 'animation_completed' ? (
                    <video
                        src={shot.video_url}
                        className="max-h-[80vh] w-auto rounded-2xl shadow-2xl"
                        controls
                        autoPlay
                        loop
                    />
                ) : shot.image_url ? (
                    <img src={shot.image_url} alt={shot.shot_type} className="max-h-[80vh] w-auto rounded-2xl shadow-2xl object-contain" />
                ) : null}

                {/* Caption */}
                <div className="mt-3 text-center">
                    <p className="text-sm text-white font-medium capitalize">{shot.shot_type.replace('_', ' ')} Shot</p>
                    <p className="text-xs text-slate-400 mt-1">
                        {shot.status === 'animation_completed' ? 'Cinematic Video' : 'Product Still'}
                    </p>
                </div>
            </div>
        </div>
    );
}


// ---------------------------------------------------------------------------
// Shot Card
// ---------------------------------------------------------------------------

function ShotCard({
    shot,
    onAnimate,
    onDelete,
    onPreview,
    isAnimating,
}: {
    shot: ProductShot;
    onAnimate: () => void;
    onDelete: () => void;
    onPreview: () => void;
    isAnimating: boolean;
}) {
    const [hovering, setHovering] = useState(false);
    const videoRef = useRef<HTMLVideoElement>(null);

    useEffect(() => {
        if (videoRef.current) {
            if (hovering) {
                videoRef.current.play().catch(() => { });
            } else {
                videoRef.current.pause();
                videoRef.current.currentTime = 0;
            }
        }
    }, [hovering]);

    const isPending = shot.status === 'image_pending' || shot.status === 'animation_pending';

    return (
        <div
            className="rounded-xl overflow-hidden bg-slate-800/60 border border-white/5 relative group transition-all hover:border-white/10 hover:shadow-lg"
            onMouseEnter={() => setHovering(true)}
            onMouseLeave={() => setHovering(false)}
        >
            {/* Media */}
            <div className="aspect-square relative cursor-pointer" onClick={onPreview}>
                {shot.status === 'animation_completed' && shot.video_url ? (
                    <video
                        ref={videoRef}
                        src={shot.video_url}
                        className="w-full h-full object-cover"
                        muted
                        loop
                        playsInline
                        poster={shot.image_url}
                    />
                ) : shot.image_url ? (
                    <img src={shot.image_url} alt={shot.shot_type} className="w-full h-full object-cover" />
                ) : (
                    <div className="w-full h-full flex items-center justify-center bg-slate-900">
                        {isPending ? (
                            <div className="flex flex-col items-center gap-2">
                                <div className="animate-spin w-8 h-8 border-2 border-slate-600 border-t-blue-400 rounded-full" />
                                <span className="text-[10px] text-slate-500 animate-pulse">
                                    {shot.status === 'image_pending' ? 'Generating...' : 'Animating...'}
                                </span>
                            </div>
                        ) : (
                            <span className="text-slate-600 text-xs">No image</span>
                        )}
                    </div>
                )}

                {/* Animation spinner overlay */}
                {shot.status === 'animation_pending' && shot.image_url && (
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                        <div className="flex flex-col items-center gap-2">
                            <div className="animate-spin w-8 h-8 border-2 border-white/20 border-t-purple-400 rounded-full" />
                            <span className="text-[10px] text-white/70">Animating...</span>
                        </div>
                    </div>
                )}

                {/* Video play icon */}
                {shot.status === 'animation_completed' && !hovering && (
                    <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                        <div className="bg-black/50 rounded-full p-2">
                            <svg className="w-6 h-6 text-white" fill="currentColor" viewBox="0 0 24 24"><path d="M8 5v14l11-7z" /></svg>
                        </div>
                    </div>
                )}

                {/* Expand icon on hover */}
                {!isPending && (shot.image_url || shot.video_url) && (
                    <div className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <div className="bg-black/60 rounded-lg p-1.5">
                            <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
                            </svg>
                        </div>
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="p-3">
                <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-white font-medium capitalize">{shot.shot_type.replace('_', ' ')}</span>
                    {shot.status === 'failed' ? (
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full font-medium text-red-400 bg-red-500/10">Failed</span>
                    ) : shot.status === 'animation_completed' ? (
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full font-medium text-green-400 bg-green-500/10">Video Ready</span>
                    ) : shot.status === 'image_completed' ? (
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full font-medium text-blue-400 bg-blue-500/10">Still Ready</span>
                    ) : (
                        <span className="text-[9px] px-1.5 py-0.5 rounded-full font-medium text-yellow-400 bg-yellow-500/10 animate-pulse">Processing</span>
                    )}
                </div>

                {/* Action buttons */}
                <div className="flex gap-1.5">
                    {shot.status === 'image_completed' && (
                        <button
                            onClick={(e) => { e.stopPropagation(); onAnimate(); }}
                            disabled={isAnimating}
                            className="flex-1 bg-purple-500/20 text-purple-300 hover:bg-purple-500/30 px-2 py-1.5 rounded-lg text-[10px] font-medium transition-colors disabled:opacity-50"
                        >
                            {isAnimating ? 'Queuing...' : '▶ Animate'}
                        </button>
                    )}
                    <button
                        onClick={(e) => { e.stopPropagation(); onDelete(); }}
                        className="bg-red-500/10 text-red-400 hover:bg-red-500/20 px-2 py-1.5 rounded-lg text-[10px] font-medium transition-colors"
                        title="Delete"
                    >
                        🗑
                    </button>
                </div>

                {/* Error message */}
                {shot.status === 'failed' && shot.error_message && (
                    <p className="text-[9px] text-red-400/70 mt-1.5 truncate" title={shot.error_message}>
                        {shot.error_message}
                    </p>
                )}
            </div>
        </div>
    );
}


// ---------------------------------------------------------------------------
// Main Gallery Component
// ---------------------------------------------------------------------------

export default function ProductShotsGallery({
    productId,
    onUpdate,
}: {
    productId: string;
    onUpdate?: () => void;
}) {
    const [shots, setShots] = useState<ProductShot[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeTab, setActiveTab] = useState<'stills' | 'videos'>('stills');
    const [animatingIds, setAnimatingIds] = useState<Set<string>>(new Set());
    const [previewShot, setPreviewShot] = useState<ProductShot | null>(null);
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchShots = useCallback(async () => {
        try {
            const data = await apiFetch<ProductShot[]>(`/api/products/${productId}/shots`);
            setShots(Array.isArray(data) ? data : []);
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    }, [productId]);

    useEffect(() => {
        fetchShots();
    }, [fetchShots]);

    // Poll for pending items
    useEffect(() => {
        const hasPending = shots.some(s =>
            s.status === 'image_pending' || s.status === 'animation_pending'
        );

        if (hasPending) {
            pollRef.current = setInterval(fetchShots, 5000);
        } else if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
        }

        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, [shots, fetchShots]);

    async function handleAnimate(shotId: string) {
        setAnimatingIds(prev => new Set(prev).add(shotId));
        try {
            await apiFetch(`/api/shots/${shotId}/animate`, { method: 'POST' });
            setShots(prev => prev.map(s =>
                s.id === shotId ? { ...s, status: 'animation_pending' as const } : s
            ));
        } catch (err) {
            console.error('Animate error:', err);
        } finally {
            setAnimatingIds(prev => {
                const next = new Set(prev);
                next.delete(shotId);
                return next;
            });
        }
    }

    async function handleDelete(shotId: string) {
        if (!confirm('Delete this shot? This cannot be undone.')) return;
        try {
            await apiFetch(`/api/shots/${shotId}`, { method: 'DELETE' });
            setShots(prev => prev.filter(s => s.id !== shotId));
            onUpdate?.();
        } catch (err) {
            console.error('Delete error:', err);
        }
    }

    if (loading) return null;
    if (shots.length === 0) return null;

    // Separate stills from animated videos (exclude failed from main view)
    const stills = shots.filter(s =>
        s.status === 'image_completed' || s.status === 'image_pending'
    );
    const videos = shots.filter(s =>
        s.status === 'animation_completed' || s.status === 'animation_pending'
    );
    const failed = shots.filter(s => s.status === 'failed');

    const displayShots = activeTab === 'stills' ? stills : videos;

    return (
        <>
            <div className="mt-4 bg-slate-900/50 rounded-2xl border border-white/5 overflow-hidden">
                {/* Tab Header */}
                <div className="flex items-center gap-0 border-b border-white/5">
                    <button
                        onClick={() => setActiveTab('stills')}
                        className={`flex-1 py-3 px-4 text-xs font-medium transition-colors ${activeTab === 'stills'
                                ? 'text-blue-400 border-b-2 border-blue-400 bg-blue-500/5'
                                : 'text-slate-500 hover:text-slate-300'
                            }`}
                    >
                        📸 Product Shots ({stills.length})
                    </button>
                    <button
                        onClick={() => setActiveTab('videos')}
                        className={`flex-1 py-3 px-4 text-xs font-medium transition-colors ${activeTab === 'videos'
                                ? 'text-purple-400 border-b-2 border-purple-400 bg-purple-500/5'
                                : 'text-slate-500 hover:text-slate-300'
                            }`}
                    >
                        🎬 Cinematic Videos ({videos.length})
                    </button>
                </div>

                {/* Grid */}
                <div className="p-4">
                    {displayShots.length === 0 ? (
                        <div className="text-center py-8">
                            <p className="text-slate-500 text-sm">
                                {activeTab === 'stills' ? 'No product shots yet.' : 'No cinematic videos yet.'}
                            </p>
                            <p className="text-slate-600 text-xs mt-1">
                                {activeTab === 'videos' ? 'Animate a product shot to create a cinematic video.' : 'Generate shots to get started.'}
                            </p>
                        </div>
                    ) : (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                            {displayShots.map((shot) => (
                                <ShotCard
                                    key={shot.id}
                                    shot={shot}
                                    onAnimate={() => handleAnimate(shot.id)}
                                    onDelete={() => handleDelete(shot.id)}
                                    onPreview={() => setPreviewShot(shot)}
                                    isAnimating={animatingIds.has(shot.id)}
                                />
                            ))}
                        </div>
                    )}

                    {/* Failed shots section */}
                    {failed.length > 0 && (
                        <div className="mt-4 border-t border-white/5 pt-3">
                            <p className="text-[10px] uppercase tracking-wider text-red-400/60 font-bold mb-2">
                                Failed ({failed.length})
                            </p>
                            <div className="flex flex-wrap gap-2">
                                {failed.map((shot) => (
                                    <div key={shot.id} className="flex items-center gap-2 bg-red-500/5 border border-red-500/10 rounded-lg px-3 py-2">
                                        <span className="text-[10px] text-red-400 capitalize">{shot.shot_type.replace('_', ' ')}</span>
                                        <button
                                            onClick={() => handleDelete(shot.id)}
                                            className="text-red-400/60 hover:text-red-400 text-[10px] transition-colors"
                                            title="Remove"
                                        >
                                            ✕
                                        </button>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            {/* Lightbox */}
            {previewShot && (
                <Lightbox shot={previewShot} onClose={() => setPreviewShot(null)} />
            )}
        </>
    );
}
