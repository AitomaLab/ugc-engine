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
    const [modelApi, setModelApi] = useState('seedance-1.5-pro');
    const [appClipId, setAppClipId] = useState<string>('auto');
    const [duration, setDuration] = useState(15);
    const [campaignName, setCampaignName] = useState('');
    const [contentStrategy, setContentStrategy] = useState('random');
    const [hook, setHook] = useState('');
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [submitting, setSubmitting] = useState(false);
    const [successMessage, setSuccessMessage] = useState('');
    const [hookLoading, setHookLoading] = useState(false);
    const [costEstimate, setCostEstimate] = useState<CostEstimate | null>(null);

    const isCampaignMode = quantity > 1;
    const selectedInf = influencers.find((i) => i.id === selectedInfluencer);
    const selectedScr = scripts.find((s) => s.id === selectedScript);

    // Fetch data
    const fetchData = useCallback(async () => {
        try {
            const [inf, scr, clips] = await Promise.all([
                apiFetch<Influencer[]>('/influencers'),
                apiFetch<Script[]>('/scripts'),
                apiFetch<AppClip[]>('/app-clips'),
            ]);
            setInfluencers(inf);
            setScripts(scr);
            setAppClips(clips);
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
                    }),
                });
                if (res.ok) {
                    setCostEstimate(await res.json());
                }
            } catch { /* silent */ }
        }, 400);
        return () => clearTimeout(timer);
    }, [modelApi, duration, customScript, selectedScript, scriptSource, API_URL]);

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
                        app_clip_id: appClipId !== 'auto' ? appClipId : undefined,
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

            {/* ============ SECTION 2: CONTENT & STYLE ============ */}
            <section className="glass-panel p-6 space-y-5">
                <div>
                    <h3 className="text-sm font-semibold text-slate-200 mb-1">Content & Style</h3>
                    <p className="text-xs text-slate-500">Configure generation parameters.</p>
                </div>

                {/* Script Source */}
                <div>
                    <label className="text-xs text-slate-400 font-medium mb-2 block">Script Source</label>
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

                {/* App Clip */}
                <div>
                    <label className="text-xs text-slate-400 font-medium mb-2 block">App Clip</label>
                    <select
                        value={appClipId}
                        onChange={(e) => setAppClipId(e.target.value)}
                        className="input-field"
                    >
                        <option value="auto">Auto-Select (Recommended)</option>
                        {appClips.map((clip) => (
                            <option key={clip.id} value={clip.id}>
                                {clip.name} ({clip.category || 'General'})
                            </option>
                        ))}
                    </select>
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
            {isCampaignMode && (
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
            )}

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
            {selectedInfluencer && (
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
            )}

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
        </div>
    );
}
