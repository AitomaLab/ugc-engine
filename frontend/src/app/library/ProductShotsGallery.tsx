'use client';

import { useState, useEffect, useRef } from 'react';
import { apiFetch } from '@/lib/utils';
import type { ProductShot } from '@/lib/types';

export default function ProductShotsGallery({
    productId,
    onUpdate,
}: {
    productId: string;
    onUpdate?: () => void;
}) {
    const [shots, setShots] = useState<ProductShot[]>([]);
    const [loading, setLoading] = useState(true);
    const [animatingIds, setAnimatingIds] = useState<Set<string>>(new Set());
    const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchShots = async () => {
        try {
            const data = await apiFetch<ProductShot[]>(`/api/products/${productId}/shots`);
            setShots(Array.isArray(data) ? data : []);
        } catch {
            // silent
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchShots();
    }, [productId]);

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
    }, [shots]);

    async function handleAnimate(shotId: string) {
        setAnimatingIds(prev => new Set(prev).add(shotId));
        try {
            await apiFetch(`/api/shots/${shotId}/animate`, { method: 'POST' });
            // Update local state immediately
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

    if (loading) return null;
    if (shots.length === 0) return null;

    return (
        <div className="mt-3">
            <p className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2">
                Cinematic Shots ({shots.length})
            </p>
            <div className="grid grid-cols-2 gap-2">
                {shots.map((shot) => (
                    <ShotCard
                        key={shot.id}
                        shot={shot}
                        onAnimate={() => handleAnimate(shot.id)}
                        isAnimating={animatingIds.has(shot.id)}
                    />
                ))}
            </div>
        </div>
    );
}

function ShotCard({
    shot,
    onAnimate,
    isAnimating,
}: {
    shot: ProductShot;
    onAnimate: () => void;
    isAnimating: boolean;
}) {
    const [hovering, setHovering] = useState(false);
    const videoRef = useRef<HTMLVideoElement>(null);

    useEffect(() => {
        if (videoRef.current) {
            if (hovering) {
                videoRef.current.play().catch(() => {});
            } else {
                videoRef.current.pause();
                videoRef.current.currentTime = 0;
            }
        }
    }, [hovering]);

    const statusLabel = {
        image_pending: 'Generating...',
        image_completed: 'Ready',
        animation_pending: 'Animating...',
        animation_completed: 'Video Ready',
        failed: 'Failed',
    }[shot.status];

    const statusColor = {
        image_pending: 'text-yellow-400 bg-yellow-500/10',
        image_completed: 'text-blue-400 bg-blue-500/10',
        animation_pending: 'text-purple-400 bg-purple-500/10',
        animation_completed: 'text-green-400 bg-green-500/10',
        failed: 'text-red-400 bg-red-500/10',
    }[shot.status];

    const isPending = shot.status === 'image_pending' || shot.status === 'animation_pending';

    return (
        <div className="rounded-lg overflow-hidden bg-slate-800/50 border border-white/5 relative">
            {/* Media */}
            <div
                className="aspect-[3/4] relative"
                onMouseEnter={() => setHovering(true)}
                onMouseLeave={() => setHovering(false)}
            >
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
                            <div className="animate-spin w-6 h-6 border-2 border-slate-600 border-t-blue-400 rounded-full" />
                        ) : (
                            <span className="text-slate-600 text-xs">No image</span>
                        )}
                    </div>
                )}

                {/* Spinner overlay for pending animation */}
                {shot.status === 'animation_pending' && shot.image_url && (
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                        <div className="animate-spin w-8 h-8 border-2 border-white/20 border-t-purple-400 rounded-full" />
                    </div>
                )}

                {/* Animate button for completed images */}
                {shot.status === 'image_completed' && (
                    <div className="absolute inset-0 bg-black/40 opacity-0 hover:opacity-100 transition-opacity flex items-center justify-center">
                        <button
                            onClick={(e) => { e.stopPropagation(); onAnimate(); }}
                            disabled={isAnimating}
                            className="bg-purple-500 text-white px-3 py-1.5 rounded-lg text-xs font-medium hover:bg-purple-600 transition-colors disabled:opacity-50"
                        >
                            {isAnimating ? 'Queuing...' : 'Animate'}
                        </button>
                    </div>
                )}
            </div>

            {/* Footer */}
            <div className="p-2 flex items-center justify-between">
                <span className="text-[10px] text-slate-400 capitalize">{shot.shot_type.replace('_', ' ')}</span>
                <span className={`text-[9px] px-1.5 py-0.5 rounded-full font-medium ${statusColor} ${isPending ? 'animate-pulse' : ''}`}>
                    {statusLabel}
                </span>
            </div>

            {/* Error tooltip */}
            {shot.status === 'failed' && shot.error_message && (
                <div className="px-2 pb-2">
                    <p className="text-[9px] text-red-400/70 truncate" title={shot.error_message}>
                        {shot.error_message}
                    </p>
                </div>
            )}
        </div>
    );
}
