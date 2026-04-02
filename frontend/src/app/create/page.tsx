'use client';

import { Suspense, useState, useRef, useEffect, useMemo } from 'react';
import { apiFetch, formatDate, getApiUrl } from '@/lib/utils';
import { useApp } from '@/providers/AppProvider';
import { useRouter, useSearchParams } from 'next/navigation';
import type { ProductShot } from '@/lib/types';
import Select from '@/components/ui/Select';

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
    name?: string;
    text: string;
    category?: string;
    script_json?: {
        hook?: string;
        methodology?: string;
        target_duration_sec?: number;
        scenes?: { scene_number: number; scene_title?: string; dialogue: string; visual_cue?: string; word_count?: number; estimated_duration_sec?: number; on_screen_text?: string }[];
        name?: string;
    };
    methodology?: string;
    video_length?: number;
    influencer_id?: string;
    product_id?: string;
    source?: string;
    is_trending?: boolean;
    times_used?: number;
    created_at?: string;
}

interface AppClip {
    id: string;
    name: string;
    category?: string;
    video_url: string;
    product_id?: string;
    first_frame_url?: string;
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
    return (
        <Suspense fallback={<div className="empty-state" style={{ padding: '40px' }}><div className="empty-title">Loading Studio...</div></div>}>
            <CreateContent />
        </Suspense>
    );
}

function CreateContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const API_URL = getApiUrl();
    const { refreshWallet } = useApp();

    // Credit costs from backend
    const [creditCosts, setCreditCosts] = useState<Record<string, number>>({});
    useEffect(() => {
        apiFetch<Record<string, number>>('/api/credits/costs').then(setCreditCosts).catch(() => {});
    }, []);

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
    const [generatedScript, setGeneratedScript] = useState('');
    const [isGeneratingScript, setIsGeneratingScript] = useState(false);
    const [scriptTab, setScriptTab] = useState<'ai'|'library'>('ai');
    const [scriptMethodology, setScriptMethodology] = useState<string>('');
    const [linkedClips, setLinkedClips] = useState<AppClip[]>([]);
    const [selectedLinkedClip, setSelectedLinkedClip] = useState<string>('');
    const [modelApi, setModelApi] = useState('veo-3.1-fast');
    const [subtitlesEnabled, setSubtitlesEnabled] = useState<boolean>(true);
    const [subtitleStyle, setSubtitleStyle] = useState<string>('hormozi');
    const [subtitlePlacement, setSubtitlePlacement] = useState<string>('middle');
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

    // ── AI Clone state (new — additive only, does not affect existing state) ────
    const [creatorMode, setCreatorMode]             = useState<'influencer' | 'ai_clone'>('influencer');
    const [userClones, setUserClones]               = useState<any[]>([]);
    const [selectedCloneId, setSelectedCloneId]     = useState<string>('');
    const [selectedLookId, setSelectedLookId]       = useState<string>('');
    const [cloneLooks, setCloneLooks]               = useState<any[]>([]);
    const [isSubmittingClone, setIsSubmittingClone] = useState(false);

    // Initial data load
    useEffect(() => {
        let mounted = true;
        Promise.all([
            apiFetch<Influencer[]>('/influencers').catch(() => []),
            apiFetch<Script[]>('/scripts').catch(() => []),
            apiFetch<AppClip[]>('/app-clips').catch(() => []),
            apiFetch<any[]>('/api/products').catch(() => [])
        ]).then(([infRes, scRes, clipRes, prodRes]) => {
            if (!mounted) return;
            setInfluencers(infRes || []);
            setScripts(scRes || []);
            setAppClips(clipRes || []);
            setProducts(prodRes || []);
            setLoading(false);

            // Fetch user's AI clones (new — additive only)
            apiFetch<any[]>('/api/clones').then(setUserClones).catch(() => {});

            const targetProductId = searchParams.get('product_id');
            if (targetProductId) {
                setProductType('physical');
                setProductId(targetProductId);
            }
            const targetInfId = searchParams.get('influencer_id');
            if (targetInfId) setSelectedInfluencer(targetInfId);
            const targetScrId = searchParams.get('script_id');
            if (targetScrId) {
                setSelectedScript(targetScrId);
                setScriptTab('library');
                setScriptSource('specific');
            }
        });
        return () => { mounted = false; };
    }, [searchParams]);

    // Re-fetch when user switches projects
    useEffect(() => {
        const handler = () => {
            setLoading(true);
            Promise.all([
                apiFetch<Influencer[]>('/influencers').catch(() => []),
                apiFetch<Script[]>('/scripts').catch(() => []),
                apiFetch<AppClip[]>('/app-clips').catch(() => []),
                apiFetch<any[]>('/api/products').catch(() => [])
            ]).then(([infRes, scRes, clipRes, prodRes]) => {
                setInfluencers(infRes || []);
                setScripts(scRes || []);
                setAppClips(clipRes || []);
                setProducts(prodRes || []);
                setLoading(false);
            });
        };
        window.addEventListener('projectChanged', handler);
        return () => window.removeEventListener('projectChanged', handler);
    }, []);

    // Cinematic Product Shots (Step 14)
    const [cinematicShots, setCinematicShots] = useState<ProductShot[]>([]);
    const [selectedCinematicShots, setSelectedCinematicShots] = useState<string[]>([]);

    // Auto-Transition Shots (Workflow B)
    const [enableAutoTransitions, setEnableAutoTransitions] = useState(false);
    const [autoTransitionType, setAutoTransitionType] = useState('match_cut');

    // Fetch animated cinematic shots when a physical product is selected
    useEffect(() => {
        if (productType === 'physical' && productId) {
            apiFetch<ProductShot[]>(`/api/products/${productId}/shots`)
                .then(shots => setCinematicShots((shots || []).filter(s => s.status === 'animation_completed')))
                .catch(() => setCinematicShots([]));
        } else {
            setCinematicShots([]);
            setSelectedCinematicShots([]);
        }
    }, [productType, productId]);

    // Fetch app clips linked to the selected digital product
    useEffect(() => {
        if (productType === 'digital' && productId) {
            apiFetch<AppClip[]>(`/api/app-clips?product_id=${productId}`)
                .then((clips) => {
                    setLinkedClips(clips || []);
                    if (clips && clips.length > 0) {
                        setSelectedLinkedClip(clips[0].id);
                        setAppClipId(clips[0].id);
                    } else {
                        setLinkedClips([]);
                        setSelectedLinkedClip('');
                        setAppClipId('auto');
                    }
                })
                .catch(() => {
                    setLinkedClips([]);
                    setAppClipId('auto');
                });
        }
    }, [productType, productId]);

    // Auto-generate script when product + influencer are selected (both physical and digital)
    useEffect(() => {
        const generateScript = async () => {
            if (!productId) return;

            setIsGeneratingScript(true);
            setGeneratedScript('');
            try {
                const res = await fetch(`${API_URL}/api/scripts/generate`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        product_id: productId,
                        duration,
                        influencer_id: selectedInfluencer || undefined,
                        product_type: productType,
                        methodology: scriptMethodology || undefined,
                    }),
                });
                if (res.ok) {
                    const data = await res.json();
                    // Handle both new script_json and legacy script response
                    let script = '';
                    if (data.script_json && data.script_json.scenes) {
                        script = data.script_json.scenes.map((s: {dialogue:string}) => s.dialogue).join(' ||| ');
                    } else if (data.script) {
                        script = data.script;
                    }
                    setGeneratedScript(script);
                    setCustomScript(script);
                    setScriptSource('custom');
                }
            } catch (err) {
                console.error("Script generation failed", err);
            } finally {
                setIsGeneratingScript(false);
            }
        };

        // Debounce slightly to avoid rapid firing if user is clicking around
        const timer = setTimeout(generateScript, 500);
        return () => clearTimeout(timer);
    }, [productType, productId, duration, selectedInfluencer, API_URL, scriptMethodology]);


    // ... (render)


    const isCampaignMode = quantity > 1;
    const selectedInf = influencers.find((i) => i.id === selectedInfluencer);
    const selectedScr = scripts.find((s) => s.id === selectedScript);

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

    // Generate AI script for digital products
    async function generateDigitalScript() {
        if (!productId || productType !== 'digital') return;
        setIsGeneratingScript(true);
        try {
            const res = await fetch(`${API_URL}/api/scripts/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    product_id: productId,
                    duration,
                    product_type: 'digital',
                    methodology: scriptMethodology || undefined,
                }),
            });
            if (res.ok) {
                const data = await res.json();
                let script = '';
                if (data.script_json && data.script_json.scenes) {
                    script = data.script_json.scenes.map((s: {dialogue:string}) => s.dialogue).join(' ||| ');
                } else if (data.script) {
                    script = data.script;
                }
                setGeneratedScript(script);
                setCustomScript(script);
                setScriptSource('custom');
            }
        } catch { /* silent */ }
        finally { setIsGeneratingScript(false); }
    }

    // Submit
    async function handleSubmit() {
        if (!selectedInfluencer) return;
        if (productType === 'digital' && !appClipId && appClipId !== 'auto') return; // 'auto' is valid for digital
        if (productType === 'physical' && !productId) {
            setSuccessMessage(" Please select a product.");
            return;
        }

        setSubmitting(true);
        setSuccessMessage('');

        try {
            // Determine the base script text depending on mode
            let baseScriptText = '';
            if (productType === 'physical') {
                baseScriptText = customScript || generatedScript || '';
            } else if (scriptSource === 'custom') {
                baseScriptText = customScript || '';
            }

            // Combine hook and base script properly without short-circuiting everything else
            let effectiveHook: string | undefined = undefined;
            if (hook && baseScriptText) {
                effectiveHook = `${hook}\n\n${baseScriptText}`;
            } else if (hook) {
                effectiveHook = hook;
            } else if (baseScriptText) {
                effectiveHook = baseScriptText;
            }

            if (isCampaignMode) {
                // Bulk creation
                // For digital campaigns: omit hook so backend generates a unique script per video
                const bulkHook = (productType === 'digital') ? undefined : effectiveHook;
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
                        product_id: productId || undefined,
                        hook: bulkHook,
                        cinematic_shot_ids: selectedCinematicShots.length > 0 ? selectedCinematicShots : undefined,
                        auto_transition_type: enableAutoTransitions ? autoTransitionType : undefined,
                        subtitles_enabled: subtitlesEnabled,
                        subtitle_style: subtitleStyle,
                        subtitle_placement: subtitlePlacement,
                    }),
                });
                setSuccessMessage(` Campaign "${campaignName || 'Untitled'}" launched with ${quantity} videos!`);
            } else {
                // Single creation
                await apiFetch('/jobs', {
                    method: 'POST',
                    body: JSON.stringify({
                        influencer_id: selectedInfluencer,
                        script_id: scriptSource === 'specific' ? selectedScript : undefined,
                        app_clip_id: (productType === 'digital' && appClipId !== 'auto') ? appClipId : undefined,
                        product_id: productId || undefined,
                        product_type: productType,
                        hook: effectiveHook,
                        model_api: modelApi,
                        assistant_type: selectedInf?.style || 'Travel',
                        length: duration,
                        cinematic_shot_ids: selectedCinematicShots.length > 0 ? selectedCinematicShots : undefined,
                        auto_transition_type: enableAutoTransitions ? autoTransitionType : undefined,
                        subtitles_enabled: subtitlesEnabled,
                        subtitle_style: subtitleStyle,
                        subtitle_placement: subtitlePlacement,
                    }),
                });
                setSuccessMessage(' Video generation started!');
            }

            // Refresh wallet balance so the header credits bar updates
            refreshWallet();

            // Reset after short delay
            setTimeout(() => {
                router.push('/activity');
            }, 2000);
        } catch (err) {
            console.error('Submit error:', err);
            setSuccessMessage(` Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
        } finally {
            setSubmitting(false);
        }
    }

    // ── AI Clone submit (new — completely separate from handleSubmit) ────────────
    async function handleCloneSubmit() {
        if (!selectedCloneId) return;

        // Derive the script text from the LEFT PANEL's script state (same as handleSubmit)
        let scriptText = '';
        if (productType === 'physical') {
            scriptText = customScript || generatedScript || '';
        } else if (scriptSource === 'custom') {
            scriptText = customScript || '';
        }
        // Combine hook + base script
        if (hook && scriptText) {
            scriptText = `${hook}\n\n${scriptText}`;
        } else if (hook) {
            scriptText = hook;
        }

        if (!scriptText.trim()) {
            setSuccessMessage('✗ Please write or generate a script first.');
            return;
        }

        setIsSubmittingClone(true);
        setSuccessMessage('');
        try {
            await apiFetch('/api/clone-jobs', {
                method: 'POST',
                body: JSON.stringify({
                    clone_id: selectedCloneId,
                    look_id: selectedLookId || undefined,
                    product_id: productId || undefined,
                    product_type: productType,
                    script_text: scriptText,
                    duration,
                    subtitles_enabled: subtitlesEnabled,
                    subtitle_style: subtitleStyle,
                    subtitle_placement: subtitlePlacement,
                }),
            });
            setSuccessMessage('✓ AI Clone video generation started!');
            refreshWallet();
            setTimeout(() => router.push('/activity'), 2000);
        } catch (err) {
            setSuccessMessage(`✗ Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
        } finally {
            setIsSubmittingClone(false);
        }
    }

    // Fetch looks when selectedCloneId changes (new)
    useEffect(() => {
        if (selectedCloneId) {
            apiFetch<any[]>(`/api/clones/${selectedCloneId}/looks`)
                .then(setCloneLooks)
                .catch(() => setCloneLooks([]));
        } else {
            setCloneLooks([]);
        }
    }, [selectedCloneId]);

    // Auto-select the first clone if only one exists (new)
    useEffect(() => {
        if (userClones.length >= 1 && !selectedCloneId) {
            setSelectedCloneId(userClones[0].id);
        }
    }, [userClones, selectedCloneId]);

    if (loading) {
        return (
            <div className="content-area">
                <div className="empty-state">
                    <div className="empty-title">Loading creative assets...</div>
                </div>
            </div>
        );
    }

    return (
        <div className="create-layout">
            {/* ──── LEFT PANEL: Configuration ──── */}
            <div className="config-panel">
                <div style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-1)', marginBottom: '20px', letterSpacing: '-0.3px' }}>
                    Create Video
                </div>

                {/* Success Banner */}
                {successMessage && (
                    <div style={{
                        background: successMessage.includes('Error') ? 'rgba(239,68,68,0.1)' : 'rgba(34,197,94,0.1)',
                        border: `1px solid ${successMessage.includes('Error') ? 'rgba(239,68,68,0.3)' : 'rgba(34,197,94,0.3)'}`,
                        borderRadius: 'var(--radius-sm)', padding: '10px 12px', marginBottom: '16px', fontSize: '12px',
                        color: successMessage.includes('Error') ? 'var(--red)' : 'var(--green)', fontWeight: 600
                    }}>
                        {successMessage}
                    </div>
                )}

                {/* STEP 1 — Product */}
                <div className="config-section">
                    <div className="config-step">
                        <div className={`step-num ${productId || appClipId ? 'done' : ''}`}>1</div>
                        <div className="step-text">Choose Product</div>
                    </div>

                    {/* Product Type Pills */}
                    <div className="pill-group" style={{ marginTop: '10px' }}>
                        <button className={`btn-secondary ${productType === 'digital' ? 'active' : ''}`} onClick={() => { setProductType('digital'); setProductId(''); setCustomScript(''); setGeneratedScript(''); }}>
                            Digital App
                        </button>
                        <button className={`btn-secondary ${productType === 'physical' ? 'active' : ''}`} onClick={() => { setProductType('physical'); setProductId(''); setCustomScript(''); setGeneratedScript(''); }}>
                            Physical Product
                        </button>
                    </div>

                    {/* Product Grid */}
                    {productType === 'digital' ? (
                        <div style={{ marginTop: '8px' }}>
                            {/* Step 1: Select Digital Product */}
                            <div style={{ marginBottom: '12px' }}>
                                <div style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-3)', marginBottom: '8px' }}>
                                    Select Digital Product
                                </div>
                                {products.filter(p => p.type === 'digital').length === 0 ? (
                                    <div style={{ fontSize: '12px', color: 'var(--text-3)', fontStyle: 'italic' }}>No digital products found. Add one in Products.</div>
                                ) : (
                                    <div className="product-selector-grid" style={{ maxHeight: '200px', overflowY: 'auto', paddingRight: '4px' }}>
                                        {products.filter(p => p.type === 'digital').map((prod) => (
                                            <div key={prod.id} className={`prod-card ${productId === prod.id ? 'selected' : ''}`} onClick={() => setProductId(prod.id)}>
                                                <div className="prod-thumb" style={prod.image_url ? { backgroundImage: `url(${prod.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : { background: 'var(--blue-light)' }}>
                                                    {!prod.image_url && <svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /></svg>}
                                                </div>
                                                <div className="prod-card-name">{prod.name}</div>
                                                <div className="prod-card-type">Digital</div>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>


{/* App Clips — 9:16 portrait grid */}
{productId && (
    <div style={{ marginTop: '12px' }}>
        <div style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-3)', marginBottom: '8px' }}>
            App Clips
            <span style={{ fontWeight: 400, marginLeft: '6px', color: 'var(--text-3)', textTransform: 'none' }}>(linked to this product)</span>
        </div>

        {linkedClips.length === 0 ? (
            <div>
                <div style={{ fontSize: '12px', color: 'var(--text-3)', fontStyle: 'italic', marginBottom: '8px' }}>
                    No clips linked to this product. Using auto-selection.
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                    {/* Auto card */}
                    <div
                        onClick={() => setAppClipId('auto')}
                        style={{
                            aspectRatio: '9/16',
                            position: 'relative',
                            borderRadius: '8px',
                            overflow: 'hidden',
                            cursor: 'pointer',
                            border: appClipId === 'auto' ? '2px solid var(--blue)' : '2px solid transparent',
                            boxShadow: appClipId === 'auto' ? '0 0 0 2px rgba(51,122,255,0.2)' : 'none',
                            background: 'var(--blue-light)',
                            display: 'flex',
                            flexDirection: 'column',
                            alignItems: 'center',
                            justifyContent: 'center',
                            gap: '6px',
                        }}
                    >
                        <svg viewBox="0 0 24 24" style={{ width: '20px', fill: 'var(--blue)' }}>
                            <polygon points="13,2 3,14 12,14 11,22 21,10 12,10" />
                        </svg>
                        <span style={{ fontSize: '10px', fontWeight: 700, color: 'var(--blue)' }}>Auto</span>
                        <span style={{ fontSize: '9px', color: 'var(--text-3)' }}>Random</span>
                    </div>

                    {appClips.slice(0, 8).map((clip) => (
                        <div
                            key={clip.id}
                            onClick={() => setAppClipId(clip.id)}
                            style={{
                                aspectRatio: '9/16',
                                position: 'relative',
                                borderRadius: '8px',
                                overflow: 'hidden',
                                cursor: 'pointer',
                                border: appClipId === clip.id ? '2px solid var(--blue)' : '2px solid transparent',
                                boxShadow: appClipId === clip.id ? '0 0 0 2px rgba(51,122,255,0.2)' : 'none',
                                background: 'var(--surface-hover)',
                                transition: 'all 0.2s',
                            }}
                        >
                            {clip.video_url ? (
                                <video src={clip.video_url} muted loop playsInline autoPlay
                                    style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
                            ) : (
                                <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--blue-light)' }}>
                                    <svg viewBox="0 0 24 24" style={{ width: '20px', fill: 'var(--blue)' }}>
                                        <rect x="5" y="2" width="14" height="20" rx="2" />
                                    </svg>
                                </div>
                            )}
                            <div style={{
                                position: 'absolute', bottom: 0, left: 0, right: 0,
                                background: 'linear-gradient(to top, rgba(0,0,0,0.85), transparent)',
                                padding: '20px 6px 6px 6px',
                            }}>
                                <div style={{ fontSize: '10px', fontWeight: 700, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                    {clip.name}
                                </div>
                                <div style={{ fontSize: '9px', color: 'rgba(255,255,255,0.7)' }}>
                                    {clip.category || 'Clip'}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </div>
        ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px' }}>
                {linkedClips.map((clip) => (
                    <div
                        key={clip.id}
                        onClick={() => { setSelectedLinkedClip(clip.id); setAppClipId(clip.id); }}
                        style={{
                            aspectRatio: '9/16',
                            position: 'relative',
                            borderRadius: '8px',
                            overflow: 'hidden',
                            cursor: 'pointer',
                            border: selectedLinkedClip === clip.id ? '2px solid var(--blue)' : '2px solid transparent',
                            boxShadow: selectedLinkedClip === clip.id ? '0 0 0 2px rgba(51,122,255,0.2)' : 'none',
                            background: 'var(--surface-hover)',
                            transition: 'all 0.2s',
                        }}
                    >
                        {clip.first_frame_url ? (
                            <img src={clip.first_frame_url} alt={clip.name}
                                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
                        ) : clip.video_url ? (
                            <video src={clip.video_url} muted loop playsInline autoPlay
                                style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
                        ) : (
                            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--blue-light)' }}>
                                <svg viewBox="0 0 24 24" style={{ width: '20px', fill: 'var(--blue)' }}>
                                    <rect x="5" y="2" width="14" height="20" rx="2" />
                                </svg>
                            </div>
                        )}
                        <div style={{
                            position: 'absolute', bottom: 0, left: 0, right: 0,
                            background: 'linear-gradient(to top, rgba(0,0,0,0.85), transparent)',
                            padding: '20px 6px 6px 6px',
                        }}>
                            <div style={{ fontSize: '10px', fontWeight: 700, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                {clip.name}
                            </div>
                            <div style={{ fontSize: '9px', color: 'rgba(255,255,255,0.7)' }}>Linked</div>
                        </div>
                    </div>
                ))}
            </div>
        )}
    </div>
)}
                        </div>
                    ) : (
                        <div style={{ marginTop: '8px' }}>
                            {products.filter(p => !p.type || p.type === 'physical').length === 0 ? (
                                <div style={{ fontSize: '12px', color: 'var(--text-3)' }}>No physical products found. Add one in Products.</div>
                            ) : (
                                <div className="product-selector-grid" style={{ maxHeight: '200px', overflowY: 'auto', paddingRight: '4px' }}>
                                    {products.filter(p => !p.type || p.type === 'physical').map((prod) => (
                                        <div key={prod.id} className={`prod-card ${productId === prod.id ? 'selected' : ''}`} onClick={() => setProductId(prod.id)}>
                                            <div className="prod-thumb" style={prod.image_url ? { backgroundImage: `url(${prod.image_url})`, backgroundSize: 'cover', backgroundPosition: 'center' } : { background: 'var(--blue-light)' }}>
                                                {!prod.image_url && <svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /></svg>}
                                            </div>
                                            <div className="prod-card-name">{prod.name}</div>
                                            <div className="prod-card-type">Physical</div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}
                </div>

                {/* Cinematic Shots (physical products only) */}
                {productType === 'physical' && cinematicShots.length > 0 && (
                    <div className="config-section">
                        <div className="config-label">
                            Cinematic Shots
                            <span style={{ fontSize: '10px', color: 'var(--text-3)', fontWeight: 400 }}>Optional</span>
                        </div>
<div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '8px', marginTop: '12px' }}>
    {cinematicShots.map((shot) => {
        const isSelected = selectedCinematicShots.includes(shot.id);
        return (
            <div
                key={shot.id}
                onClick={() => setSelectedCinematicShots(prev =>
                    isSelected ? prev.filter(id => id !== shot.id) : [...prev, shot.id]
                )}
                style={{
                    aspectRatio: '9/16',
                    position: 'relative',
                    borderRadius: '8px',
                    overflow: 'hidden',
                    cursor: 'pointer',
                    border: isSelected ? '2px solid var(--blue)' : '2px solid transparent',
                    boxShadow: isSelected ? '0 0 0 2px rgba(51,122,255,0.2)' : 'none',
                    background: '#0d1117',
                    transition: 'all 0.2s',
                }}
            >
                {shot.video_url ? (
                    <video src={shot.video_url} autoPlay muted loop playsInline
                        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
                ) : shot.image_url ? (
                    <img src={shot.image_url} alt=""
                        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
                ) : (
                    <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-3)', fontSize: '10px', textAlign: 'center', padding: '8px', lineHeight: 1.2 }}>
                        No Preview
                    </div>
                )}
                <div style={{
                    position: 'absolute', bottom: 0, left: 0, right: 0,
                    background: 'linear-gradient(to top, rgba(0,0,0,0.85), transparent)',
                    padding: '20px 6px 6px 6px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'flex-end',
                }}>
                    <span style={{ fontSize: '10px', fontWeight: 600, color: '#fff', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: '4px' }}>
                        {shot.shot_type.replace('_', ' ')}
                    </span>
                    {isSelected && (
                        <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', flexShrink: 0, fill: 'var(--blue)' }}>
                            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" />
                        </svg>
                    )}
                </div>
            </div>
        );
    })}
</div>
                        {selectedCinematicShots.length > 0 && (
                            <div style={{ fontSize: '10px', color: 'var(--blue)', marginTop: '4px' }}>
                                {selectedCinematicShots.length} shot{selectedCinematicShots.length > 1 ? 's' : ''} selected
                            </div>
                        )}
                    </div>
                )}

                {/* Transition Effects */}
                {productType === 'physical' && productId && selectedCinematicShots.length > 0 && (
                    <div className="config-section">
                        <div className="config-label">
                            Transitions
                            <button onClick={() => setEnableAutoTransitions(!enableAutoTransitions)}
                                style={{ width: 36, height: 20, borderRadius: 10, background: enableAutoTransitions ? 'var(--blue)' : 'var(--border)', position: 'relative', cursor: 'pointer', border: 'none', padding: 0 }}>
                                <span style={{ position: 'absolute', left: 2, top: 2, width: 16, height: 16, borderRadius: '50%', background: 'white', transition: 'transform 0.15s', transform: enableAutoTransitions ? 'translateX(16px)' : 'translateX(0)' }} />
                            </button>
                        </div>
                        {enableAutoTransitions && (
                            <div className="pill-group">
                                {[
                                    { value: 'match_cut', label: 'Match Cut' },
                                    { value: 'whip_pan', label: 'Whip Pan' },
                                    { value: 'focus_pull', label: 'Focus Pull' },
                                ].map((tt) => (
                                    <button key={tt.value} className={`btn-secondary ${autoTransitionType === tt.value ? 'active' : ''}`}
                                        onClick={() => setAutoTransitionType(tt.value)}>
                                        {tt.label}
                                    </button>
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* STEP 2 — Video Count */}
                <div className="config-section">
                    <div className="config-step">
                        <div className={`step-num ${productId ? 'done' : ''}`}>2</div>
                        <div className="step-text">Video Count</div>
                    </div>
                    <div className="video-count-row">
                        <button className="count-btn" onClick={() => setQuantity(Math.max(1, quantity - 1))}>-</button>
                        <div className="count-display">{quantity}</div>
                        <button className="count-btn" onClick={() => setQuantity(Math.min(100, quantity + 1))}>+</button>
                        <div className={`count-label ${isCampaignMode ? 'campaign' : ''}`}>
                            {isCampaignMode ? 'Campaign' : 'Single'}
                        </div>
                    </div>
                    <div className={`count-hint ${isCampaignMode ? 'campaign' : ''}`}>
                        {isCampaignMode ? `Campaign mode: ${quantity} videos` : '2+ to enable campaign mode'}
                    </div>
                </div>

                {/* Campaign Mode */}
                {isCampaignMode && (
                    <div className="config-section">
                        <div className="config-label">Campaign Name</div>
                        <input type="text" className="input-field" value={campaignName} onChange={e => setCampaignName(e.target.value)} placeholder="e.g., Spring Promo" />
                        <div style={{ marginTop: '10px' }}>
                            <div className="config-label">Content Strategy</div>
                            <div className="pill-group">
                                {CONTENT_STRATEGIES.map(s => (
                                    <button key={s.value} className={`btn-secondary ${contentStrategy === s.value ? 'active' : ''}`} onClick={() => setContentStrategy(s.value)}>
                                        {s.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {/* AI MODEL SELECTOR — HIDDEN: Defaulting to Veo 3.1. Uncomment to re-enable.
                <div className="config-section">
                    <div className="config-step">
                        <div className="step-num">3</div>
                        <div className="step-text">AI Model</div>
                    </div>
                    <div className="pill-group">
                        {AI_MODELS.map(model => (
                            <button key={model.value} className={`btn-secondary ${modelApi === model.value ? 'active' : ''}`} onClick={() => setModelApi(model.value)} style={{padding:'8px 16px'}}>
                                {model.label}
                            </button>
                        ))}
                    </div>
                </div>
                */}

                {/* Duration */}
                <div className="config-section">
                    <div className="config-label">Duration</div>
                    <div className="pill-group">
                        {[15, 30].map(d => (
                            <button key={d} className={`btn-secondary ${duration === d ? 'active' : ''}`} onClick={() => setDuration(d)}>
                                {d}s
                            </button>
                        ))}
                    </div>
                </div>

{/* ── SCRIPT ── */}
<div className="config-section">
    <div className="config-step">
        <div className={`step-num ${(customScript || generatedScript || selectedScript) ? 'done' : ''}`}>3</div>
        <div className="step-text">Script</div>
    </div>
    <div style={{ display: 'flex', flexWrap: 'nowrap', gap: '6px', marginBottom: '10px' }}>
        <button
            className={`btn-secondary ${scriptTab === 'ai' ? 'active' : ''}`}
            onClick={() => { setScriptTab('ai'); setScriptSource('custom'); }}
            style={{ whiteSpace: 'nowrap', padding: '6px 14px', fontSize: '12px' }}
        >
            AI Generated
        </button>
        <button
            className={`btn-secondary ${scriptTab === 'library' ? 'active' : ''}`}
            onClick={() => setScriptTab('library')}
            style={{ whiteSpace: 'nowrap', padding: '6px 14px', fontSize: '12px' }}
        >
            From Library ({(() => {
                const sp = products.find(p => p.id === productId);
                const sc = sp?.category || '';
                return scripts.filter(s => {
                    const mp = s.product_id === productId;
                    const mc = sc && s.category && s.category.toLowerCase() === sc.toLowerCase();
                    if (!mp && !mc) return false;
                    if (s.video_length && s.video_length !== duration) return false;
                    return true;
                }).length;
            })()})
        </button>
    </div>

    {scriptTab === 'ai' ? (
        <div>
            {/* Script Style — themed dropdown */}
            <div style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-3)', marginBottom: '6px' }}>
                Script Style
            </div>
            <Select
                value={scriptMethodology}
                onChange={setScriptMethodology}
                style={{ marginBottom: '10px' }}
                options={[
                    { value: '', label: '🎲 Random (Recommended)' },
                    { value: 'Hook/Benefit/CTA', label: 'Hook / Benefit / CTA' },
                    { value: 'Problem/Agitate/Solve', label: 'Problem / Agitate / Solve' },
                    { value: 'Contrarian/Shock', label: 'Contrarian / Shock' },
                    { value: 'Social Proof', label: 'Social Proof' },
                    { value: 'Aspiration/Dream', label: 'Aspiration / Dream' },
                    { value: 'Curiosity/Cliffhanger', label: 'Curiosity / Cliffhanger' },
                ]}
            />

            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '6px' }}>
                <button
                    onClick={productType === 'digital' ? generateDigitalScript : () => {
                        setIsGeneratingScript(true);
                        fetch(`${API_URL}/api/scripts/generate`, {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                product_id: productId,
                                duration,
                                influencer_id: selectedInfluencer || undefined,
                                methodology: scriptMethodology || undefined,
                            }),
                        })
                            .then(res => res.json())
                            .then(data => {
                                let script = '';
                                if (data.script_json && data.script_json.scenes) {
                                    script = data.script_json.scenes.map((s: { dialogue: string }) => s.dialogue).join(' ||| ');
                                } else if (data.script) {
                                    script = data.script;
                                }
                                setGeneratedScript(script);
                                setCustomScript(script);
                                setScriptSource('custom');
                            })
                            .finally(() => setIsGeneratingScript(false));
                    }}
                    disabled={isGeneratingScript || !productId}
                    style={{ fontSize: '11px', color: 'var(--blue)', fontWeight: 600, cursor: 'pointer', background: 'none', border: 'none', opacity: isGeneratingScript ? 0.5 : 1 }}
                >
                    {isGeneratingScript ? 'Generating...' : 'Regenerate'}
                </button>
            </div>

            <textarea
                className="config-textarea"
                rows={6}
                value={isGeneratingScript ? 'Generating compelling script...' : (scriptSource === 'custom' ? customScript : generatedScript)}
                onChange={e => { setCustomScript(e.target.value); setScriptSource('custom'); }}
                placeholder={productType === 'digital'
                    ? 'AI will generate a script based on your product and website...'
                    : 'Select a product to generate a script...'}
                disabled={isGeneratingScript}
                style={{ fontSize: '13px', lineHeight: '1.5' }}
            />
        </div>
    ) : (() => {
        const selectedProduct = products.find(p => p.id === productId);
        const selectedCategory = selectedProduct?.category || '';
        const filtered = scripts.filter(s => {
            const matchesProduct = s.product_id === productId;
            const matchesCategory = selectedCategory && s.category && s.category.toLowerCase() === selectedCategory.toLowerCase();
            if (!matchesProduct && !matchesCategory) return false;
            if (s.video_length && s.video_length !== duration) return false;
            return true;
        }).sort((a, b) => {
            const aMatch = a.product_id === productId ? 1 : 0;
            const bMatch = b.product_id === productId ? 1 : 0;
            return bMatch - aMatch;
        });
        return (
            <div style={{ maxHeight: '300px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '6px' }}>
                {filtered.length === 0 ? (
                    <div style={{ fontSize: '12px', color: 'var(--text-3)', padding: '20px 12px', textAlign: 'center', lineHeight: 1.6 }}>
                        <div style={{ marginBottom: '8px' }}>No scripts found for this product or category{duration ? ` (${duration}s)` : ''}.</div>
                        <div style={{ display: 'flex', gap: '8px', justifyContent: 'center', flexWrap: 'wrap' }}>
                            <button onClick={() => { setScriptTab('ai'); setScriptSource('custom'); }}
                                style={{ fontSize: '11px', color: 'var(--blue)', fontWeight: 600, cursor: 'pointer', background: 'var(--blue-light)', border: '1px solid var(--blue)', borderRadius: 'var(--radius-sm)', padding: '6px 12px' }}>
                                Use AI Generated
                            </button>
                            <button onClick={() => window.open('/scripts', '_blank')}
                                style={{ fontSize: '11px', color: 'var(--text-2)', fontWeight: 600, cursor: 'pointer', background: 'var(--bg-2)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '6px 12px' }}>
                                Go to Scripts Page →
                            </button>
                        </div>
                    </div>
                ) : filtered.map(scr => {
                    const hookText = scr.script_json?.hook || scr.text?.split('|||')[0]?.trim() || scr.name || 'Untitled';
                    const isSelected = selectedScript === scr.id;
                    return (
                        <div key={scr.id}
                            onClick={() => {
                                setSelectedScript(scr.id);
                                setScriptSource('specific');
                                const scenes = scr.script_json?.scenes || [];
                                const fullText = scenes.map(s => s.dialogue).join('\n\n') || scr.text || '';
                                setCustomScript(fullText);
                            }}
                            style={{
                                padding: '10px 12px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', transition: 'all 0.15s',
                                border: isSelected ? '2px solid var(--blue)' : '1px solid var(--border)',
                                background: isSelected ? 'var(--blue-light)' : 'var(--bg-2)',
                            }}>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-1)', marginBottom: '4px', lineHeight: 1.3 }}>
                                &ldquo;{hookText.slice(0, 80)}{hookText.length > 80 ? '...' : ''}&rdquo;
                            </div>
                            <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                                {scr.category && <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(51,122,255,0.1)', color: 'var(--blue)', fontWeight: 500 }}>{scr.category}</span>}
                                {scr.methodology && <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(139,92,246,0.1)', color: '#8B5CF6', fontWeight: 500 }}>{scr.methodology}</span>}
                                {scr.video_length && <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(245,158,11,0.1)', color: '#F59E0B', fontWeight: 500 }}>{scr.video_length}s</span>}
                                {scr.is_trending && <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(22,163,74,0.1)', color: '#16A34A', fontWeight: 500 }}>Trending</span>}
                                {scr.product_id === productId && <span style={{ fontSize: '10px', padding: '2px 6px', borderRadius: '4px', background: 'rgba(51,122,255,0.15)', color: 'var(--blue)', fontWeight: 600 }}>This Product</span>}
                            </div>
                        </div>
                    );
                })}
            </div>
        );
    })()}
</div>

                {/* SUBTITLE CONFIGURATION */}
                <div className="config-section">
                    <div className="config-label" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span>Subtitles</span>
                        <button
                            onClick={() => setSubtitlesEnabled(!subtitlesEnabled)}
                            style={{
                                width: '44px',
                                height: '24px',
                                borderRadius: '12px',
                                border: 'none',
                                cursor: 'pointer',
                                backgroundColor: subtitlesEnabled ? '#337AFF' : '#D1D5DB',
                                position: 'relative' as const,
                                transition: 'background-color 0.2s',
                            }}
                        >
                            <span style={{
                                position: 'absolute' as const,
                                top: '2px',
                                left: subtitlesEnabled ? '22px' : '2px',
                                width: '20px',
                                height: '20px',
                                borderRadius: '50%',
                                backgroundColor: '#FFFFFF',
                                transition: 'left 0.2s',
                                boxShadow: '0 1px 3px rgba(0,0,0,0.2)',
                            }} />
                        </button>
                    </div>

                    {subtitlesEnabled && (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '12px' }}>

                            {/* Style Selector */}
                            <div>
                                <div style={{ marginBottom: '8px', fontSize: '12px', color: '#6B7280' }}>Style</div>
<div style={{ display: 'flex', flexWrap: 'nowrap', gap: '8px' }}>
    {[
        { value: 'hormozi', label: 'Hormozi' },
        { value: 'mrbeast', label: 'MrBeast' },
        { value: 'plain', label: 'Plain' },
    ].map(s => (
        <button
            key={s.value}
            className={`btn-secondary ${subtitleStyle === s.value ? 'active' : ''}`}
            onClick={() => setSubtitleStyle(s.value)}
            style={{ flex: 1, textAlign: 'center', padding: '8px 0' }}
        >
            {s.label}
        </button>
    ))}
</div>
                            </div>

                            {/* Placement Selector */}
                            <div>
                                <div style={{ marginBottom: '8px', fontSize: '12px', color: '#6B7280' }}>Placement</div>
                                <div className="pill-group">
                                    {[
                                        { value: 'top', label: 'Top' },
                                        { value: 'middle', label: 'Middle' },
                                        { value: 'bottom', label: 'Bottom' },
                                    ].map(p => (
                                        <button
                                            key={p.value}
                                            className={`btn-secondary ${subtitlePlacement === p.value ? 'active' : ''}`}
                                            onClick={() => setSubtitlePlacement(p.value)}
                                        >
                                            {p.label}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Live Preview */}
                            <div>
                                <div style={{ marginBottom: '8px', fontSize: '12px', color: '#6B7280' }}>Preview</div>
                                <div style={{
                                    position: 'relative' as const,
                                    width: '100%',
                                    paddingTop: '177.78%',
                                    backgroundColor: '#1a1a2e',
                                    borderRadius: '12px',
                                    overflow: 'hidden',
                                    backgroundImage: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
                                }}>
                                    <div style={{
                                        position: 'absolute' as const,
                                        left: '50%',
                                        transform: 'translateX(-50%)',
                                        width: '90%',
                                        textAlign: 'center' as const,
                                        ...(subtitlePlacement === 'top' ? { top: '8%' } : {}),
                                        ...(subtitlePlacement === 'middle' ? { top: '50%', transform: 'translate(-50%, -50%)' } : {}),
                                        ...(subtitlePlacement === 'bottom' ? { bottom: '12%' } : {}),
                                    }}>
                                        {subtitleStyle === 'hormozi' && (
                                            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '3px' }}>
                                                {['THIS', 'APP', 'IS', 'INSANE'].map((word, i) => (
                                                    <span key={i} style={{
                                                        fontFamily: 'Impact, Arial Black, sans-serif',
                                                        fontSize: '22px',
                                                        fontWeight: 900,
                                                        color: word === 'INSANE' ? '#FFFF00' : '#FFFFFF',
                                                        textShadow: '-2px -2px 0 #000, 2px -2px 0 #000, -2px 2px 0 #000, 2px 2px 0 #000',
                                                        textTransform: 'uppercase' as const,
                                                        display: 'inline-block',
                                                        transform: word === 'INSANE' ? 'scale(1.1)' : 'scale(1)',
                                                    }}>
                                                        {word}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                        {subtitleStyle === 'mrbeast' && (
                                            <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '4px' }}>
                                                {['THIS', 'APP', 'IS', 'INSANE'].map((word, i) => (
                                                    <span key={i} style={{
                                                        fontFamily: 'Arial Black, sans-serif',
                                                        fontSize: '18px',
                                                        fontWeight: 900,
                                                        color: '#FFFFFF',
                                                        backgroundColor: 'rgba(0,0,0,0.75)',
                                                        padding: '2px 8px',
                                                        borderRadius: '6px',
                                                        display: 'inline-block',
                                                    }}>
                                                        {word}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                        {subtitleStyle === 'plain' && (
                                            <span style={{
                                                fontFamily: 'Arial, sans-serif',
                                                fontSize: '16px',
                                                fontWeight: 700,
                                                color: '#FFFFFF',
                                                textShadow: '1px 1px 4px rgba(0,0,0,0.9)',
                                            }}>
                                                This app is insane
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div>

                        </div>
                    )}
                </div>


                {/* Advanced Settings */}
                <div className="config-section">
                    <button onClick={() => setShowAdvanced(!showAdvanced)} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 500, color: 'var(--text-3)', cursor: 'pointer', background: 'none', border: 'none' }}>
                        <svg style={{ width: 12, height: 12, stroke: 'currentColor', fill: 'none', strokeWidth: 2, transform: showAdvanced ? 'rotate(180deg)' : 'none', transition: 'transform 0.15s' }} viewBox="0 0 24 24"><path d="M6 9l6 6 6-6" /></svg>
                        Advanced Settings
                    </button>
                    {showAdvanced && (
                        <div style={{ marginTop: '10px' }}>
                            <div className="config-label">AI Hook</div>
                            <div style={{ display: 'flex', gap: '6px' }}>
                                <input type="text" className="input-field" value={hook} onChange={e => setHook(e.target.value)} placeholder="Optional opening hook..." style={{ flex: 1 }} />
                                <button className="btn-secondary" style={{ fontSize: '11px', whiteSpace: 'nowrap', padding: '6px 12px' }} onClick={generateHook} disabled={!selectedInfluencer || hookLoading}>
                                    {hookLoading ? '...' : 'Generate'}
                                </button>
                            </div>
                        </div>
                    )}
                </div>

                {/* Credit Cost Summary */}
                {(() => {
                    const costKey = `${productType}_${duration}s`;
                    const creditCost = creditCosts[costKey] || 0;
                    return creditCost > 0 ? (
                        <div className="gen-summary">
                            <div className="gen-summary-title">Credit Cost</div>
                            <div className="gen-summary-row"><span>Video Type</span><span style={{ textTransform: 'capitalize' }}>{productType} {duration}s</span></div>
                            <div className="gen-summary-divider" />
                            <div className="gen-summary-total"><span>Per Video</span><span style={{ color: 'var(--blue)', fontWeight: 700 }}>{creditCost} credits</span></div>
                            {isCampaignMode && (
                                <div className="gen-summary-total" style={{ marginTop: '4px' }}><span>Campaign ({quantity})</span><span style={{ color: 'var(--blue)', fontWeight: 700 }}>{creditCost * quantity} credits</span></div>
                            )}
                        </div>
                    ) : null;
                })()}

                {/* Generate Button */}
                <button className="btn-generate" onClick={creatorMode === 'ai_clone' ? handleCloneSubmit : handleSubmit} disabled={creatorMode === 'ai_clone' ? (!selectedCloneId || isSubmittingClone) : (!selectedInfluencer || submitting)}>
                    <svg style={{ width: 16, height: 16, stroke: 'white', fill: 'none', strokeWidth: 2 }} viewBox="0 0 24 24"><polygon points="13,2 3,14 12,14 11,22 21,10 12,10" /></svg>
                    {creatorMode === 'ai_clone'
                        ? (isSubmittingClone ? 'Launching...' : 'Generate AI Clone Video')
                        : (submitting ? 'Launching...' : isCampaignMode ? 'Launch Campaign' : 'Generate Video')}
                    {creatorMode === 'influencer' && creditCosts[`${productType}_${duration}s`] && <span className="credit-cost">{isCampaignMode ? creditCosts[`${productType}_${duration}s`] * quantity : creditCosts[`${productType}_${duration}s`]} cr</span>}
                </button>
            </div>

            {/* ──── RIGHT PANEL: Workspace ──── */}
            <div className="workspace">
                {/* ── Creator Mode Toggle (new — additive only) ─────────────────────────── */}
                <div style={{ display: 'flex', gap: '0', marginBottom: '20px', borderBottom: '1px solid var(--border-soft)' }}>
                    <button
                        onClick={() => setCreatorMode('influencer')}
                        style={{
                            flex: 1, padding: '10px 16px', fontSize: '13px', fontWeight: 600,
                            background: 'none', border: 'none', cursor: 'pointer',
                            borderBottom: creatorMode === 'influencer' ? '2px solid var(--blue)' : '2px solid transparent',
                            color: creatorMode === 'influencer' ? 'var(--blue)' : 'var(--text-3)',
                            transition: 'all 0.15s',
                        }}
                    >
                        AI Influencer
                    </button>
                    <button
                        onClick={() => setCreatorMode('ai_clone')}
                        style={{
                            flex: 1, padding: '10px 16px', fontSize: '13px', fontWeight: 600,
                            background: 'none', border: 'none', cursor: 'pointer',
                            borderBottom: creatorMode === 'ai_clone' ? '2px solid var(--blue)' : '2px solid transparent',
                            color: creatorMode === 'ai_clone' ? 'var(--blue)' : 'var(--text-3)',
                            transition: 'all 0.15s',
                        }}
                    >
                        My AI Clone
                    </button>
                </div>

                {/* Influencer Selector / Onboarding Tutorial */}
                {creatorMode === 'influencer' && (
                <div className="config-section">
                    {influencers.length === 0 ? (
                        <div style={{ padding: '28px 16px' }}>
                            <div style={{ textAlign: 'center', marginBottom: '32px' }}>
                                <div style={{ fontSize: '28px', fontWeight: 800, color: 'var(--text-1)', lineHeight: 1.2, letterSpacing: '-0.5px' }}>
                                    CREATE YOUR FIRST VIDEO
                                </div>
                                <div style={{ fontSize: '16px', color: 'var(--text-2)', marginTop: '8px' }}>
                                    Get started <span style={{ color: 'var(--blue)', fontWeight: 700 }}>in 3 easy steps</span>
                                </div>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '20px' }}>
                                {/* Step 1 */}
                                <a href="/influencers" style={{ textDecoration: 'none', color: 'inherit', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', cursor: 'pointer' }}>
                                    <div style={{ position: 'relative', width: '100%', aspectRatio: '4/5', borderRadius: '16px', overflow: 'hidden', marginBottom: '14px', transition: 'transform 0.2s, box-shadow 0.2s' }} onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(99,102,241,0.3)'; }} onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = ''; }}>
                                        <div style={{ position: 'absolute', top: '12px', left: '12px', width: '34px', height: '34px', borderRadius: '50%', background: '#22c55e', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: '16px', zIndex: 2, boxShadow: '0 2px 8px rgba(34,197,94,0.4)' }}>1</div>
                                        <img src="/tutorial_step1.jpg" alt="Create Influencer" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    </div>
                                    <div style={{ fontWeight: 700, fontSize: '16px', color: 'var(--text-1)', marginBottom: '6px' }}>Create Influencer</div>
                                    <div style={{ fontSize: '13px', color: 'var(--text-3)', lineHeight: 1.5 }}>Upload a photo to create your AI influencer</div>
                                </a>

                                {/* Step 2 */}
                                <a href="/products" style={{ textDecoration: 'none', color: 'inherit', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', cursor: 'pointer' }}>
                                    <div style={{ position: 'relative', width: '100%', aspectRatio: '4/5', borderRadius: '16px', overflow: 'hidden', marginBottom: '14px', transition: 'transform 0.2s, box-shadow 0.2s' }} onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-4px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(245,158,11,0.3)'; }} onMouseLeave={e => { e.currentTarget.style.transform = ''; e.currentTarget.style.boxShadow = ''; }}>
                                        <div style={{ position: 'absolute', top: '12px', left: '12px', width: '34px', height: '34px', borderRadius: '50%', background: '#22c55e', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: '16px', zIndex: 2, boxShadow: '0 2px 8px rgba(34,197,94,0.4)' }}>2</div>
                                        <img src="/tutorial_step2.png" alt="Add Product" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    </div>
                                    <div style={{ fontWeight: 700, fontSize: '16px', color: 'var(--text-1)', marginBottom: '6px' }}>Add Product</div>
                                    <div style={{ fontSize: '13px', color: 'var(--text-3)', lineHeight: 1.5 }}>Add your app or physical product to promote</div>
                                </a>

                                {/* Step 3 */}
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
                                    <div style={{ position: 'relative', width: '100%', aspectRatio: '4/5', borderRadius: '16px', overflow: 'hidden', marginBottom: '14px' }}>
                                        <div style={{ position: 'absolute', top: '12px', left: '12px', width: '34px', height: '34px', borderRadius: '50%', background: '#22c55e', color: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 800, fontSize: '16px', zIndex: 2, boxShadow: '0 2px 8px rgba(34,197,94,0.4)' }}>3</div>
                                        <img src="/tutorial_step3.jpg" alt="Create Video" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    </div>
                                    <div style={{ fontWeight: 700, fontSize: '16px', color: 'var(--text-1)', marginBottom: '6px' }}>Create Video</div>
                                    <div style={{ fontSize: '13px', color: 'var(--text-3)', lineHeight: 1.5 }}>Generate UGC videos with AI — it&apos;s that simple!</div>
                                </div>
                            </div>

                            <div style={{ textAlign: 'center', marginTop: '28px' }}>
                                <a href="/influencers" style={{ display: 'inline-block', padding: '12px 36px', background: 'linear-gradient(135deg, var(--blue) 0%, var(--blue-dark) 100%)', color: 'white', borderRadius: '12px', fontSize: '15px', fontWeight: 700, textDecoration: 'none', boxShadow: '0 4px 16px rgba(51,122,255,0.3)', transition: 'all 0.2s' }}>
                                    Create Influencer →
                                </a>
                            </div>
                        </div>
                    ) : (
                        <>
                            <div className="section-title">Select Influencer</div>
                            <div className="influencer-grid">
                                {influencers.map(inf => (
                                    <div key={inf.id}
                                        className={`inf-card ${selectedInfluencer === inf.id ? 'selected' : ''}`}
                                        onClick={() => setSelectedInfluencer(inf.id)}
                                    >
                                        <div className="inf-thumb" style={inf.image_url ? { backgroundImage: `url(${inf.image_url})` } : { background: 'linear-gradient(135deg, var(--blue) 0%, #6B4EFF 100%)' }}>
                                            <div className="inf-name">{inf.name}</div>
                                        </div>
                                        <div className="inf-check">
                                            <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12" /></svg>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </>
                    )}
                </div>
                )}

                {/* ── AI Clone mode ── */}
                {creatorMode === 'ai_clone' && (
                    <div style={{ marginBottom: '24px' }}>
                        {userClones.length === 0 ? (
                            <div style={{ textAlign: 'center', padding: '32px 16px', background: 'var(--surface)', borderRadius: '12px', border: '1px solid var(--border-soft)' }}>
                                <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-1)', marginBottom: '8px' }}>
                                    No AI Clone set up yet
                                </div>
                                <div style={{ fontSize: '12px', color: 'var(--text-3)', marginBottom: '16px' }}>
                                    Create your AI Clone to generate videos with your own face and voice.
                                </div>
                                <a
                                    href='/influencers?tab=ai_clones'
                                    style={{
                                        display: 'inline-block', padding: '10px 24px',
                                        background: 'var(--blue)', color: 'white',
                                        borderRadius: 'var(--radius-sm)', fontSize: '13px',
                                        fontWeight: 700, textDecoration: 'none',
                                    }}
                                >
                                    Set Up My AI Clone →
                                </a>
                            </div>
                        ) : (
                            <>
                                {/* ── Look selector grid (same layout as influencer selector) ── */}
                                <div className="section-title">Select Look</div>
                                {cloneLooks.length > 0 ? (
                                    <div className="influencer-grid">
                                        {/* Random look card */}
                                        <div
                                            className={`inf-card ${!selectedLookId ? 'selected' : ''}`}
                                            onClick={() => setSelectedLookId('')}
                                        >
                                            <div className="inf-thumb" style={{ background: 'linear-gradient(135deg, var(--blue-light) 0%, var(--blue) 100%)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '6px' }}>
                                                <svg viewBox='0 0 24 24' style={{ width: '24px', fill: 'white' }}>
                                                    <polygon points='13,2 3,14 12,14 11,22 21,10 12,10' />
                                                </svg>
                                                <div className="inf-name">Random</div>
                                            </div>
                                            <div className="inf-check">
                                                <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12" /></svg>
                                            </div>
                                        </div>

                                        {/* Individual look cards */}
                                        {cloneLooks.map(look => (
                                            <div key={look.id}
                                                className={`inf-card ${selectedLookId === look.id ? 'selected' : ''}`}
                                                onClick={() => setSelectedLookId(look.id)}
                                            >
                                                <div className="inf-thumb" style={{ backgroundImage: `url(${look.image_url})` }}>
                                                    <div className="inf-name">{look.label}</div>
                                                </div>
                                                <div className="inf-check">
                                                    <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12" /></svg>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className='empty-state' style={{ padding: '24px' }}>
                                        <div className='empty-title'>No looks yet</div>
                                        <div className='empty-sub'>Upload a portrait photo in the <a href='/influencers?tab=ai_clones' style={{ color: 'var(--blue)' }}>Influencers</a> page to get started.</div>
                                    </div>
                                )}
                                <div style={{ marginTop: '8px', fontSize: '11px', color: 'var(--text-3)' }}>
                                    <a href='/influencers?tab=ai_clones' style={{ color: 'var(--blue)' }}>Manage looks →</a>
                                </div>
                            </>
                        )}
                    </div>
                )}

                {/* Smart Preview */}
                {selectedInfluencer && (
                    <div className="how-it-works" style={{ textAlign: 'left', marginTop: '24px' }}>
                        <div style={{ fontSize: '14px', color: 'var(--text-1)', lineHeight: 1.7 }}>
                            You&apos;re about to create{' '}
                            <strong>{quantity} video{quantity > 1 ? 's' : ''}</strong>{' '}
                            featuring{' '}
                            <span style={{ color: 'var(--blue)', fontWeight: 700 }}>{selectedInf?.name}</span>
                            , using{' '}
                            <strong>{scriptSource === 'random' ? 'random' : scriptSource === 'specific' ? 'a specific' : 'a custom'}</strong>{' '}
                            script and{' '}
                            <span style={{ color: 'var(--blue)', fontWeight: 600 }}>{AI_MODELS.find(m => m.value === modelApi)?.label}</span>.
                            {isCampaignMode && campaignName && (
                                <> Campaign: <strong style={{ color: 'var(--blue)' }}>&quot;{campaignName}&quot;</strong>.</>
                            )}
                            {' '}Estimated time: ~{quantity * 2.5} minutes.
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
