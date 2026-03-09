'use client';

import { useState } from 'react';
import { apiFetch } from '@/lib/utils';

const TRANSITION_TYPES = [
    {
        value: 'match_cut',
        label: 'Match Cut & Push-In',
        desc: 'Smooth continuous zoom from influencer to product close-up',
    },
    {
        value: 'whip_pan',
        label: 'Whip Pan Reveal',
        desc: 'Fast motion-blurred pan transitioning to the product',
    },
    {
        value: 'focus_pull',
        label: 'Focus Pull',
        desc: 'Background blurs out as the product snaps into sharp focus',
    },
];

const TARGET_STYLES = [
    { value: 'studio_white', label: 'Studio White', desc: 'Clean, bright studio' },
    { value: 'natural_setting', label: 'Natural Setting', desc: 'Outdoor, soft sunlight' },
    { value: 'moody', label: 'Moody', desc: 'Dark, dramatic shadows' },
];

interface Product {
    id: string;
    name: string;
    image_url: string;
}

export default function TransitionShotModal({
    product,
    precedingSceneVideoUrl,
    onClose,
    onSuccess,
}: {
    product: Product;
    precedingSceneVideoUrl: string;
    onClose: () => void;
    onSuccess: () => void;
}) {
    const [transitionType, setTransitionType] = useState('match_cut');
    const [targetStyle, setTargetStyle] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    async function handleGenerate() {
        setSubmitting(true);
        setError('');
        try {
            await apiFetch(`/api/products/${product.id}/transition-shot`, {
                method: 'POST',
                body: JSON.stringify({
                    transition_type: transitionType,
                    target_style: targetStyle,
                    preceding_scene_video_url: precedingSceneVideoUrl,
                }),
            });
            onSuccess();
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Generation failed');
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <div
                className="bg-[#0f1115] border border-white/10 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl relative animate-in fade-in zoom-in-95 duration-200"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="p-5 border-b border-[#E8ECF4] flex justify-between items-center bg-gradient-to-r from-purple-500/10 to-transparent">
                    <div className="flex items-center gap-2">
                        <span className="text-lg">&#x2728;</span>
                        <h3 className="text-lg font-bold text-white">Create a Transition Shot</h3>
                    </div>
                    <button onClick={onClose} className="text-[#4A5568] hover:text-white p-1 hover:bg-white/10 rounded-full transition-colors">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="p-6 space-y-5">
                    {/* Product Info */}
                    <div className="flex items-center gap-3">
                        <div className="w-12 h-12 rounded-lg overflow-hidden bg-white/80 flex-shrink-0">
                            <img src={product.image_url} alt={product.name} className="w-full h-full object-cover" />
                        </div>
                        <div>
                            <p className="text-sm font-medium text-white">{product.name}</p>
                            <p className="text-xs text-[#94A3B8]">Context-aware transition shot</p>
                        </div>
                    </div>

                    {/* Transition Type */}
                    <div>
                        <label className="text-xs text-[#4A5568] font-medium mb-2 block">Transition Type</label>
                        <div className="space-y-2">
                            {TRANSITION_TYPES.map((tt) => (
                                <button
                                    key={tt.value}
                                    onClick={() => setTransitionType(tt.value)}
                                    className={`w-full text-left p-3 rounded-xl border transition-all ${
                                        transitionType === tt.value
                                            ? 'border-purple-500 bg-purple-500/10'
                                            : 'border-white/5 bg-white/[0.02] hover:bg-white/5'
                                    }`}
                                >
                                    <p className="text-sm font-medium text-white">{tt.label}</p>
                                    <p className="text-[10px] text-[#94A3B8] mt-0.5">{tt.desc}</p>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Target Style (Optional) */}
                    <div>
                        <label className="text-xs text-[#4A5568] font-medium mb-2 block">
                            Target Style <span className="text-[#94A3B8]">(Optional)</span>
                        </label>
                        <div className="grid grid-cols-3 gap-2">
                            {TARGET_STYLES.map((ts) => (
                                <button
                                    key={ts.value}
                                    onClick={() => setTargetStyle(targetStyle === ts.value ? null : ts.value)}
                                    className={`text-center p-2.5 rounded-xl border transition-all ${
                                        targetStyle === ts.value
                                            ? 'border-purple-500 bg-purple-500/10'
                                            : 'border-white/5 bg-white/[0.02] hover:bg-white/5'
                                    }`}
                                >
                                    <p className="text-xs font-medium text-white">{ts.label}</p>
                                    <p className="text-[9px] text-[#94A3B8] mt-0.5">{ts.desc}</p>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Info */}
                    <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                        <p className="text-[10px] text-[#94A3B8]">
                            This will analyze the last frame of the preceding scene and generate
                            a cinematic shot that seamlessly blends using a {TRANSITION_TYPES.find(t => t.value === transitionType)?.label.toLowerCase()} transition.
                        </p>
                    </div>

                    {/* Error */}
                    {error && (
                        <p className="text-xs text-red-400 bg-red-500/10 rounded-lg p-2">{error}</p>
                    )}

                    {/* Submit */}
                    <button
                        onClick={handleGenerate}
                        disabled={submitting}
                        className="w-full py-3 rounded-xl bg-gradient-to-r from-purple-500 to-pink-500 text-white font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
                    >
                        {submitting ? 'Creating Transition...' : 'Create Transition Shot'}
                    </button>
                </div>
            </div>
        </div>
    );
}
