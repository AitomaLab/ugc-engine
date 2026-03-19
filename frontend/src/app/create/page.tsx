'use client';

import { Suspense, useState, useRef, useEffect, useMemo } from 'react';
import { apiFetch, formatDate, getApiUrl } from '@/lib/utils';
import { useRouter, useSearchParams } from 'next/navigation';
import type { ProductShot } from '@/lib/types';

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
                        hook: effectiveHook,
                        cinematic_shot_ids: selectedCinematicShots.length > 0 ? selectedCinematicShots : undefined,
                        auto_transition_type: enableAutoTransitions ? autoTransitionType : undefined,
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
                    }),
                });
                setSuccessMessage(' Video generation started!');
            }

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
                        <button className={`pill ${productType === 'digital' ? 'selected' : ''}`} onClick={() => { setProductType('digital'); setProductId(''); setCustomScript(''); setGeneratedScript(''); }}>
                            Digital App
                        </button>
                        <button className={`pill ${productType === 'physical' ? 'selected' : ''}`} onClick={() => { setProductType('physical'); setProductId(''); setCustomScript(''); setGeneratedScript(''); }}>
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
                                    <div className="product-selector-grid">
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

                            {/* Step 2: Generate Script (when product selected) */}
                            {productId && (
                                <div style={{ marginBottom: '12px' }}>
                                    <div style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--blue)', marginBottom: '8px' }}>Script</div>
                                    <div className="pill-group" style={{marginBottom:'10px'}}>
                                        <button className={`pill ${scriptTab === 'ai' ? 'selected' : ''}`} onClick={() => { setScriptTab('ai'); setScriptSource('custom'); }}>AI Generated</button>
                                        <button className={`pill ${scriptTab === 'library' ? 'selected' : ''}`} onClick={() => setScriptTab('library')}>From Library ({(() => { const sp = products.find(p => p.id === productId); const sc = sp?.category || ''; return scripts.filter(s => { const mp = s.product_id === productId; const mc = sc && s.category && s.category.toLowerCase() === sc.toLowerCase(); if (!mp && !mc) return false; if (s.video_length && s.video_length !== duration) return false; return true; }).length; })()})</button>
                                    </div>
                                    {scriptTab === 'ai' ? (
                                        <div>
                                            <div style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-3)', marginBottom: '6px' }}>Script Style</div>
                                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginBottom: '10px' }}>
                                                {['', 'Hook/Benefit/CTA', 'Problem/Agitate/Solve', 'Contrarian/Shock', 'Social Proof', 'Aspiration/Dream', 'Curiosity/Cliffhanger'].map(m => (
                                                    <button key={m} className={`pill ${scriptMethodology === m ? 'selected' : ''}`} onClick={() => setScriptMethodology(m)} style={{fontSize:'11px',padding:'5px 10px'}}>
                                                        {m || '🎲 Random'}
                                                    </button>
                                                ))}
                                            </div>
                                            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '6px' }}>
                                                <button onClick={generateDigitalScript} disabled={isGeneratingScript} style={{ fontSize: '11px', color: 'var(--blue)', fontWeight: 600, cursor: 'pointer', background: 'none', border: 'none', opacity: isGeneratingScript ? 0.5 : 1 }}>
                                                    {isGeneratingScript ? 'Generating...' : 'Regenerate'}
                                                </button>
                                            </div>
                                            <textarea
                                                className="config-textarea"
                                                rows={6}
                                                value={customScript}
                                                onChange={e => { setCustomScript(e.target.value); setScriptSource('custom'); }}
                                                placeholder="AI will generate a script based on your product and website..."
                                                disabled={isGeneratingScript}
                                                style={{ fontSize: '13px', lineHeight: '1.5' }}
                                            />
                                        </div>
                                    ) : (() => {
                                        const selectedProduct = products.find(p => p.id === productId);
                                        const selectedCategory = selectedProduct?.category || '';
                                        const filtered = scripts.filter(s => {
                                            // Only show scripts linked to this product or matching its category
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
                                        <div style={{maxHeight:'250px',overflowY:'auto',display:'flex',flexDirection:'column',gap:'6px'}}>
                                            {filtered.length === 0 ? (
                                                <div style={{fontSize:'12px',color:'var(--text-3)',padding:'20px 12px',textAlign:'center',lineHeight:1.6}}>
                                                    <div style={{marginBottom:'8px'}}>No scripts found for this product or category{duration ? ` (${duration}s)` : ''}.</div>
                                                    <div style={{display:'flex',gap:'8px',justifyContent:'center',flexWrap:'wrap'}}>
                                                        <button onClick={() => { setScriptTab('ai'); setScriptSource('custom'); }} style={{fontSize:'11px',color:'var(--blue)',fontWeight:600,cursor:'pointer',background:'var(--blue-light)',border:'1px solid var(--blue)',borderRadius:'var(--radius-sm)',padding:'6px 12px'}}>Use AI Generated</button>
                                                        <button onClick={() => window.open('/scripts','_blank')} style={{fontSize:'11px',color:'var(--text-2)',fontWeight:600,cursor:'pointer',background:'var(--bg-2)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 12px'}}>Go to Scripts Page →</button>
                                                    </div>
                                                </div>
                                            ) : filtered.map(scr => {
                                                const scrHook = scr.script_json?.hook || scr.text?.split('|||')[0]?.trim() || scr.name || 'Untitled';
                                                const isSel = selectedScript === scr.id;
                                                return (
                                                    <div key={scr.id} onClick={() => {
                                                        setSelectedScript(scr.id);
                                                        setScriptSource('specific');
                                                        const scenes = scr.script_json?.scenes || [];
                                                        const fullText = scenes.map(s => s.dialogue).join('\n\n') || scr.text || '';
                                                        setCustomScript(fullText);
                                                    }} style={{
                                                        padding:'10px 12px',borderRadius:'var(--radius-sm)',cursor:'pointer',transition:'all 0.15s',
                                                        border: isSel ? '2px solid var(--blue)' : '1px solid var(--border)',
                                                        background: isSel ? 'var(--blue-light)' : 'var(--bg-2)',
                                                    }}>
                                                        <div style={{fontSize:'12px',fontWeight:600,color:'var(--text-1)',marginBottom:'4px',lineHeight:1.3}}>&ldquo;{scrHook.slice(0,80)}{scrHook.length>80?'...':''}&rdquo;</div>
                                                        <div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
                                                            {scr.category && <span style={{fontSize:'10px',padding:'2px 6px',borderRadius:'4px',background:'rgba(51,122,255,0.1)',color:'var(--blue)',fontWeight:500}}>{scr.category}</span>}
                                                            {scr.methodology && <span style={{fontSize:'10px',padding:'2px 6px',borderRadius:'4px',background:'rgba(139,92,246,0.1)',color:'#8B5CF6',fontWeight:500}}>{scr.methodology}</span>}
                                                            {scr.video_length && <span style={{fontSize:'10px',padding:'2px 6px',borderRadius:'4px',background:'rgba(245,158,11,0.1)',color:'#F59E0B',fontWeight:500}}>{scr.video_length}s</span>}
                                                            {scr.is_trending && <span style={{fontSize:'10px',padding:'2px 6px',borderRadius:'4px',background:'rgba(22,163,74,0.1)',color:'#16A34A',fontWeight:500}}>Trending</span>}
                                                            {scr.product_id === productId && <span style={{fontSize:'10px',padding:'2px 6px',borderRadius:'4px',background:'rgba(51,122,255,0.15)',color:'var(--blue)',fontWeight:600}}>This Product</span>}
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                        </div>
                                        );
                                    })()}
                                </div>
                            )}

                            {/* Step 3: Select Linked App Clip */}
                            {productId && (
                                <div>
                                    <div style={{ fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.6px', color: 'var(--text-3)', marginBottom: '8px' }}>
                                        App Clip
                                        <span style={{ fontWeight: 400, marginLeft: '4px', color: 'var(--text-3)' }}>(linked to this product)</span>
                                    </div>
                                    {linkedClips.length === 0 ? (
                                        <div>
                                            <div style={{ fontSize: '12px', color: 'var(--text-3)', fontStyle: 'italic', marginBottom: '8px' }}>
                                                No clips linked to this product. Using auto-selection.
                                            </div>
                                            <div className="product-selector-grid">
                                                <div className={`prod-card ${appClipId === 'auto' ? 'selected' : ''}`} onClick={() => setAppClipId('auto')}>
                                                    <div className="prod-thumb" style={{ background: 'var(--blue-light)' }}>
                                                        <svg viewBox="0 0 24 24"><polygon points="13,2 3,14 12,14 11,22 21,10 12,10" /></svg>
                                                    </div>
                                                    <div className="prod-card-name">Auto</div>
                                                    <div className="prod-card-type">Random</div>
                                                </div>
                                                {appClips.slice(0, 8).map((clip) => (
                                                    <div key={clip.id} className={`prod-card ${appClipId === clip.id ? 'selected' : ''}`} onClick={() => setAppClipId(clip.id)}>
                                                        <div className="prod-thumb" style={clip.video_url ? {} : { background: 'var(--blue-light)' }}>
                                                            {clip.video_url ? (
                                                                <video src={clip.video_url} muted loop playsInline autoPlay style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0 }} />
                                                            ) : (
                                                                <svg viewBox="0 0 24 24"><rect x="5" y="2" width="14" height="20" rx="2" /><line x1="12" y1="18" x2="12.01" y2="18" /></svg>
                                                            )}
                                                        </div>
                                                        <div className="prod-card-name">{clip.name}</div>
                                                        <div className="prod-card-type">{clip.category || 'Clip'}</div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="product-selector-grid">
                                            {linkedClips.map((clip) => (
                                                <div key={clip.id} className={`prod-card ${selectedLinkedClip === clip.id ? 'selected' : ''}`} onClick={() => { setSelectedLinkedClip(clip.id); setAppClipId(clip.id); }}>
                                                    <div className="prod-thumb" style={{}}>
                                                        {clip.first_frame_url ? (
                                                            <img src={clip.first_frame_url} alt={clip.name} style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0 }} />
                                                        ) : clip.video_url ? (
                                                            <video src={clip.video_url} muted loop playsInline autoPlay style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0 }} />
                                                        ) : (
                                                            <svg viewBox="0 0 24 24"><rect x="5" y="2" width="14" height="20" rx="2" /><line x1="12" y1="18" x2="12.01" y2="18" /></svg>
                                                        )}
                                                    </div>
                                                    <div className="prod-card-name">{clip.name}</div>
                                                    <div className="prod-card-type">Linked</div>
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
                                <div className="product-selector-grid" style={{ maxHeight: '120px', overflowY: 'auto', paddingRight: '4px' }}>
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
                        <div style={{ display: 'flex', gap: '12px', marginTop: '12px', overflowX: 'auto', paddingBottom: '16px' }} className="no-scrollbar">
                            {cinematicShots.map((shot) => {
                                const isSelected = selectedCinematicShots.includes(shot.id);
                                return (
                                    <div
                                        key={shot.id}
                                        style={{ width: '88px', height: '156px', flexShrink: 0, position: 'relative', borderRadius: '12px', overflow: 'hidden', cursor: 'pointer', border: isSelected ? '2px solid var(--blue)' : '2px solid transparent', boxShadow: isSelected ? '0 0 0 2px rgba(51,122,255,0.2)' : 'none', transition: 'all 0.2s' }}
                                        onClick={() => setSelectedCinematicShots(prev => isSelected ? prev.filter(id => id !== shot.id) : [...prev, shot.id])}
                                    >
                                        {shot.video_url ? (
                                            <video src={shot.video_url} autoPlay muted loop playsInline style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', inset: 0 }} />
                                        ) : shot.image_url ? (
                                            <img src={shot.image_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', inset: 0 }} />
                                        ) : (
                                            <div style={{ width: '100%', height: '100%', backgroundColor: 'var(--surface-hover)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-3)', fontSize: '11px', textAlign: 'center', padding: '8px', lineHeight: 1.2 }}>No Preview</div>
                                        )}
                                        <div style={{ position: 'absolute', bottom: 0, left: 0, right: 0, background: 'linear-gradient(to top, rgba(0,0,0,0.8), transparent)', padding: '24px 8px 8px 8px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', color: 'white', fontSize: '10px', fontWeight: 600 }}>
                                            <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', paddingRight: '4px' }}>{shot.shot_type.replace('_', ' ')}</span>
                                            {isSelected && <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', flexShrink: 0, fill: 'var(--blue)' }}><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z" /></svg>}
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
                                    <button key={tt.value} className={`pill ${autoTransitionType === tt.value ? 'selected' : ''}`}
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
                        <div className={`step-num ${selectedInfluencer ? 'done' : ''}`}>2</div>
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
                                    <button key={s.value} className={`pill ${contentStrategy === s.value ? 'selected' : ''}`} onClick={() => setContentStrategy(s.value)}>
                                        {s.label}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}

                {/* STEP 3 — AI Model */}
                <div className="config-section">
                    <div className="config-step">
                        <div className="step-num">3</div>
                        <div className="step-text">AI Model</div>
                    </div>
                    <div className="pill-group">
                        {AI_MODELS.map(model => (
                            <button key={model.value} className={`pill ${modelApi === model.value ? 'selected' : ''}`} onClick={() => setModelApi(model.value)}>
                                {model.label}
                            </button>
                        ))}
                    </div>
                </div>

                {/* Duration */}
                <div className="config-section">
                    <div className="config-label">Duration</div>
                    <div className="pill-group">
                        {[15, 30].map(d => (
                            <button key={d} className={`pill ${duration === d ? 'selected' : ''}`} onClick={() => setDuration(d)}>
                                {d}s
                            </button>
                        ))}
                    </div>
                </div>

                {/* Script Source — physical products only (digital scripts handled inline in Step 1) */}
                {productType === 'physical' && (
                    <div className="config-section">
                        <div className="config-label">Script</div>
                    <div className="pill-group" style={{marginBottom:'10px'}}>
                        <button className={`pill ${scriptTab === 'ai' ? 'selected' : ''}`} onClick={() => { setScriptTab('ai'); setScriptSource('custom'); }}>AI Generated</button>
                        <button className={`pill ${scriptTab === 'library' ? 'selected' : ''}`} onClick={() => setScriptTab('library')}>From Library ({(() => { const sp = products.find(p => p.id === productId); const sc = sp?.category || ''; return scripts.filter(s => { const mp = s.product_id === productId; const mc = sc && s.category && s.category.toLowerCase() === sc.toLowerCase(); if (!mp && !mc) return false; if (s.video_length && s.video_length !== duration) return false; return true; }).length; })()})</button>
                    </div>
                    {scriptTab === 'ai' ? (
                        <div>
                            <div style={{ fontSize: '10px', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-3)', marginBottom: '6px' }}>Script Style</div>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px', marginBottom: '10px' }}>
                                {['', 'Hook/Benefit/CTA', 'Problem/Agitate/Solve', 'Contrarian/Shock', 'Social Proof', 'Aspiration/Dream', 'Curiosity/Cliffhanger'].map(m => (
                                    <button key={m} className={`pill ${scriptMethodology === m ? 'selected' : ''}`} onClick={() => setScriptMethodology(m)} style={{fontSize:'11px',padding:'5px 10px'}}>
                                        {m || '🎲 Random'}
                                    </button>
                                ))}
                            </div>
                            <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '6px' }}>
                                <button onClick={() => {
                                    setIsGeneratingScript(true);
                                    fetch(`${API_URL}/api/scripts/generate`, {
                                        method: 'POST',
                                        headers: { 'Content-Type': 'application/json' },
                                        body: JSON.stringify({ product_id: productId, duration, influencer_id: selectedInfluencer || undefined, methodology: scriptMethodology || undefined }),
                                    })
                                        .then(res => res.json())
                                        .then(data => {
                                            let script = '';
                                            if (data.script_json && data.script_json.scenes) {
                                                script = data.script_json.scenes.map((s: {dialogue:string}) => s.dialogue).join(' ||| ');
                                            } else if (data.script) {
                                                script = data.script;
                                            }
                                            setGeneratedScript(script); setCustomScript(script); setScriptSource('custom');
                                        })
                                        .finally(() => setIsGeneratingScript(false));
                                }} disabled={isGeneratingScript || !productId} style={{ fontSize: '11px', color: 'var(--blue)', fontWeight: 600, cursor: 'pointer', background: 'none', border: 'none' }}>
                                    {isGeneratingScript ? 'Generating...' : 'Regenerate'}
                                </button>
                            </div>
                            <textarea className="config-textarea" rows={8}
                                value={isGeneratingScript ? 'Generating compelling script...' : (scriptSource === 'custom' ? customScript : generatedScript)}
                                onChange={e => { setCustomScript(e.target.value); setScriptSource('custom'); }}
                                placeholder="Select a product to generate a script..."
                                disabled={isGeneratingScript}
                                style={{ fontSize: '13px', lineHeight: '1.5' }}
                            />
                        </div>
                    ) : (() => {
                        // Smart filtering: match by product + category relevance
                        const selectedProduct = products.find(p => p.id === productId);
                        const selectedCategory = selectedProduct?.category || '';
                        const filtered = scripts.filter(s => {
                            // Only show scripts linked to this product or matching its category
                            const matchesProduct = s.product_id === productId;
                            const matchesCategory = selectedCategory && s.category && s.category.toLowerCase() === selectedCategory.toLowerCase();
                            if (!matchesProduct && !matchesCategory) return false;
                            if (s.video_length && s.video_length !== duration) return false;
                            return true;
                        }).sort((a, b) => {
                            // Scripts linked to the current product come first
                            const aMatch = a.product_id === productId ? 1 : 0;
                            const bMatch = b.product_id === productId ? 1 : 0;
                            return bMatch - aMatch;
                        });
                        return (
                        <div style={{maxHeight:'300px',overflowY:'auto',display:'flex',flexDirection:'column',gap:'6px'}}>
                            {filtered.length === 0 ? (
                                <div style={{fontSize:'12px',color:'var(--text-3)',padding:'20px 12px',textAlign:'center',lineHeight:1.6}}>
                                    <div style={{marginBottom:'8px'}}>No scripts found for this product or category{duration ? ` (${duration}s)` : ''}.</div>
                                    <div style={{display:'flex',gap:'8px',justifyContent:'center',flexWrap:'wrap'}}>
                                        <button onClick={() => { setScriptTab('ai'); setScriptSource('custom'); }} style={{fontSize:'11px',color:'var(--blue)',fontWeight:600,cursor:'pointer',background:'var(--blue-light)',border:'1px solid var(--blue)',borderRadius:'var(--radius-sm)',padding:'6px 12px'}}>Use AI Generated</button>
                                        <button onClick={() => window.open('/scripts','_blank')} style={{fontSize:'11px',color:'var(--text-2)',fontWeight:600,cursor:'pointer',background:'var(--bg-2)',border:'1px solid var(--border)',borderRadius:'var(--radius-sm)',padding:'6px 12px'}}>Go to Scripts Page →</button>
                                    </div>
                                </div>
                            ) : filtered.map(scr => {
                                const hook = scr.script_json?.hook || scr.text?.split('|||')[0]?.trim() || scr.name || 'Untitled';
                                const isSelected = selectedScript === scr.id;
                                return (
                                    <div key={scr.id} onClick={() => {
                                        setSelectedScript(scr.id);
                                        setScriptSource('specific');
                                        const scenes = scr.script_json?.scenes || [];
                                        const fullText = scenes.map(s => s.dialogue).join('\n\n') || scr.text || '';
                                        setCustomScript(fullText);
                                    }} style={{
                                        padding:'10px 12px',borderRadius:'var(--radius-sm)',cursor:'pointer',transition:'all 0.15s',
                                        border: isSelected ? '2px solid var(--blue)' : '1px solid var(--border)',
                                        background: isSelected ? 'var(--blue-light)' : 'var(--bg-2)',
                                    }}>
                                        <div style={{fontSize:'12px',fontWeight:600,color:'var(--text-1)',marginBottom:'4px',lineHeight:1.3}}>&ldquo;{hook.slice(0,80)}{hook.length>80?'...':''}&rdquo;</div>
                                        <div style={{display:'flex',gap:'6px',flexWrap:'wrap'}}>
                                            {scr.category && <span style={{fontSize:'10px',padding:'2px 6px',borderRadius:'4px',background:'rgba(51,122,255,0.1)',color:'var(--blue)',fontWeight:500}}>{scr.category}</span>}
                                            {scr.methodology && <span style={{fontSize:'10px',padding:'2px 6px',borderRadius:'4px',background:'rgba(139,92,246,0.1)',color:'#8B5CF6',fontWeight:500}}>{scr.methodology}</span>}
                                            {scr.video_length && <span style={{fontSize:'10px',padding:'2px 6px',borderRadius:'4px',background:'rgba(245,158,11,0.1)',color:'#F59E0B',fontWeight:500}}>{scr.video_length}s</span>}
                                            {scr.is_trending && <span style={{fontSize:'10px',padding:'2px 6px',borderRadius:'4px',background:'rgba(22,163,74,0.1)',color:'#16A34A',fontWeight:500}}>Trending</span>}
                                            {scr.product_id === productId && <span style={{fontSize:'10px',padding:'2px 6px',borderRadius:'4px',background:'rgba(51,122,255,0.15)',color:'var(--blue)',fontWeight:600}}>This Product</span>}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                        );
                    })()}
                </div>
                )}

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

                {/* Cost Summary */}
                {costEstimate && (
                    <div className="gen-summary">
                        <div className="gen-summary-title">Cost Estimate</div>
                        <div className="gen-summary-row"><span>Video</span><span>${costEstimate.cost_video?.toFixed(3) ?? '0.000'}</span></div>
                        <div className="gen-summary-row"><span>Voice</span><span>${costEstimate.cost_voice?.toFixed(3) ?? '0.000'}</span></div>
                        <div className="gen-summary-row"><span>Music</span><span>${costEstimate.cost_music?.toFixed(3) ?? '0.000'}</span></div>
                        <div className="gen-summary-row"><span>Processing</span><span>${costEstimate.cost_processing?.toFixed(3) ?? '0.000'}</span></div>
                        <div className="gen-summary-divider" />
                        <div className="gen-summary-total"><span>Per Video</span><span>${costEstimate.total_cost?.toFixed(3) ?? '0.000'}</span></div>
                        {isCampaignMode && (
                            <div className="gen-summary-total" style={{ marginTop: '4px' }}><span>Campaign ({quantity})</span><span>${(costEstimate.total_cost * quantity).toFixed(2)}</span></div>
                        )}
                    </div>
                )}

                {/* Generate Button */}
                <button className="btn-generate" onClick={handleSubmit} disabled={!selectedInfluencer || submitting}>
                    <svg style={{ width: 16, height: 16, stroke: 'white', fill: 'none', strokeWidth: 2 }} viewBox="0 0 24 24"><polygon points="13,2 3,14 12,14 11,22 21,10 12,10" /></svg>
                    {submitting ? 'Launching...' : isCampaignMode ? `Launch Campaign (${quantity})` : 'Generate Video'}
                    {costEstimate && <span className="credit-cost">${costEstimate.total_cost?.toFixed(2) ?? '0.00'}</span>}
                </button>
            </div>

            {/* ──── RIGHT PANEL: Workspace ──── */}
            <div className="workspace">
                {/* Influencer Selector */}
                <div className="config-section">
                    <div className="section-title">Select Influencer</div>
                    {influencers.length === 0 ? (
                        <div className="empty-state" style={{ padding: '40px 20px' }}>
                            <div className="empty-icon">
                                <svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" /></svg>
                            </div>
                            <div className="empty-title">No influencers yet</div>
                            <div className="empty-sub">Add an AI influencer profile to get started.</div>
                        </div>
                    ) : (
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
                    )}
                </div>

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
