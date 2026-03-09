'use client';

import { useState, useEffect } from 'react';
import { apiFetch } from '@/lib/utils';

const SHOT_TYPES = [
    { value: 'hero', label: 'Hero', desc: 'Classic, centered, well-lit product shot' },
    { value: 'macro_detail', label: 'Macro Detail', desc: 'Extreme close-up on texture and material' },
    { value: 'elevated', label: 'Elevated', desc: 'Elevated on a block, luxurious feel' },
    { value: 'moody_dramatic', label: 'Moody/Dramatic', desc: 'High-contrast, chiaroscuro lighting' },
    { value: 'floating', label: 'Floating', desc: 'Suspended weightlessly, futuristic' },
    { value: 'lifestyle', label: 'Lifestyle', desc: 'Natural setting, ready for use' },
    { value: 'silhouette', label: 'Silhouette', desc: 'Backlit outline, dramatic shape' },
    { value: 'overhead', label: 'Overhead', desc: 'Top-down flat lay composition' },
];

interface Product {
    id: string;
    name: string;
    image_url: string;
}

interface ShotCosts {
    image_generation_cost: number;
    animation_cost: number;
}

export default function GenerateShotModal({
    product,
    onClose,
    onSuccess,
}: {
    product: Product;
    onClose: () => void;
    onSuccess: () => void;
}) {
    const [shotType, setShotType] = useState('hero');
    const [variations, setVariations] = useState(1);
    const [costs, setCosts] = useState<ShotCosts | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        apiFetch<ShotCosts>('/api/shots/costs')
            .then(setCosts)
            .catch(() => setCosts({ image_generation_cost: 0.09, animation_cost: 0.08 }));
    }, []);

    async function handleGenerate() {
        setSubmitting(true);
        setError('');
        try {
            await apiFetch(`/api/products/${product.id}/shots`, {
                method: 'POST',
                body: JSON.stringify({ shot_type: shotType, variations }),
            });
            onSuccess();
            onClose();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Generation failed');
        } finally {
            setSubmitting(false);
        }
    }

    const estimatedCost = costs ? (costs.image_generation_cost * variations).toFixed(2) : '...';

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
            <div
                className="bg-[#0f1115] border border-white/10 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl relative animate-in fade-in zoom-in-95 duration-200"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="p-5 border-b border-[#E8ECF4] flex justify-between items-center bg-gradient-to-r from-blue-500/10 to-transparent">
                    <div className="flex items-center gap-2">
                        <svg className="w-5 h-5 text-[#337AFF]" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                        <h3 className="text-lg font-bold text-white">Generate Cinematic Shots</h3>
                    </div>
                    <button onClick={onClose} className="text-[#4A5568] hover:text-white p-1 hover:bg-white/10 rounded-full transition-colors">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
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
                            <p className="text-xs text-[#94A3B8]">Cinematic product photography</p>
                        </div>
                    </div>

                    {/* Shot Type */}
                    <div>
                        <label className="text-xs text-[#4A5568] font-medium mb-2 block">Shot Type</label>
                        <div className="grid grid-cols-2 gap-2">
                            {SHOT_TYPES.map((st) => (
                                <button
                                    key={st.value}
                                    onClick={() => setShotType(st.value)}
                                    className={`text-left p-3 rounded-xl border transition-all ${
                                        shotType === st.value
                                            ? 'border-[#337AFF] bg-[#337AFF]/10'
                                            : 'border-white/5 bg-white/[0.02] hover:bg-white/5'
                                    }`}
                                >
                                    <p className="text-sm font-medium text-white">{st.label}</p>
                                    <p className="text-[10px] text-[#94A3B8] mt-0.5">{st.desc}</p>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Variations */}
                    <div>
                        <label className="text-xs text-[#4A5568] font-medium mb-2 block">Variations</label>
                        <div className="flex gap-2">
                            {[1, 2, 3, 4].map((n) => (
                                <button
                                    key={n}
                                    onClick={() => setVariations(n)}
                                    className={`flex-1 py-2 rounded-lg text-sm font-medium transition-all ${
                                        variations === n
                                            ? 'bg-blue-500 text-white'
                                            : 'bg-white/5 text-[#4A5568] hover:bg-white/10'
                                    }`}
                                >
                                    {n}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Cost Estimate */}
                    <div className="bg-white/5 rounded-xl p-3 border border-white/5">
                        <div className="flex justify-between items-center">
                            <span className="text-xs text-[#4A5568]">Estimated cost</span>
                            <span className="text-sm font-mono text-green-400">${estimatedCost}</span>
                        </div>
                        <p className="text-[10px] text-[#94A3B8] mt-1">
                            {variations} image{variations > 1 ? 's' : ''} x ${costs?.image_generation_cost?.toFixed(2) ?? '...'}/image. Animation billed separately.
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
                        className="w-full py-3 rounded-xl bg-gradient-to-r from-blue-500 to-purple-500 text-white font-medium text-sm hover:opacity-90 transition-opacity disabled:opacity-50"
                    >
                        {submitting ? 'Generating...' : `Generate ${variations} Shot${variations > 1 ? 's' : ''}`}
                    </button>
                </div>
            </div>
        </div>
    );
}
