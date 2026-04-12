'use client';

import { useState, useEffect, useRef } from 'react';
import { Influencer } from '@/lib/types';
import { apiFetch } from '@/lib/utils';
import { creativeFetch } from '@/lib/creative-os-api';
import { useTranslation } from '@/lib/i18n';

// Supabase URL for constructing public image URLs
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';

interface InfluencerModalProps {
    isOpen: boolean;
    onClose: () => void;
    initialData: Influencer | null;
    onSave: () => void;
}

const PRESET_CATEGORIES = ['Travel', 'Fashion', 'Tech', 'Fitness', 'Food', 'General'];

// Animated progress steps
const GEN_STEPS = [
    'Designing persona...',
    'Building facial structure...',
    'Generating hair and features...',
    'Applying skin texture...',
    'Composing lighting setup...',
    'Setting environment...',
    'Refining details...',
    'Final rendering...',
];

const IDENTITY_STEPS = [
    'Analyzing facial geometry...',
    'Mapping skin details and texture...',
    'Measuring body proportions...',
    'Generating character description...',
    'Building character sheet prompt...',
    'Rendering closeup view...',
    'Rendering front medium view...',
    'Rendering 90° profile view...',
    'Rendering full body view...',
    'Splitting and uploading views...',
    'Finalizing identity...',
];

const GEN_ESTIMATED_SECONDS = 50;
const IDENTITY_ESTIMATED_SECONDS = 90;

export function InfluencerModal({ isOpen, onClose, initialData, onSave }: InfluencerModalProps) {
    const { t } = useTranslation();
    const [name, setName] = useState('');
    const [gender, setGender] = useState('Female');
    const [description, setDescription] = useState('');
    const [style, setStyle] = useState(''); // Category
    const [imageUrl, setImageUrl] = useState('');
    const [voiceId, setVoiceId] = useState('');

    const [uploading, setUploading] = useState(false);
    const [saving, setSaving] = useState(false);

    // Step 1: Generate AI Influencer state
    const [generating, setGenerating] = useState(false);
    const [genStep, setGenStep] = useState(0);
    const genStartRef = useRef<number>(0);
    const [genElapsed, setGenElapsed] = useState(0);

    // Step 2: Generate Identity state
    const [generatingIdentity, setGeneratingIdentity] = useState(false);
    const [idStep, setIdStep] = useState(0);
    const idStartRef = useRef<number>(0);
    const [idElapsed, setIdElapsed] = useState(0);

    // Character sheet views (carousel)
    const [characterViews, setCharacterViews] = useState<string[]>([]);
    const [currentViewIndex, setCurrentViewIndex] = useState(0);

    const fileInputRef = useRef<HTMLInputElement>(null);

    // Timer effect for Step 1 generation
    useEffect(() => {
        if (!generating) { setGenStep(0); setGenElapsed(0); return; }
        genStartRef.current = Date.now();
        const stepInt = setInterval(() => setGenStep(p => p < GEN_STEPS.length - 1 ? p + 1 : p), 5000);
        const timerInt = setInterval(() => setGenElapsed(Math.floor((Date.now() - genStartRef.current) / 1000)), 1000);
        return () => { clearInterval(stepInt); clearInterval(timerInt); };
    }, [generating]);

    // Timer effect for Step 2 identity generation
    useEffect(() => {
        if (!generatingIdentity) { setIdStep(0); setIdElapsed(0); return; }
        idStartRef.current = Date.now();
        const stepInt = setInterval(() => setIdStep(p => p < IDENTITY_STEPS.length - 1 ? p + 1 : p), 7000);
        const timerInt = setInterval(() => setIdElapsed(Math.floor((Date.now() - idStartRef.current) / 1000)), 1000);
        return () => { clearInterval(stepInt); clearInterval(timerInt); };
    }, [generatingIdentity]);

    // Reset form when opening/changing data
    useEffect(() => {
        if (isOpen) {
            if (initialData) {
                setName(initialData.name);
                setGender(initialData.gender || 'Female');
                setDescription(initialData.description || '');
                setStyle(initialData.style || '');
                setImageUrl(initialData.image_url || '');
                setVoiceId(initialData.elevenlabs_voice_id || '');
                setCharacterViews(initialData.character_views || []);
                setCurrentViewIndex(0);
            } else {
                setName(''); setGender('Female'); setDescription('');
                setStyle(''); setImageUrl(''); setVoiceId('');
                setCharacterViews([]); setCurrentViewIndex(0);
            }
        }
    }, [isOpen, initialData]);

    if (!isOpen) return null;

    // Which images to display in the left panel carousel
    // Profile image is ALWAYS first; character sheet views are appended after
    const displayImages: string[] = [];
    if (imageUrl) displayImages.push(imageUrl);
    if (characterViews.length > 0) displayImages.push(...characterViews);
    const hasMultipleViews = displayImages.length > 1;

    // ── Step 1: Generate AI Influencer ──
    async function handleGenerateInfluencer() {
        if (generating) return;
        setGenerating(true);
        try {
            const result = await creativeFetch<{
                name: string; gender: string; age: string; description: string; image_url: string;
            }>('/creative-os/generate/image/generate-influencer', { method: 'POST' });
            if (result) {
                setName(result.name || '');
                setGender(result.gender === 'Male' ? 'Male' : 'Female');
                setDescription(result.description || '');
                setImageUrl(result.image_url || '');
                setCharacterViews([]); // reset any old views
                setCurrentViewIndex(0);
            }
        } catch (err) {
            console.error('Generate influencer failed:', err);
            alert('Failed to generate influencer. Please try again.');
        } finally {
            setGenerating(false);
        }
    }

    // ── Step 2: Generate Identity ──
    async function handleGenerateIdentity() {
        if (generatingIdentity || !imageUrl) return;
        setGeneratingIdentity(true);
        try {
            const result = await creativeFetch<{
                description: string;
                character_sheet_url: string;
                views: string[];
            }>('/creative-os/generate/image/generate-identity', {
                method: 'POST',
                body: JSON.stringify({ image_url: imageUrl }),
            }, 300_000); // 5 min timeout — GPT Vision + NanoBanana + retries + splitting
            if (result) {
                if (result.description) setDescription(result.description);
                if (result.views && result.views.length > 0) {
                    setCharacterViews(result.views);
                    setCurrentViewIndex(0); // Stay on profile photo
                }
            }
        } catch (err) {
            console.error('Generate identity failed:', err);
            alert('Failed to generate identity. Please try again.');
        } finally {
            setGeneratingIdentity(false);
        }
    }

    async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
        if (!e.target.files || e.target.files.length === 0) return;
        const file = e.target.files[0];
        if (!file.type.startsWith('image/')) { alert('Please upload an image file'); return; }
        if (file.size > 5 * 1024 * 1024) { alert('Image must be under 5MB'); return; }
        try {
            setUploading(true);
            const cleanName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_');
            const fileName = `inf_${Date.now()}_${cleanName}`;
            const { signed_url, path } = await apiFetch<{ signed_url: string, path: string }>('/assets/signed-url', {
                method: 'POST', body: JSON.stringify({ bucket: 'influencer-images', file_name: fileName }),
            });
            const uploadRes = await fetch(signed_url, { method: 'PUT', body: file, headers: { 'Content-Type': file.type } });
            if (!uploadRes.ok) throw new Error('Upload failed');
            const publicUrl = `${SUPABASE_URL}/storage/v1/object/public/influencer-images/${path}`;
            setImageUrl(publicUrl);
        } catch (err) {
            console.error('Upload Error:', err); alert('Failed to upload image. Please try again.');
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    }

    async function handleSave() {
        if (!name.trim()) return;
        try {
            setSaving(true);
            const payload: Record<string, unknown> = {
                name, gender, description, style,
                image_url: imageUrl,
                elevenlabs_voice_id: voiceId,
            };
            if (characterViews.length > 0) {
                payload.character_views = characterViews;
            }
            if (initialData) {
                await apiFetch(`/influencers/${initialData.id}`, { method: 'PUT', body: JSON.stringify(payload) });
            } else {
                await apiFetch('/influencers', { method: 'POST', body: JSON.stringify(payload) });
            }
            onSave(); onClose();
        } catch (err) {
            console.error('Save Error:', err); alert('Failed to save influencer.');
        } finally { setSaving(false); }
    }

    // Carousel navigation
    const goToPrev = () => setCurrentViewIndex(i => Math.max(0, i - 1));
    const goToNext = () => setCurrentViewIndex(i => Math.min(displayImages.length - 1, i + 1));

    // Which overlay to show
    const isLoading = uploading || generating || generatingIdentity;
    const activeSteps = generatingIdentity ? IDENTITY_STEPS : GEN_STEPS;
    const activeStep = generatingIdentity ? idStep : genStep;
    const activeElapsed = generatingIdentity ? idElapsed : genElapsed;
    const activeEstimated = generatingIdentity ? IDENTITY_ESTIMATED_SECONDS : GEN_ESTIMATED_SECONDS;

    // View labels for the carousel dots — profile photo first, then 4 character views
    const allViewLabels = ['Profile Photo', 'Closeup', 'Front', 'Profile', 'Full Body'];
    const getViewLabel = (idx: number) => {
        if (characterViews.length === 0) return 'Profile Photo';
        return allViewLabels[idx] || `View ${idx + 1}`;
    };

    return (
        <>
            {/* Backdrop */}
            <div
                onClick={onClose}
                style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
                    backdropFilter: 'blur(6px)', zIndex: 9999, animation: 'infModalFadeIn 0.2s ease',
                }}
            />

            {/* Modal */}
            <div style={{
                position: 'fixed', top: '50%', left: '50%',
                transform: 'translate(-50%, -50%)',
                width: '94vw', maxWidth: '860px', height: '90vh', maxHeight: '700px',
                background: '#FFF', borderRadius: '20px',
                boxShadow: '0 32px 80px rgba(0,0,0,0.25)', zIndex: 10000,
                display: 'flex', overflow: 'hidden',
                animation: 'infModalScaleIn 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
            }}>

                {/* ── Left: Image Preview Panel with Carousel ── */}
                <div style={{
                    flex: '0 0 340px', background: '#0D1117',
                    display: 'flex', flexDirection: 'column',
                    overflow: 'hidden', position: 'relative',
                }}>
                    {/* Hidden file input */}
                    <input type="file" ref={fileInputRef} onChange={handleFileSelect} style={{ display: 'none' }} accept="image/*" />

                    {/* Main image area — fills entire left panel */}
                    <div style={{
                        flex: 1, display: 'flex', alignItems: 'center',
                        justifyContent: 'center', padding: '16px', position: 'relative',
                    }}>
                        <div
                            onClick={displayImages.length === 0 && !isLoading ? () => fileInputRef.current?.click() : undefined}
                            style={{
                                width: '100%', aspectRatio: '9 / 16', borderRadius: '14px',
                                overflow: 'hidden', display: 'flex', alignItems: 'center',
                                justifyContent: 'center', position: 'relative',
                                cursor: displayImages.length === 0 && !isLoading ? 'pointer' : 'default',
                                background: displayImages.length > 0 ? 'transparent'
                                    : 'linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)',
                                border: displayImages.length > 0 ? 'none' : '1.5px dashed rgba(255,255,255,0.15)',
                                transition: 'border-color 0.2s, background 0.2s',
                            }}
                            onMouseEnter={e => {
                                if (displayImages.length === 0 && !isLoading) {
                                    e.currentTarget.style.borderColor = 'rgba(139, 92, 246, 0.4)';
                                    e.currentTarget.style.background = 'linear-gradient(180deg, rgba(139,92,246,0.08) 0%, rgba(139,92,246,0.03) 100%)';
                                }
                            }}
                            onMouseLeave={e => {
                                if (displayImages.length === 0) {
                                    e.currentTarget.style.borderColor = 'rgba(255,255,255,0.15)';
                                    e.currentTarget.style.background = 'linear-gradient(180deg, rgba(255,255,255,0.06) 0%, rgba(255,255,255,0.02) 100%)';
                                }
                            }}
                        >
                            {displayImages.length > 0 ? (
                                <img
                                    key={displayImages[currentViewIndex]}
                                    src={displayImages[currentViewIndex]}
                                    alt={`View ${currentViewIndex + 1}`}
                                    style={{
                                        width: '100%', height: '100%', objectFit: 'cover', display: 'block',
                                        animation: 'infStepFade 0.3s ease',
                                    }}
                                />
                            ) : (
                                /* Empty state — click to upload */
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                                    <div style={{
                                        width: '48px', height: '48px', borderRadius: '50%',
                                        border: '1.5px dashed rgba(255,255,255,0.2)',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    }}>
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="2" strokeLinecap="round">
                                            <line x1="12" y1="5" x2="12" y2="19" />
                                            <line x1="5" y1="12" x2="19" y2="12" />
                                        </svg>
                                    </div>
                                    <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)', fontWeight: 500 }}>
                                        Click to upload image
                                    </span>
                                    <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)', fontWeight: 400 }}>
                                        9:16 Profile Photo
                                    </span>
                                </div>
                            )}

                            {/* Remove button — small overlay on top-right of image */}
                            {displayImages.length > 0 && !isLoading && (
                                <button
                                    onClick={(e) => { e.stopPropagation(); setImageUrl(''); setCharacterViews([]); setCurrentViewIndex(0); }}
                                    title="Remove image"
                                    style={{
                                        position: 'absolute', top: '8px', right: '8px',
                                        width: '26px', height: '26px', borderRadius: '50%',
                                        background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
                                        border: 'none', cursor: 'pointer', display: 'flex',
                                        alignItems: 'center', justifyContent: 'center', padding: 0,
                                        opacity: 0.6, transition: 'opacity 0.15s',
                                    }}
                                    onMouseEnter={e => (e.currentTarget.style.opacity = '1')}
                                    onMouseLeave={e => (e.currentTarget.style.opacity = '0.6')}
                                >
                                    <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="#f87171" strokeWidth="2" strokeLinecap="round">
                                        <line x1="1" y1="1" x2="11" y2="11" /><line x1="11" y1="1" x2="1" y2="11" />
                                    </svg>
                                </button>
                            )}

                            {/* Carousel arrows */}
                            {hasMultipleViews && !isLoading && (
                                <>
                                    {currentViewIndex > 0 && (
                                        <button
                                            onClick={goToPrev}
                                            style={{
                                                position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)',
                                                width: '32px', height: '32px', borderRadius: '50%',
                                                background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
                                                border: 'none', cursor: 'pointer', display: 'flex',
                                                alignItems: 'center', justifyContent: 'center',
                                                color: 'white', fontSize: '14px',
                                            }}
                                        >
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round"><path d="M15 18l-6-6 6-6"/></svg>
                                        </button>
                                    )}
                                    {currentViewIndex < displayImages.length - 1 && (
                                        <button
                                            onClick={goToNext}
                                            style={{
                                                position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)',
                                                width: '32px', height: '32px', borderRadius: '50%',
                                                background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
                                                border: 'none', cursor: 'pointer', display: 'flex',
                                                alignItems: 'center', justifyContent: 'center',
                                                color: 'white', fontSize: '14px',
                                            }}
                                        >
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round"><path d="M9 18l6-6-6-6"/></svg>
                                        </button>
                                    )}
                                </>
                            )}

                            {/* Loading overlay — uploading */}
                            {uploading && !generating && !generatingIdentity && (
                                <div style={{
                                    position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)',
                                    backdropFilter: 'blur(4px)', display: 'flex', flexDirection: 'column',
                                    alignItems: 'center', justifyContent: 'center', gap: '12px', borderRadius: '14px',
                                }}>
                                    <div style={{ width: '28px', height: '28px', border: '2.5px solid rgba(255,255,255,0.2)', borderTopColor: 'white', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                                    <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.7)', fontWeight: 500 }}>Uploading...</span>
                                </div>
                            )}

                            {/* Loading overlay — generating (Step 1 or Step 2) with animated steps */}
                            {(generating || generatingIdentity) && (
                                <div style={{
                                    position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.7)',
                                    backdropFilter: 'blur(6px)', display: 'flex', flexDirection: 'column',
                                    alignItems: 'center', justifyContent: 'center', gap: '16px',
                                    borderRadius: '14px', padding: '24px',
                                }}>
                                    <div style={{
                                        width: '32px', height: '32px',
                                        border: '2.5px solid rgba(139, 92, 246, 0.25)', borderTopColor: '#a78bfa',
                                        borderRadius: '50%', animation: 'spin 1s linear infinite',
                                    }} />
                                    <span key={activeStep} style={{
                                        fontSize: '13px', color: 'rgba(255,255,255,0.9)', fontWeight: 600,
                                        textAlign: 'center', lineHeight: 1.4, animation: 'infStepFade 0.4s ease',
                                    }}>
                                        {activeSteps[activeStep]}
                                    </span>
                                    <div style={{ width: '80%', height: '3px', borderRadius: '2px', background: 'rgba(255,255,255,0.1)', overflow: 'hidden' }}>
                                        <div style={{
                                            height: '100%', borderRadius: '2px',
                                            background: 'linear-gradient(90deg, #8b5cf6, #a78bfa)',
                                            width: `${Math.min((activeElapsed / activeEstimated) * 100, 95)}%`,
                                            transition: 'width 1s linear',
                                        }} />
                                    </div>
                                    <span style={{ fontSize: '11px', color: 'rgba(255,255,255,0.45)', fontWeight: 500 }}>
                                        {activeElapsed < activeEstimated
                                            ? `~${activeEstimated - activeElapsed}s remaining`
                                            : 'Almost done...'}
                                    </span>
                                </div>
                            )}
                        </div>

                        {/* Dot indicators for carousel */}
                        {hasMultipleViews && !isLoading && (
                            <div style={{
                                position: 'absolute', bottom: '24px', left: 0, right: 0,
                                display: 'flex', justifyContent: 'center', gap: '6px',
                            }}>
                                {displayImages.map((_, i) => (
                                    <button
                                        key={i}
                                        onClick={() => setCurrentViewIndex(i)}
                                        style={{
                                            width: i === currentViewIndex ? '20px' : '6px',
                                            height: '6px', borderRadius: '3px', border: 'none',
                                            background: i === currentViewIndex ? '#a78bfa' : 'rgba(255,255,255,0.3)',
                                            cursor: 'pointer', padding: 0, transition: 'all 0.2s',
                                        }}
                                    />
                                ))}
                            </div>
                        )}

                        {/* View label */}
                        {hasMultipleViews && !isLoading && (
                            <div style={{
                                position: 'absolute', bottom: '34px', left: 0, right: 0,
                                textAlign: 'center',
                            }}>
                                <span style={{
                                    fontSize: '10px', fontWeight: 600, color: 'rgba(255,255,255,0.5)',
                                    textTransform: 'uppercase', letterSpacing: '0.5px',
                                }}>
                                    {getViewLabel(currentViewIndex)}
                                </span>
                            </div>
                        )}
                    </div>
                </div>

                {/* ── Right: Config Panel ── */}
                <div style={{
                    flex: '1 1 auto', padding: '24px 24px 20px',
                    display: 'flex', flexDirection: 'column', overflowY: 'auto', position: 'relative',
                }}>
                    {/* Header */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
                        <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-1, #0D1B3E)', margin: 0, letterSpacing: '-0.2px' }}>
                            {initialData ? t('influencer.editTitle') : t('influencer.addTitle')}
                        </h3>
                        <button
                            onClick={onClose}
                            style={{
                                width: '30px', height: '30px', borderRadius: '50%', border: 'none',
                                background: 'rgba(0,0,0,0.05)', cursor: 'pointer',
                                display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 0,
                                transition: 'background 0.15s', flexShrink: 0,
                            }}
                            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.1)')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.05)')}
                        >
                            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="#666" strokeWidth="2" strokeLinecap="round">
                                <line x1="1" y1="1" x2="11" y2="11" /><line x1="11" y1="1" x2="1" y2="11" />
                            </svg>
                        </button>
                    </div>

                    {/* ── STEP 1: Generate AI Influencer — only in create mode ── */}
                    {!initialData && (
                        <button
                            onClick={handleGenerateInfluencer}
                            disabled={generating || generatingIdentity}
                            id="generate-influencer-btn"
                            style={{
                                width: '100%', padding: '11px 16px', borderRadius: '10px',
                                border: '1px solid transparent',
                                background: generating
                                    ? 'linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(99, 102, 241, 0.15))'
                                    : 'linear-gradient(135deg, rgba(139, 92, 246, 0.10), rgba(99, 102, 241, 0.10))',
                                color: 'var(--purple, #8b5cf6)', fontSize: '13px', fontWeight: 600,
                                cursor: generating || generatingIdentity ? 'default' : 'pointer',
                                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                                transition: 'all 0.2s', opacity: generating ? 0.8 : 1, marginBottom: '16px',
                            }}
                            onMouseEnter={(e) => { if (!generating && !generatingIdentity) (e.currentTarget as HTMLButtonElement).style.background = 'linear-gradient(135deg, rgba(139, 92, 246, 0.20), rgba(99, 102, 241, 0.20))'; }}
                            onMouseLeave={(e) => { if (!generating && !generatingIdentity) (e.currentTarget as HTMLButtonElement).style.background = 'linear-gradient(135deg, rgba(139, 92, 246, 0.10), rgba(99, 102, 241, 0.10))'; }}
                        >
                            {generating ? (
                                <><div style={{ width: '14px', height: '14px', border: '2px solid rgba(139,92,246,0.3)', borderTopColor: '#8b5cf6', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> Generating influencer...</>
                            ) : (
                                <>
                                    <svg width="14" height="14" viewBox="40 40 300 300" fill="currentColor" style={{display:'inline',verticalAlign:'-1px'}}><path d="M67.27 185.02L52.28 189.16L67.27 193.29C124.52 209.07 169.24 253.79 185.02 311.04L189.15 326.03L193.29 311.04C209.07 253.79 253.79 209.07 311.04 193.29L326.03 189.16L311.04 185.02C253.79 169.24 209.07 124.52 193.29 67.27L189.15 52.28L185.02 67.27C169.24 124.52 124.52 169.24 67.27 185.02Z"/></svg>
                                    Generate AI Influencer
                                </>
                            )}
                        </button>
                    )}

                    {/* Form Fields */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', flex: 1 }}>

                        {/* Name */}
                        <div>
                            <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-3, #8A93B0)', letterSpacing: '0.5px', textTransform: 'uppercase' as const, display: 'block', marginBottom: '5px' }}>
                                {t('influencer.name')} <span style={{ color: 'var(--red, #ef4444)' }}>*</span>
                            </label>
                            <input value={name} onChange={(e) => setName(e.target.value)} className="input-field w-full" placeholder={t('influencer.namePlaceholder')} />
                        </div>

                        {/* Gender */}
                        <div>
                            <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-3, #8A93B0)', letterSpacing: '0.5px', textTransform: 'uppercase' as const, display: 'block', marginBottom: '5px' }}>
                                {t('influencer.sex')} <span style={{ color: 'var(--red, #ef4444)' }}>*</span>
                            </label>
                            <div style={{ display: 'flex', gap: '8px' }}>
                                {[{ key: 'Male', label: t('influencer.male') }, { key: 'Female', label: t('influencer.female') }].map(g => (
                                    <button key={g.key} type="button" onClick={() => setGender(g.key)} style={{
                                        flex: 1, padding: '8px 16px', borderRadius: 'var(--radius-sm, 8px)', fontSize: '13px', fontWeight: 500, transition: 'all 0.15s',
                                        border: `1px solid ${gender === g.key ? 'var(--blue, #337AFF)' : 'var(--border, rgba(0,0,0,0.08))'}`,
                                        background: gender === g.key ? 'var(--blue, #337AFF)' : 'var(--surface, white)',
                                        color: gender === g.key ? 'white' : 'var(--text-2, #5A6178)',
                                    }}>{g.label}</button>
                                ))}
                            </div>
                        </div>

                        {/* Category */}
                        <div>
                            <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-3, #8A93B0)', letterSpacing: '0.5px', textTransform: 'uppercase' as const, display: 'block', marginBottom: '5px' }}>
                                {t('influencer.category')}
                            </label>
                            <input value={style} onChange={(e) => setStyle(e.target.value)} list="categories-list" className="input-field w-full" placeholder={t('influencer.categoryPlaceholder')} />
                            <datalist id="categories-list">{PRESET_CATEGORIES.map(c => <option key={c} value={c} />)}</datalist>
                        </div>

                        {/* Image URL */}
                        <div>
                            <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-3, #8A93B0)', letterSpacing: '0.5px', textTransform: 'uppercase' as const, display: 'block', marginBottom: '5px' }}>
                                {t('influencer.profileImage')}
                            </label>
                            <input value={imageUrl} onChange={(e) => setImageUrl(e.target.value)} placeholder={t('influencer.pasteUrl')} className="input-field w-full" style={{ fontSize: '12px' }} />
                        </div>

                        {/* ── STEP 2: Generate Identity — only when profile image exists ── */}
                        {imageUrl && (
                            <button
                                onClick={handleGenerateIdentity}
                                disabled={generatingIdentity || generating}
                                id="generate-identity-btn"
                                style={{
                                    width: '100%', padding: '11px 16px', borderRadius: '10px',
                                    border: '1px solid transparent',
                                    background: generatingIdentity
                                        ? 'linear-gradient(135deg, rgba(16, 185, 129, 0.15), rgba(59, 130, 246, 0.15))'
                                        : 'linear-gradient(135deg, rgba(16, 185, 129, 0.10), rgba(59, 130, 246, 0.10))',
                                    color: '#10b981', fontSize: '13px', fontWeight: 600,
                                    cursor: generatingIdentity || generating ? 'default' : 'pointer',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                                    transition: 'all 0.2s', opacity: generatingIdentity ? 0.8 : 1,
                                }}
                                onMouseEnter={(e) => { if (!generatingIdentity && !generating) (e.currentTarget as HTMLButtonElement).style.background = 'linear-gradient(135deg, rgba(16, 185, 129, 0.20), rgba(59, 130, 246, 0.20))'; }}
                                onMouseLeave={(e) => { if (!generatingIdentity && !generating) (e.currentTarget as HTMLButtonElement).style.background = 'linear-gradient(135deg, rgba(16, 185, 129, 0.10), rgba(59, 130, 246, 0.10))'; }}
                            >
                                {generatingIdentity ? (
                                    <><div style={{ width: '14px', height: '14px', border: '2px solid rgba(16,185,129,0.3)', borderTopColor: '#10b981', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> Generating identity...</>
                                ) : (
                                    <>
                                        <svg width="14" height="14" viewBox="40 40 300 300" fill="currentColor" style={{display:'inline',verticalAlign:'-1px'}}><path d="M67.27 185.02L52.28 189.16L67.27 193.29C124.52 209.07 169.24 253.79 185.02 311.04L189.15 326.03L193.29 311.04C209.07 253.79 253.79 209.07 311.04 193.29L326.03 189.16L311.04 185.02C253.79 169.24 209.07 124.52 193.29 67.27L189.15 52.28L185.02 67.27C169.24 124.52 124.52 169.24 67.27 185.02Z"/></svg>
                                        Generate Identity
                                    </>
                                )}
                            </button>
                        )}

                        {/* Description */}
                        <div>
                            <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-3, #8A93B0)', letterSpacing: '0.5px', textTransform: 'uppercase' as const, display: 'block', marginBottom: '5px' }}>
                                {t('influencer.description')}
                            </label>
                            <textarea
                                value={description}
                                onChange={(e) => setDescription(e.target.value)}
                                className="input-field w-full"
                                placeholder={t('influencer.descPlaceholder')}
                                rows={3}
                                style={{ resize: 'none' }}
                            />
                        </div>

                        {/* Voice ID */}
                        <div>
                            <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-3, #8A93B0)', letterSpacing: '0.5px', textTransform: 'uppercase' as const, display: 'block', marginBottom: '5px' }}>
                                {t('influencer.voiceId')}
                            </label>
                            <input value={voiceId} onChange={(e) => setVoiceId(e.target.value)} className="input-field w-full font-mono" placeholder={t('influencer.voicePlaceholder')} style={{ fontSize: '12px' }} />
                        </div>
                    </div>

                    {/* Footer */}
                    <div style={{
                        display: 'flex', justifyContent: 'flex-end', gap: '10px',
                        paddingTop: '16px', borderTop: '1px solid rgba(0,0,0,0.06)', marginTop: '20px',
                    }}>
                        <button onClick={onClose} style={{
                            padding: '9px 20px', borderRadius: '10px',
                            border: '1px solid var(--border, rgba(0,0,0,0.08))',
                            background: 'var(--surface, white)', color: 'var(--text-2, #5A6178)',
                            fontSize: '13px', fontWeight: 600, cursor: 'pointer',
                        }}>Cancel</button>
                        <button
                            onClick={handleSave}
                            disabled={saving || !name.trim()}
                            style={{
                                padding: '9px 24px', borderRadius: '10px', border: 'none',
                                background: saving || !name.trim() ? 'rgba(51,122,255,0.4)' : 'linear-gradient(135deg, #337AFF, #6C5CE7)',
                                color: 'white', fontSize: '13px', fontWeight: 700,
                                cursor: saving || !name.trim() ? 'default' : 'pointer', transition: 'all 0.2s',
                            }}
                        >
                            {saving ? t('common.saving') : (initialData ? t('product.saveChanges') : t('influencer.createInfluencer'))}
                        </button>
                    </div>
                </div>
            </div>

            <style>{`
                @keyframes infModalFadeIn { from { opacity: 0; } to { opacity: 1; } }
                @keyframes infModalScaleIn {
                    from { opacity: 0; transform: translate(-50%, -50%) scale(0.95); }
                    to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
                }
                @keyframes infStepFade {
                    from { opacity: 0; transform: translateY(6px); }
                    to { opacity: 1; transform: translateY(0); }
                }
            `}</style>
        </>
    );
}
