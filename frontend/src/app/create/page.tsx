'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiFetch, getApiUrl } from '@/lib/utils';
import { useRouter } from 'next/navigation';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Influencer {
    id: string;
    name: string;
    description?: string;
    personality?: string;
    image_url?: string;
    style?: string;
}

interface Script {
    id: string;
    text: string;
    category?: string;
}

interface AppClip {
    id: string;
    name: string;
    category?: string;
    video_url: string;
}

interface CostEstimate {
    cost_video: number;
    cost_voice: number;
    cost_music: number;
    cost_processing: number;
    total_cost: number;
}

const AI_MODELS = [
    { value: 'seedance-1.5-pro', label: 'Seedance 1.5 Pro', desc: 'Lip-sync + Spanish · $0.28/clip' },
    { value: 'seedance-2.0', label: 'Seedance 2.0', desc: '2K quality · Faster lip-sync' },
    { value: 'kling-2.6', label: 'Kling 2.6', desc: 'Silent video only' },
    { value: 'veo-3.1-fast', label: 'Veo 3.1 Fast', desc: 'Google · Speech + audio · $0.30/clip' },
    { value: 'veo-3.1', label: 'Veo 3.1', desc: 'Google · Highest quality, slower' },
    { value: 'infinitalk-audio', label: 'InfiniteTalk', desc: 'Realistic lip-sync dialog' },
];

const CONTENT_STRATEGIES = [
    { value: 'random', label: 'Random (Recommended)', desc: 'Each video gets a random script/clip' },
    { value: 'sequential', label: 'Sequential', desc: 'Scripts used in order' },
    { value: 'fixed', label: 'Fixed', desc: 'All videos use the same script' },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CreatePage() {
    const router = useRouter();
    const API_URL = getApiUrl();

    // Data
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [scripts, setScripts] = useState<Script[]>([]);
    const [appClips, setAppClips] = useState<AppClip[]>([]);
    const [loading, setLoading] = useState(true);

    // Form State
    const [selectedInfluencer, setSelectedInfluencer] = useState<string>('');
    const [quantity, setQuantity] = useState(1);
    const [scriptSource, setScriptSource] = useState<'random' | 'specific' | 'custom'>('random');
    const [selectedScript, setSelectedScript] = useState<string>('');
    const [customScript, setCustomScript] = useState('');
    const [generatedScript, setGeneratedScript] = useState('');                 // NEW
    const [isGeneratingScript, setIsGeneratingScript] = useState(false);        // NEW
    const [modelApi, setModelApi] = useState('seedance-1.5-pro');
    const [appClipId, setAppClipId] = useState<string>('');
    const [productId, setProductId] = useState<string>('');
    const [productType, setProductType] = useState<'digital' | 'physical'>('digital');
    const [products, setProducts] = useState<any[]>([]);
    const [duration, setDuration] = useState(15);
    const [campaignName, setCampaignName] = useState('');
    const [contentStrategy, setContentStrategy] = useState('random');
    const [hook, setHook] = useState('');
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [successMessage, setSuccessMessage] = useState('');
    const [hookLoading, setHookLoading] = useState(false);
    const [costEstimate, setCostEstimate] = useState<CostEstimate | any | null>(null);

    // Auto-generate script for physical products
    useEffect(() => {
        const generateScript = async () => {
            if (productType === 'physical' && productId) {
                setIsGeneratingScript(true);
                setGeneratedScript(''); // Clear previous
                try {
                    const res = await fetch(`${API_URL}/api/scripts/generate`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ product_id: productId, duration }),
                    });
                    if (res.ok) {
                        const data = await res.json();
                        setGeneratedScript(data.script);
                        // Auto-switch to custom source so the generated script is used
                        setScriptSource('custom');
                        setCustomScript(data.script);
                    }
                } catch (err) {
                    console.error("Script generation failed", err);
                } finally {
                    setIsGeneratingScript(false);
                }
            }
        };

        // Debounce slightly to avoid rapid firing if user is clicking around
        const timer = setTimeout(generateScript, 500);
        return () => clearTimeout(timer);
    }, [productType, productId, duration, API_URL]);


    // ... (render)


    const isCampaignMode = quantity > 1;
    const selectedInf = influencers.find((i) => i.id === selectedInfluencer);
    const selectedScr = scripts.find((s) => s.id === selectedScript);

    // Fetch data
    const fetchData = useCallback(async () => {
        try {
            const [inf, scr, clips, prods] = await Promise.all([
                apiFetch<Influencer[]>('/influencers'),
                apiFetch<Script[]>('/scripts'),
                apiFetch<AppClip[]>('/app-clips'),
                apiFetch<any[]>('/api/products').then(d => Array.isArray(d) ? d : []).catch(() => []),
            ]);
            setInfluencers(inf);
            setScripts(scr);
            setAppClips(clips);
            setProducts(prods);
        } catch (err) {
            console.error('Create page fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    // Debounced cost estimation
    useEffect(() => {
        const timer = setTimeout(async () => {
            try {
                const scriptText = scriptSource === 'custom' ? customScript : (selectedScr?.text || '');
                const res = await fetch(`${API_URL}/estimate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        script_text: scriptText,
                        duration,
                        model: modelApi,
                        product_type: productType,
                        num_scenes: 2
                    }),
                });
                if (res.ok) {
                    setCostEstimate(await res.json());
                }
            } catch { /* silent */ }
        }, 400);
        return () => clearTimeout(timer);
    }, [modelApi, duration, customScript, selectedScript, scriptSource, productType, API_URL]);

    // Generate AI Hook
    async function generateHook() {
        if (!selectedInfluencer) return;
        setHookLoading(true);
        try {
            const res = await fetch(`${API_URL}/ai/hook`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    influencer_id: selectedInfluencer,
                    category: selectedInf?.style || 'General',
                }),
            });
            if (res.ok) {
                const data = await res.json();
                setHook(data.hook || '');
            }
        } catch { /* silent */ }
        finally { setHookLoading(false); }
    }

    // Submit
    async function handleSubmit() {
        if (!selectedInfluencer) return;
        if (productType === 'digital' && !appClipId && appClipId !== 'auto') return; // 'auto' is valid for digital
        if (productType === 'physical' && !productId) {
            setSuccessMessage("❌ Please select a product.");
            return;
        }

        setSubmitting(true);
        setSuccessMessage('');

        try {
            if (isCampaignMode) {
                // Bulk creation
                await apiFetch('/jobs/bulk', {
                    method: 'POST',
                    body: JSON.stringify({
                        influencer_id: selectedInfluencer,
                        count: quantity,
                        duration,
                        model_api: modelApi,
                        campaign_name: campaignName || undefined,
                        assistant_type: selectedInf?.style || 'Travel',
                        product_type: productType,
                        product_id: productType === 'physical' ? productId : undefined
                    }),
                });
                setSuccessMessage(`🚀 Campaign "${campaignName || 'Untitled'}" launched with ${quantity} videos!`);
            } else {
                // Single creation
                await apiFetch('/jobs', {
                    method: 'POST',
                    body: JSON.stringify({
                        influencer_id: selectedInfluencer,
                        script_id: scriptSource === 'specific' ? selectedScript : undefined,
                        app_clip_id: (productType === 'digital' && appClipId !== 'auto') ? appClipId : undefined,
                        product_id: productType === 'physical' ? productId : undefined,
                        product_type: productType,
                        hook: hook || undefined,
                        model_api: modelApi,
                        assistant_type: selectedInf?.style || 'Travel',
                        length: duration,
                    }),
                });
                setSuccessMessage('🎬 Video generation started!');
            }

            // Reset after short delay
            setTimeout(() => {
                router.push('/activity');
            }, 2000);
        } catch (err) {
            console.error('Submit error:', err);
            setSuccessMessage(`❌ Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
        } finally {
            setSubmitting(false);
        }
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-slate-500 text-sm italic animate-pulse">
                    Loading creative assets...
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-10 animate-slide-up max-w-3xl">
            <header>
                <h2 className="text-3xl font-bold tracking-tight">
                    <span className="gradient-text">Create</span>
                </h2>
                <p className="text-slate-400 mt-2 text-sm">
                    Generate single videos or launch full campaigns — all from one place.
                </p>
            </header>

            {/* Success Banner */}
            {successMessage && (
                <div className={`glass-panel p-4 text-center text-sm font-medium ${successMessage.startsWith('❌') ? 'text-red-400' : 'text-green-400'}`}>
                    {successMessage}
                </div>
            )}

            {/* ============ SECTION 1: WHAT TO CREATE ============ */}
            <section className="glass-panel p-6 space-y-6">
                <div>
                    <h3 className="text-sm font-semibold text-slate-200 mb-1">What do you want to create?</h3>
                    <p className="text-xs text-slate-500">Select an influencer and specify quantity.</p>
                </div>

                {/* Influencer Grid */}
                <div>
                    <label className="text-xs text-slate-400 font-medium mb-3 block">Influencer</label>
                    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                        {influencers.map((inf) => (
                            <button
                                key={inf.id}
                                onClick={() => setSelectedInfluencer(inf.id)}
                                className={`
                  relative p-4 rounded-xl text-left transition-all duration-200
                  ${selectedInfluencer === inf.id
                                        ? 'bg-blue-500/10 border-blue-500/40 ring-1 ring-blue-500/20'
                                        : 'bg-slate-800/30 border-slate-700/30 hover:border-slate-600/50 hover:bg-slate-800/50'
                                    }
                  border
                `}
                            >
                                {inf.image_url ? (
                                    <img
                                        src={inf.image_url}
                                        alt={inf.name}
                                        className="w-12 h-12 rounded-lg object-cover mb-3"
                                    />
                                ) : (
                                    <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center text-blue-400 font-bold text-lg mb-3">
                                        {inf.name[0]}
                                    </div>
                                )}
                                <p className="text-sm font-medium text-slate-200">{inf.name}</p>
                                {inf.style && (
                                    <p className="text-[10px] text-slate-500 mt-0.5">{inf.style}</p>
                                )}
                                {selectedInfluencer === inf.id && (
                                    <div className="absolute top-2 right-2 w-5 h-5 rounded-full bg-blue-500 flex items-center justify-center">
                                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="3">
                                            <path d="M5 13l4 4L19 7" />
                                        </svg>
                                    </div>
                                )}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Quantity */}
                <div>
                    <label className="text-xs text-slate-400 font-medium mb-2 block">
                        How many videos?
                    </label>
                    <div className="flex items-center gap-3">
                        <input
                            type="number"
                            min={1}
                            max={100}
                            value={quantity}
                            onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
                            className="input-field w-24 text-center"
                        />
                        <span className="text-xs text-slate-500">
                            {isCampaignMode
                                ? '→ Campaign mode enabled'
                                : 'Enter 2+ to launch a campaign'}
                        </span>
                    </div>
                </div>
            </section>

            {/* ============ SECTION 2: PRODUCT / APP CLIP ============ */}
            <section className="glass-panel p-6 space-y-6">
                <div>
                    <h3 className="text-sm font-semibold text-slate-200 mb-1">2. Choose Your Product</h3>
                    <p className="text-xs text-slate-500">Select what you want to promote.</p>
                </div>

                {/* Type Switcher */}
                <div className="flex bg-slate-800/50 p-1 rounded-lg w-fit">
                    <button
                        onClick={() => setProductType('digital')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${productType === 'digital' ? 'bg-blue-600 text-white shadow-lg' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                        📱 Digital App
                    </button>
                    <button
                        onClick={() => setProductType('physical')}
                        className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${productType === 'physical' ? 'bg-purple-600 text-white shadow-lg' : 'text-slate-400 hover:text-slate-200'}`}
                    >
                        📦 Physical Product
                    </button>
                </div>

                {/* Grid */}
                {productType === 'digital' ? (
                    <div>
                        <label className="text-xs text-slate-400 font-medium mb-3 block">Select App Clip</label>
                        {appClips.length === 0 ? (
                            <p className="text-slate-500 text-sm italic">No app clips found. Add one in the Library.</p>
                        ) : (
                            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                                <div
                                    onClick={() => setAppClipId('auto')}
                                    className={`cursor-pointer rounded-xl border-2 transition-all p-4 flex flex-col items-center justify-center gap-2 bg-slate-800/20 ${appClipId === 'auto' ? 'border-blue-500 shadow-blue-500/20 shadow-lg' : 'border-dashed border-slate-700/50 hover:border-slate-500'}`}
                                >
                                    <span className="text-2xl">✨</span>
                                    <span className="text-sm font-medium text-slate-300">Auto-Select</span>
                                </div>
                                {appClips.map((clip) => (
                                    <div
                                        key={clip.id}
                                        onClick={() => setAppClipId(clip.id)}
                                        className={`cursor-pointer rounded-xl overflow-hidden border-2 transition-all relative aspect-video bg-slate-800 ${appClipId === clip.id ? 'border-blue-500 shadow-blue-500/20 shadow-lg scale-[1.02]' : 'border-transparent opacity-60 hover:opacity-100'}`}
                                    >
                                        <video src={clip.video_url} className="w-full h-full object-cover" muted />
                                        <div className="absolute bottom-0 left-0 right-0 bg-black/70 p-2">
                                            <p className="text-xs text-white truncate">{clip.name}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                ) : (
                    <div>
                        <label className="text-xs text-slate-400 font-medium mb-3 block">Select Product</label>
                        {products.length === 0 ? (
                            <p className="text-slate-500 text-sm italic">No products found. Add one in the Library.</p>
                        ) : (
                            <div className="grid grid-cols-3 md:grid-cols-4 gap-3">
                                {products.map((prod) => (
                                    <div
                                        key={prod.id}
                                        onClick={() => setProductId(prod.id)}
                                        className={`cursor-pointer rounded-xl overflow-hidden border-2 transition-all relative aspect-[3/4] bg-slate-800 ${productId === prod.id ? 'border-purple-500 shadow-purple-500/20 shadow-lg scale-[1.02]' : 'border-transparent opacity-60 hover:opacity-100'}`}
                                    >
                                        <img src={prod.image_url} alt={prod.name} className="w-full h-full object-cover" />
                                        <div className="absolute bottom-0 left-0 right-0 bg-black/70 p-2">
                                            <p className="text-xs text-white truncate">{prod.name}</p>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                )}
            </section>

            {/* ============ SECTION 3: SCRIPT & STYLE ============ */}
            <section className="glass-panel p-6 space-y-5">
                <div>
                    <h3 className="text-sm font-semibold text-slate-200 mb-1">3. Content & Style</h3>
                    <p className="text-xs text-slate-500">Configure generation parameters.</p>
                </div>

                {/* Script Source */}
                <div>
                    <label className="text-xs text-slate-400 font-medium mb-2 block">Script Source</label>

                    {productType === 'physical' ? (
                        <div className="space-y-2">
                            <div className="flex justify-between items-center mb-1">
                                <span className="text-[10px] uppercase text-purple-400 font-bold tracking-wider">
                                    ✨ AI Generated Script
                                </span>
                                <button
                                    onClick={() => {
                                        // Manually trigger regeneration
                                        setIsGeneratingScript(true);
                                        fetch(`${API_URL}/api/scripts/generate`, {
                                            method: 'POST',
                                            headers: { 'Content-Type': 'application/json' },
                                            body: JSON.stringify({ product_id: productId, duration }),
                                        })
                                            .then(res => res.json())
                                            .then(data => {
                                                setGeneratedScript(data.script);
                                                setCustomScript(data.script);
                                                setScriptSource('custom');
                                            })
                                            .finally(() => setIsGeneratingScript(false));
                                    }}
                                    disabled={isGeneratingScript || !productId}
                                    className="text-xs text-slate-400 hover:text-white transition-colors"
                                >
                                    {isGeneratingScript ? 'Generating...' : '↻ Regenerate'}
                                </button>
                            </div>

                            <textarea
                                value={isGeneratingScript ? 'Generating compelling script for your product...' : (scriptSource === 'custom' ? customScript : generatedScript)}
                                onChange={(e) => {
                                    setCustomScript(e.target.value);
                                    setScriptSource('custom');
                                }}
                                placeholder="Select a product to generate a script..."
                                rows={6}
                                disabled={isGeneratingScript}
                                className={`input-field w-full resize-none font-mono text-sm leading-relaxed ${isGeneratingScript ? 'animate-pulse text-slate-500' : ''}`}
                            />
                            <p className="text-[10px] text-slate-500">
                                This script is tailored to your product&apos;s visual analysis and selected duration.
                            </p>
                        </div>
                    ) : (
                        <>
                            <select
                                value={scriptSource}
                                onChange={(e) => setScriptSource(e.target.value as 'random' | 'specific' | 'custom')}
                                className="input-field"
                            >
                                <option value="random">Random from library (Recommended)</option>
                                <option value="specific">Use a specific script</option>
                                <option value="custom">Write custom script</option>
                            </select>

                            {scriptSource === 'specific' && (
                                <select
                                    value={selectedScript}
                                    onChange={(e) => setSelectedScript(e.target.value)}
                                    className="input-field mt-3"
                                >
                                    <option value="">Select a script...</option>
                                    {scripts.map((s) => (
                                        <option key={s.id} value={s.id}>
                                            {s.text.substring(0, 80)}{s.text.length > 80 ? '...' : ''} ({s.category || 'General'})
                                        </option>
                                    ))}
                                </select>
                            )}

                            {scriptSource === 'custom' && (
                                <textarea
                                    value={customScript}
                                    onChange={(e) => setCustomScript(e.target.value)}
                                    placeholder="Write your script here..."
                                    rows={4}
                                    className="input-field mt-3 resize-none"
                                />
                            )}
                        </>
                    )}
                </div>

                {/* AI Model */}
                <div>
                    <label className="text-xs text-slate-400 font-medium mb-2 block">AI Model</label>
                    <div className="grid grid-cols-2 gap-2">
                        {AI_MODELS.map((model) => (
                            <button
                                key={model.value}
                                onClick={() => setModelApi(model.value)}
                                className={`
                  p-3 rounded-xl text-left transition-all border text-sm
                  ${modelApi === model.value
                                        ? 'bg-blue-500/10 border-blue-500/30 text-white'
                                        : 'bg-slate-800/20 border-slate-700/30 text-slate-400 hover:border-slate-600/50'
                                    }
                `}
                            >
                                <p className="font-medium text-xs">{model.label}</p>
                                <p className="text-[10px] text-slate-500 mt-0.5">{model.desc}</p>
                            </button>
                        ))}
                    </div>
                </div>

                {/* Duration */}
                <div>
                    <label className="text-xs text-slate-400 font-medium mb-2 block">Duration</label>
                    <div className="flex gap-2">
                        {[15, 30].map((d) => (
                            <button
                                key={d}
                                onClick={() => setDuration(d)}
                                className={`
                  px-6 py-2.5 rounded-xl text-sm font-medium transition-all border
                  ${duration === d
                                        ? 'bg-blue-500/10 border-blue-500/30 text-white'
                                        : 'bg-slate-800/20 border-slate-700/30 text-slate-400 hover:border-slate-600/50'
                                    }
                `}
                            >
                                {d}s
                            </button>
                        ))}
                    </div>
                </div>
            </section>

            {/* ============ SECTION 3: CAMPAIGN MODE ============ */}
            {
                isCampaignMode && (
                    <section className="glass-panel p-6 space-y-5 border-blue-500/20">
                        <div>
                            <h3 className="text-sm font-semibold text-blue-400 mb-1">
                                🚀 Campaign Mode
                            </h3>
                            <p className="text-xs text-slate-500">
                                Configure your batch of {quantity} videos.
                            </p>
                        </div>

                        <div>
                            <label className="text-xs text-slate-400 font-medium mb-2 block">Campaign Name</label>
                            <input
                                type="text"
                                value={campaignName}
                                onChange={(e) => setCampaignName(e.target.value)}
                                placeholder="e.g., Spring Promo for Max"
                                className="input-field"
                            />
                        </div>

                        <div>
                            <label className="text-xs text-slate-400 font-medium mb-2 block">Content Strategy</label>
                            <div className="space-y-2">
                                {CONTENT_STRATEGIES.map((strategy) => (
                                    <button
                                        key={strategy.value}
                                        onClick={() => setContentStrategy(strategy.value)}
                                        className={`
                    w-full p-3 rounded-xl text-left transition-all border text-sm
                    ${contentStrategy === strategy.value
                                                ? 'bg-blue-500/10 border-blue-500/30 text-white'
                                                : 'bg-slate-800/20 border-slate-700/30 text-slate-400 hover:border-slate-600/50'
                                            }
                  `}
                                    >
                                        <p className="font-medium text-xs">{strategy.label}</p>
                                        <p className="text-[10px] text-slate-500 mt-0.5">{strategy.desc}</p>
                                    </button>
                                ))}
                            </div>
                        </div>
                    </section>
                )
            }

            {/* ============ ADVANCED SETTINGS ============ */}
            <div>
                <button
                    onClick={() => setShowAdvanced(!showAdvanced)}
                    className="flex items-center gap-2 text-xs text-slate-500 hover:text-slate-300 transition-colors"
                >
                    <svg
                        width="14"
                        height="14"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        className={`transition-transform ${showAdvanced ? 'rotate-180' : ''}`}
                    >
                        <path d="M6 9l6 6 6-6" />
                    </svg>
                    Advanced Settings
                </button>

                {showAdvanced && (
                    <div className="glass-panel p-6 mt-3 space-y-4">
                        <div>
                            <label className="text-xs text-slate-400 font-medium mb-2 block">AI Hook</label>
                            <div className="flex gap-2">
                                <input
                                    type="text"
                                    value={hook}
                                    onChange={(e) => setHook(e.target.value)}
                                    placeholder="Optional opening hook..."
                                    className="input-field flex-1"
                                />
                                <button
                                    onClick={generateHook}
                                    disabled={!selectedInfluencer || hookLoading}
                                    className="btn-secondary text-xs whitespace-nowrap"
                                >
                                    {hookLoading ? '...' : '✨ Generate'}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* ============ SMART PREVIEW ============ */}
            {
                selectedInfluencer && (
                    <section className="glass-panel p-5 border-slate-700/40">
                        <p className="text-sm text-slate-300 leading-relaxed">
                            You&apos;re about to create{' '}
                            <span className="text-white font-semibold">
                                {quantity} video{quantity > 1 ? 's' : ''}
                            </span>{' '}
                            featuring{' '}
                            <span className="text-blue-400 font-semibold">
                                {selectedInf?.name}
                            </span>
                            , using{' '}
                            <span className="text-white">
                                {scriptSource === 'random' ? 'random' : scriptSource === 'specific' ? 'a specific' : 'a custom'}
                            </span>{' '}
                            script and{' '}
                            <span className="text-purple-400 font-medium">
                                {AI_MODELS.find((m) => m.value === modelApi)?.label}
                            </span>
                            .
                            {isCampaignMode && campaignName && (
                                <> Campaign: <span className="text-yellow-400 font-medium">&quot;{campaignName}&quot;</span>.</>
                            )}
                            {' '}Estimated time: ~{quantity * 2.5} minutes.
                        </p>

                        {/* Cost Breakdown */}
                        {costEstimate && (
                            <div className="mt-4 pt-4 border-t border-slate-700/40">
                                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-3">
                                    {[
                                        { label: 'Video', value: costEstimate.cost_video, icon: '🎬' },
                                        { label: 'Voice', value: costEstimate.cost_voice, icon: '🎙️' },
                                        { label: 'Music', value: costEstimate.cost_music, icon: '🎵' },
                                        { label: 'Processing', value: costEstimate.cost_processing, icon: '⚙️' },
                                    ].map((c) => (
                                        <div key={c.label} className="text-center">
                                            <p className="text-[10px] uppercase text-slate-500 tracking-wider">{c.icon} {c.label}</p>
                                            <p className="text-sm font-medium text-slate-300">${c.value.toFixed(3)}</p>
                                        </div>
                                    ))}
                                    {productType === 'physical' && costEstimate.cost_image > 0 && (
                                        <div className="text-center col-span-2 sm:col-span-4 mt-2 border-t border-slate-800 pt-2">
                                            <p className="text-[10px] uppercase text-purple-400 tracking-wider">📸 Product Images (Nano)</p>
                                            <p className="text-sm font-medium text-purple-300">${costEstimate.cost_image.toFixed(3)}</p>
                                        </div>
                                    )}
                                </div>
                                <div className="flex items-center justify-between bg-slate-800/40 rounded-lg px-4 py-2.5">
                                    <span className="text-xs text-slate-400 font-medium">
                                        {isCampaignMode ? 'Cost per video' : 'Estimated Total'}
                                    </span>
                                    <span className="text-lg font-bold text-green-400">
                                        ${costEstimate.total_cost.toFixed(3)}
                                    </span>
                                </div>
                                {isCampaignMode && (
                                    <div className="flex items-center justify-between bg-green-500/5 border border-green-500/15 rounded-lg px-4 py-2.5 mt-2">
                                        <span className="text-xs text-green-400/80 font-medium">
                                            Campaign Total ({quantity} videos)
                                        </span>
                                        <span className="text-xl font-bold text-green-400">
                                            ${(costEstimate.total_cost * quantity).toFixed(2)}
                                        </span>
                                    </div>
                                )}
                            </div>
                        )}
                    </section>
                )
            }

            {/* ============ SUBMIT ============ */}
            <div className="flex items-center gap-4">
                <button
                    onClick={handleSubmit}
                    disabled={!selectedInfluencer || submitting}
                    className="btn-primary px-8 py-3 text-base"
                >
                    {submitting
                        ? 'Launching...'
                        : isCampaignMode
                            ? `🚀 Launch Campaign (${quantity} videos)`
                            : '🎬 Generate Video'}
                </button>
                <button
                    onClick={() => router.push('/')}
                    className="btn-secondary"
                >
                    Cancel
                </button>
            </div>
        </div >
    );
}
