'use client';

import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Product } from '@/lib/types';
import Select from '@/components/ui/Select';
import MediaPreviewModal from '@/components/ui/MediaPreviewModal';
import { apiFetch } from '@/lib/utils';
import { creativeFetch } from '@/lib/creative-os-api';
import { useTranslation } from '@/lib/i18n';
import { MODAL_HEIGHT_SHORT, MODAL_WIDTH_NARROW } from '@/lib/modal-sizing';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';

// Progress steps for product shots generation
const SHOTS_STEPS = [
    'Analyzing product image with GPT-4o Vision…',
    'Generating product sheet prompt…',
    'NanoBanana Pro is rendering 4 views…',
    'Splitting and cropping views…',
    'Uploading product shots…',
];
const SHOTS_ESTIMATED_SECONDS = 90;

interface ProductModalProps {
    isOpen: boolean;
    onClose: () => void;
    product: Product | null;
    onSave: () => void;
    defaultType?: string;
}

export default function ProductModal({ isOpen, onClose, product, onSave, defaultType }: ProductModalProps) {
    const { t } = useTranslation();
    const isEditing = !!product;
    const isDigitalCreate = !isEditing && defaultType === 'digital';

    const [name, setName] = useState('');
    const [type, setType] = useState('physical');
    const [imageUrl, setImageUrl] = useState('');
    const [websiteUrl, setWebsiteUrl] = useState('');
    const [uploading, setUploading] = useState(false);

    // Product shots carousel state
    const [productViews, setProductViews] = useState<string[]>([]);
    const [currentViewIndex, setCurrentViewIndex] = useState(0);
    const [generatingShots, setGeneratingShots] = useState(false);
    const [shotsStep, setShotsStep] = useState(0);
    const [shotsElapsed, setShotsElapsed] = useState(0);
    const shotsStartRef = useRef(0);

    // Clip upload state (digital creation mode only)
    const [clipVideoUrl, setClipVideoUrl] = useState('');
    const [clipName, setClipName] = useState('');
    const [dragActive, setDragActive] = useState(false);
    const clipInputRef = useRef<HTMLInputElement>(null);

    // AI Analysis / Product Description State
    const [analyzing, setAnalyzing] = useState(false);
    const [analysisResult, setAnalysisResult] = useState<any>(null);
    const [previewAssetUrl, setPreviewAssetUrl] = useState<string | null>(null);
    const [descriptionMode, setDescriptionMode] = useState<'ai' | 'manual'>('ai');
    const [manualDescription, setManualDescription] = useState('');

    const fileInputRef = useRef<HTMLInputElement>(null);
    const [mounted, setMounted] = useState(false);

    useEffect(() => { setMounted(true); }, []);

    // Progress timer for product shots generation
    useEffect(() => {
        if (!generatingShots) { setShotsStep(0); setShotsElapsed(0); return; }
        shotsStartRef.current = Date.now();
        const stepInt = setInterval(() => setShotsStep(p => p < SHOTS_STEPS.length - 1 ? p + 1 : p), 12000);
        const timerInt = setInterval(() => setShotsElapsed(Math.floor((Date.now() - shotsStartRef.current) / 1000)), 1000);
        return () => { clearInterval(stepInt); clearInterval(timerInt); };
    }, [generatingShots]);

    // Reset form when opening/changing data
    useEffect(() => {
        if (isOpen) {
            if (product) {
                setName(product.name || '');
                setType(product.type || defaultType || 'physical');
                setImageUrl(product.image_url || '');
                setWebsiteUrl(product.website_url || '');
                setProductViews(product.product_views || []);
                setCurrentViewIndex(0);
                setAnalysisResult(product.visual_description || null);
                // If there's a string description, start in manual mode
                if (typeof product.visual_description === 'string') {
                    setDescriptionMode('manual');
                    setManualDescription(product.visual_description);
                } else {
                    setDescriptionMode(product.visual_description ? 'ai' : 'ai');
                    setManualDescription('');
                }
            } else {
                setName(''); setType(defaultType || 'physical');
                setImageUrl(''); setWebsiteUrl('');
                setProductViews([]); setCurrentViewIndex(0);
                setAnalysisResult(null);
                setClipVideoUrl(''); setClipName('');
                setDescriptionMode('ai'); setManualDescription('');
            }
        }
    }, [isOpen, product, defaultType]);

    if (!isOpen || !mounted) return null;

    // Build carousel: original image first, then shot views, then upload card (virtual last slide)
    const displayImages: string[] = [];
    if (imageUrl) displayImages.push(imageUrl);
    if (productViews.length > 0) displayImages.push(...productViews);
    // Total slides = real images + 1 upload card (only for physical products with at least 1 image)
    const hasUploadCard = !isDigitalCreate && imageUrl;
    const totalSlides = displayImages.length + (hasUploadCard ? 1 : 0);
    const isOnUploadCard = hasUploadCard && currentViewIndex === displayImages.length;
    const hasMultipleSlides = totalSlides > 1;

    const goToPrev = () => setCurrentViewIndex(i => Math.max(0, i - 1));
    const goToNext = () => setCurrentViewIndex(i => Math.min(totalSlides - 1, i + 1));

    const allViewLabels = ['Product Image', 'Hero Front', 'Open View', 'Detail', 'Alt Angle'];
    const getViewLabel = (idx: number) => {
        if (isOnUploadCard && idx === displayImages.length) return 'Add Image';
        if (productViews.length === 0) return 'Product Image';
        return allViewLabels[idx] || `View ${idx + 1}`;
    };

    const isDigitalProduct = type === 'digital' || isDigitalCreate;
    const isLoading = uploading || generatingShots;
    const shotsProgress = Math.min(100, Math.round((shotsElapsed / SHOTS_ESTIMATED_SECONDS) * 100));

    // ── File upload — appends to product views when images already exist ──
    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;
        setUploading(true);
        try {
            const signRes = await apiFetch<{ signed_url: string; public_url: string }>('/api/products/upload', {
                method: 'POST',
                body: JSON.stringify({ file_name: file.name, content_type: file.type }),
            });
            const uploadRes = await fetch(signRes.signed_url, {
                method: 'PUT', headers: { 'Content-Type': file.type }, body: file,
            });
            if (!uploadRes.ok) throw new Error("Upload failed");

            if (!imageUrl) {
                // No image yet — set as the main product image
                setImageUrl(signRes.public_url);
            } else {
                // Already have image(s) — append to product views
                setProductViews(prev => [...prev, signRes.public_url]);
                // Navigate to the newly added image
                setCurrentViewIndex(displayImages.length); // will be the new last real image
            }
        } catch (err) {
            console.error('Upload Error:', err);
            alert('Failed to upload image.');
        } finally {
            setUploading(false);
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    };

    // ── Clip video upload (digital mode) ──
    async function uploadClipVideo(file: File) {
        if (!file.type.startsWith('video/')) { alert('Please select a video file.'); return; }
        if (file.size > 200 * 1024 * 1024) { alert('Video must be under 200 MB.'); return; }
        try {
            setUploading(true);
            const cleanName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_');
            const fileName = `clip_${Date.now()}_${cleanName}`;
            const signedRes = await apiFetch<{ signed_url: string; path: string }>('/assets/signed-url', {
                method: 'POST',
                body: JSON.stringify({ bucket: 'app-clips', file_name: fileName }),
            });
            const uploadRes = await fetch(signedRes.signed_url, {
                method: 'PUT', body: file, headers: { 'Content-Type': file.type },
            });
            if (!uploadRes.ok) throw new Error('Upload failed');
            const publicUrl = `${SUPABASE_URL}/storage/v1/object/public/app-clips/${signedRes.path}`;
            setClipVideoUrl(publicUrl);
            if (!clipName) setClipName(file.name.replace(/\.[^.]+$/, ''));
        } catch (err) {
            console.error('[ProductModal] Clip upload error:', err);
            alert('Failed to upload clip video.');
        } finally {
            setUploading(false);
            if (clipInputRef.current) clipInputRef.current.value = '';
        }
    }

    // ── Generate Product Shots ──
    async function handleGenerateShots() {
        if (generatingShots || !imageUrl) return;
        setGeneratingShots(true);
        try {
            const result = await creativeFetch<{
                product_sheet_url: string;
                views: string[];
            }>('/creative-os/generate/image/generate-product-shots', {
                method: 'POST',
                body: JSON.stringify({ image_url: imageUrl }),
            }, 300_000);
            if (result?.views?.length) {
                setProductViews(result.views);
                setCurrentViewIndex(0);
            }
        } catch (err) {
            console.error('Generate product shots failed:', err);
            alert('Failed to generate product shots. Please try again.');
        } finally {
            setGeneratingShots(false);
        }
    }

    // ── AI Analysis (now works without saving — uses image_url directly) ──
    const handleAnalyze = async () => {
        if (!imageUrl || analyzing) return;
        setAnalyzing(true);
        try {
            if (isDigitalProduct && product?.id) {
                const result = await apiFetch<any>(`/api/products/${product.id}/analyze-digital`, { method: 'POST' });
                setAnalysisResult(result.analysis || result);
            } else {
                // Use the new image_url-based endpoint (no product_id required)
                const result = await apiFetch<any>('/api/products/analyze-image', {
                    method: 'POST',
                    body: JSON.stringify({
                        image_url: imageUrl,
                        product_id: product?.id || undefined, // persist if product exists
                    }),
                });
                setAnalysisResult(result);
            }
        } catch (err: any) {
            console.error(err);
            alert(err.message || 'Failed to analyze product.');
        } finally {
            setAnalyzing(false);
        }
    };

    // ── Submit ──
    const handleSubmit = async () => {
        if (!name.trim()) return;
        try {
            const basePayload: Record<string, unknown> = {
                name, type,
                image_url: imageUrl,
                website_url: isDigitalProduct ? (websiteUrl || undefined) : undefined,
            };
            if (productViews.length > 0) basePayload.product_views = productViews;
            // Pass description: AI result or manual text
            if (descriptionMode === 'manual' && manualDescription.trim()) {
                basePayload.visual_description = manualDescription.trim();
            } else if (analysisResult) {
                basePayload.visual_description = analysisResult;
            }

            if (isDigitalCreate) {
                const newProduct = await apiFetch<{ id: string }>('/api/products', {
                    method: 'POST',
                    body: JSON.stringify({ ...basePayload, type: 'digital', image_url: imageUrl || '' }),
                });
                if (clipVideoUrl && newProduct?.id) {
                    try {
                        await apiFetch('/app-clips', {
                            method: 'POST',
                            body: JSON.stringify({ name: clipName || name, video_url: clipVideoUrl, product_id: newProduct.id }),
                        });
                    } catch (clipErr: any) {
                        alert(`Product created, but clip creation failed: ${clipErr.message}`);
                    }
                }
            } else if (!isEditing) {
                await apiFetch('/api/products', { method: 'POST', body: JSON.stringify(basePayload) });
            } else {
                await apiFetch(`/api/products/${product!.id}`, { method: 'PUT', body: JSON.stringify(basePayload) });
            }
            onSave(); onClose();
            if (isDigitalCreate && clipVideoUrl) setTimeout(() => { onSave(); }, 4000);
        } catch (err) {
            console.error(err);
            alert('Failed to save product.');
        }
    };

    // ── Analysis button state ──
    const analyzeDisabled = isDigitalProduct
        ? (!product?.id || analyzing)
        : (!imageUrl || analyzing);

    return createPortal(
        <>
            {/* Backdrop */}
            <div
                onClick={onClose}
                style={{
                    position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
                    backdropFilter: 'blur(6px)', zIndex: 9999, animation: 'pmFadeIn 0.2s ease',
                }}
            />

            {/* Modal */}
            <div style={{
                position: 'fixed', top: '50%', left: '50%',
                transform: 'translate(-50%, -50%)',
                width: MODAL_WIDTH_NARROW, maxWidth: MODAL_WIDTH_NARROW, height: MODAL_HEIGHT_SHORT, maxHeight: MODAL_HEIGHT_SHORT,
                background: '#FFF', borderRadius: '20px',
                boxShadow: '0 32px 80px rgba(0,0,0,0.25)', zIndex: 10000,
                display: 'flex', overflow: 'hidden',
                animation: 'pmScaleIn 0.25s cubic-bezier(0.4, 0, 0.2, 1)',
            }}>

                {/* ── Left: Image Preview Panel with Carousel ── */}
                <div style={{
                    flex: '0 0 340px', background: '#0D1117',
                    display: 'flex', flexDirection: 'column',
                    overflow: 'hidden', position: 'relative',
                }}>
                    <input type="file" ref={fileInputRef} onChange={handleFileChange} style={{ display: 'none' }} accept="image/*" />
                    <input type="file" ref={clipInputRef} style={{ display: 'none' }} accept="video/*"
                        onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadClipVideo(f); }} />

                    {/* Main image area */}
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
                            {isOnUploadCard ? (
                                /* Upload card — last slide in carousel */
                                <div
                                    onClick={() => fileInputRef.current?.click()}
                                    style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px', cursor: 'pointer' }}
                                >
                                    <div style={{
                                        width: '48px', height: '48px', borderRadius: '50%',
                                        border: '1.5px dashed rgba(255,255,255,0.25)',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    }}>
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="2" strokeLinecap="round">
                                            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                                        </svg>
                                    </div>
                                    <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.45)', fontWeight: 500 }}>
                                        Add another image
                                    </span>
                                    <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.25)' }}>
                                        PNG, JPG up to 10MB
                                    </span>
                                </div>
                            ) : displayImages.length > 0 ? (
                                <img
                                    key={displayImages[currentViewIndex]}
                                    src={displayImages[currentViewIndex]}
                                    alt={getViewLabel(currentViewIndex)}
                                    style={{
                                        width: '100%', height: '100%', objectFit: 'contain', display: 'block',
                                        animation: 'pmStepFade 0.3s ease',
                                    }}
                                    onClick={() => setPreviewAssetUrl(displayImages[currentViewIndex])}
                                />
                            ) : isDigitalCreate ? (
                                /* Digital empty state — upload video */
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}
                                    onClick={(e) => { e.stopPropagation(); clipInputRef.current?.click(); }}
                                >
                                    <div style={{
                                        width: '48px', height: '48px', borderRadius: '50%',
                                        border: '1.5px dashed rgba(255,255,255,0.2)',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    }}>
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="2" strokeLinecap="round">
                                            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                                        </svg>
                                    </div>
                                    <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)', fontWeight: 500 }}>
                                        Click to upload video
                                    </span>
                                    <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)' }}>
                                        MP4, MOV up to 200MB
                                    </span>
                                </div>
                            ) : (
                                /* Physical empty state — upload image */
                                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '10px' }}>
                                    <div style={{
                                        width: '48px', height: '48px', borderRadius: '50%',
                                        border: '1.5px dashed rgba(255,255,255,0.2)',
                                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                                    }}>
                                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="2" strokeLinecap="round">
                                            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
                                        </svg>
                                    </div>
                                    <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.35)', fontWeight: 500 }}>
                                        Click to upload image
                                    </span>
                                    <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.2)' }}>
                                        PNG, JPG up to 10MB
                                    </span>
                                </div>
                            )}

                            {/* Remove button — only on real image slides */}
                            {displayImages.length > 0 && !isLoading && !isOnUploadCard && (
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        if (currentViewIndex === 0) {
                                            // Removing main image — clear everything
                                            setImageUrl(''); setProductViews([]); setCurrentViewIndex(0);
                                        } else {
                                            // Removing a product view
                                            const viewIdx = currentViewIndex - 1; // offset by 1 (main image is at 0)
                                            setProductViews(prev => prev.filter((_, i) => i !== viewIdx));
                                            setCurrentViewIndex(i => Math.max(0, i - 1));
                                        }
                                    }}
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
                            {hasMultipleSlides && !isLoading && (
                                <>
                                    {currentViewIndex > 0 && (
                                        <button onClick={goToPrev} style={{
                                            position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)',
                                            width: '32px', height: '32px', borderRadius: '50%',
                                            background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
                                            border: 'none', cursor: 'pointer', display: 'flex',
                                            alignItems: 'center', justifyContent: 'center',
                                        }}>
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round"><path d="M15 18l-6-6 6-6"/></svg>
                                        </button>
                                    )}
                                    {currentViewIndex < totalSlides - 1 && (
                                        <button onClick={goToNext} style={{
                                            position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)',
                                            width: '32px', height: '32px', borderRadius: '50%',
                                            background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
                                            border: 'none', cursor: 'pointer', display: 'flex',
                                            alignItems: 'center', justifyContent: 'center',
                                        }}>
                                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round"><path d="M9 18l6-6-6-6"/></svg>
                                        </button>
                                    )}
                                </>
                            )}

                            {/* Dots + label */}
                            {hasMultipleSlides && !isLoading && (
                                <div style={{ position: 'absolute', bottom: '14px', left: 0, right: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                                    <div style={{ display: 'flex', gap: '5px', alignItems: 'center' }}>
                                        {Array.from({ length: totalSlides }).map((_, i) => (
                                            <button key={i} onClick={() => setCurrentViewIndex(i)} style={{
                                                width: i === currentViewIndex ? '20px' : '6px',
                                                height: '6px', borderRadius: '3px', border: 'none',
                                                background: i === currentViewIndex
                                                    ? (i === displayImages.length ? 'rgba(255,255,255,0.6)' : '#a78bfa')
                                                    : (i === displayImages.length ? 'rgba(255,255,255,0.15)' : 'rgba(255,255,255,0.3)'),
                                                cursor: 'pointer', padding: 0, transition: 'all 0.2s',
                                            }} />
                                        ))}
                                    </div>
                                    <span style={{ fontSize: '10px', fontWeight: 600, color: 'rgba(255,255,255,0.5)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                                        {getViewLabel(currentViewIndex)}
                                    </span>
                                </div>
                            )}

                            {/* Loading overlay — generating shots */}
                            {generatingShots && (
                                <div style={{
                                    position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.7)',
                                    backdropFilter: 'blur(8px)', display: 'flex', flexDirection: 'column',
                                    alignItems: 'center', justifyContent: 'center', gap: '14px', borderRadius: '14px',
                                }}>
                                    <svg style={{ animation: 'spin 1s linear infinite', height: '28px', width: '28px' }} fill="none" viewBox="0 0 24 24">
                                        <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="white" strokeWidth="4" />
                                        <path style={{ opacity: 0.75 }} fill="white" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                    </svg>
                                    <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.9)', fontWeight: 500, textAlign: 'center', maxWidth: '200px' }}>
                                        {SHOTS_STEPS[shotsStep]}
                                    </span>
                                    <div style={{ width: '140px', height: '3px', borderRadius: '2px', background: 'rgba(255,255,255,0.15)', overflow: 'hidden' }}>
                                        <div style={{
                                            height: '100%', borderRadius: '2px',
                                            background: 'linear-gradient(90deg, #8b5cf6, #a78bfa)',
                                            width: `${shotsProgress}%`, transition: 'width 1s linear',
                                        }} />
                                    </div>
                                    <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.4)' }}>
                                        {shotsElapsed}s / ~{SHOTS_ESTIMATED_SECONDS}s
                                    </span>
                                </div>
                            )}

                            {/* Uploading overlay */}
                            {uploading && (
                                <div style={{
                                    position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.6)',
                                    backdropFilter: 'blur(4px)', display: 'flex', flexDirection: 'column',
                                    alignItems: 'center', justifyContent: 'center', gap: '12px', borderRadius: '14px',
                                }}>
                                    <div style={{ width: '24px', height: '24px', border: '2px solid rgba(255,255,255,0.2)', borderTopColor: '#a78bfa', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                                    <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.8)', fontWeight: 500 }}>Uploading…</span>
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* ── Right: Config Panel ── */}
                <div style={{
                    flex: '1 1 auto',
                    display: 'flex', flexDirection: 'column',
                    overflow: 'hidden', position: 'relative',
                }}>
                    {/* Scrollable content area */}
                    <div style={{
                        flex: 1, overflowY: 'auto',
                        padding: '24px 24px 0',
                        display: 'flex', flexDirection: 'column',
                    }}>
                        {/* Header */}
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px', flexShrink: 0 }}>
                            <h3 style={{ fontSize: '17px', fontWeight: 700, color: 'var(--text-1, #0D1B3E)', margin: 0, letterSpacing: '-0.2px' }}>
                                {isEditing ? t('product.title') : isDigitalCreate ? t('product.newDigital') : t('product.addNew')}
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

                        {/* Form Fields */}
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', flex: 1 }}>

                        {/* Name */}
                        <div>
                            <label style={{ fontSize: '11px', fontWeight: 700, color: '#8A93B0', letterSpacing: '0.5px', textTransform: 'uppercase' as const, display: 'block', marginBottom: '5px' }}>
                                {t('product.productName')} <span style={{ color: '#ef4444' }}>*</span>
                            </label>
                            <input value={name} onChange={(e) => setName(e.target.value)}
                                placeholder={isDigitalCreate ? t('product.placeholderDigital') : t('product.placeholderPhysical')}
                                className="input-field w-full" />
                        </div>

                        {/* Asset Type — hidden for digital create */}
                        {!isDigitalCreate && (
                            <div>
                                <label style={{ fontSize: '11px', fontWeight: 700, color: '#8A93B0', letterSpacing: '0.5px', textTransform: 'uppercase' as const, display: 'block', marginBottom: '5px' }}>
                                    {t('product.assetType')}
                                </label>
                                <Select
                                    value={type}
                                    onChange={setType}
                                    options={[
                                        { value: 'physical', label: t('product.physicalProduct') },
                                        { value: 'digital', label: t('product.digitalProduct') }
                                    ]}
                                    className="input-field w-full"
                                />
                            </div>
                        )}

                        {/* Website URL — only for digital products */}
                        {isDigitalProduct && (
                            <div>
                                <label style={{ fontSize: '11px', fontWeight: 700, color: '#8A93B0', letterSpacing: '0.5px', textTransform: 'uppercase' as const, display: 'block', marginBottom: '5px' }}>
                                    {t('product.websiteUrl')}
                                </label>
                                <p style={{ fontSize: '11px', color: '#94a3b8', margin: '0 0 6px' }}>
                                    AI will analyse the website to understand your product and brand
                                </p>
                                <input value={websiteUrl} onChange={(e) => setWebsiteUrl(e.target.value)}
                                    placeholder="https://yourproduct.com" className="input-field w-full" type="url" />
                            </div>
                        )}

                        {/* ── Generate Shots button — only for physical products with image ── */}
                        {imageUrl && !isDigitalProduct && (
                            <button
                                onClick={handleGenerateShots}
                                disabled={generatingShots}
                                style={{
                                    width: '100%', padding: '11px 16px', borderRadius: '10px',
                                    border: '1px solid transparent',
                                    background: generatingShots
                                        ? 'linear-gradient(135deg, rgba(139, 92, 246, 0.15), rgba(99, 102, 241, 0.15))'
                                        : 'linear-gradient(135deg, rgba(139, 92, 246, 0.10), rgba(99, 102, 241, 0.10))',
                                    color: '#8b5cf6', fontSize: '13px', fontWeight: 600,
                                    cursor: generatingShots ? 'default' : 'pointer',
                                    display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                                    transition: 'all 0.2s', opacity: generatingShots ? 0.8 : 1,
                                }}
                                onMouseEnter={(e) => { if (!generatingShots) (e.currentTarget as HTMLButtonElement).style.background = 'linear-gradient(135deg, rgba(139, 92, 246, 0.20), rgba(99, 102, 241, 0.20))'; }}
                                onMouseLeave={(e) => { if (!generatingShots) (e.currentTarget as HTMLButtonElement).style.background = 'linear-gradient(135deg, rgba(139, 92, 246, 0.10), rgba(99, 102, 241, 0.10))'; }}
                            >
                                {generatingShots ? (
                                    <><div style={{ width: '14px', height: '14px', border: '2px solid rgba(139,92,246,0.3)', borderTopColor: '#8b5cf6', borderRadius: '50%', animation: 'spin 1s linear infinite' }} /> Generating shots…</>
                                ) : (
                                    <>
                                        <svg width="14" height="14" viewBox="40 40 300 300" fill="currentColor" style={{display:'inline',verticalAlign:'-1px'}}><path d="M67.27 185.02L52.28 189.16L67.27 193.29C124.52 209.07 169.24 253.79 185.02 311.04L189.15 326.03L193.29 311.04C209.07 253.79 253.79 209.07 311.04 193.29L326.03 189.16L311.04 185.02C253.79 169.24 209.07 124.52 193.29 67.27L189.15 52.28L185.02 67.27C169.24 124.52 124.52 169.24 67.27 185.02Z"/></svg>
                                        Generate Shots
                                    </>
                                )}
                            </button>
                        )}

                        {/* ── Product Description section — fills remaining space ── */}
                        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minHeight: 0 }}>
                            <label style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.5px', textTransform: 'uppercase' as const, display: 'block', marginBottom: '4px', flexShrink: 0,
                                color: '#8A93B0',
                            }}>
                                Product Description
                            </label>
                            <p style={{ fontSize: '11px', color: '#94a3b8', margin: '0 0 8px', flexShrink: 0 }}>
                                Describe your product for better AI generations, or generate a description automatically.
                            </p>

                            {/* Toggle: AI / Manual */}
                            <div style={{
                                display: 'flex', gap: '4px', marginBottom: '10px', flexShrink: 0,
                                padding: '3px', borderRadius: '10px', background: 'rgba(0,0,0,0.04)',
                            }}>
                                <button
                                    onClick={() => setDescriptionMode('ai')}
                                    style={{
                                        flex: 1, padding: '8px 0', border: 'none', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
                                        borderRadius: '8px',
                                        background: descriptionMode === 'ai' ? 'white' : 'transparent',
                                        color: descriptionMode === 'ai' ? '#337AFF' : '#8A93B0',
                                        boxShadow: descriptionMode === 'ai' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                                        transition: 'all 0.15s',
                                    }}
                                >
                                    Generate with AI
                                </button>
                                <button
                                    onClick={() => setDescriptionMode('manual')}
                                    style={{
                                        flex: 1, padding: '8px 0', border: 'none', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
                                        borderRadius: '8px',
                                        background: descriptionMode === 'manual' ? 'white' : 'transparent',
                                        color: descriptionMode === 'manual' ? '#337AFF' : '#8A93B0',
                                        boxShadow: descriptionMode === 'manual' ? '0 1px 3px rgba(0,0,0,0.08)' : 'none',
                                        transition: 'all 0.15s',
                                    }}
                                >
                                    Write manually
                                </button>
                            </div>

                            {descriptionMode === 'manual' ? (
                                /* ── Manual description textarea ── */
                                <textarea
                                    value={manualDescription}
                                    onChange={e => setManualDescription(e.target.value)}
                                    placeholder="Describe your product: what it is, its key features, target audience, brand positioning..."
                                    style={{
                                        flex: 1, minHeight: '100px', width: '100%', padding: '12px',
                                        borderRadius: '10px', border: '1px solid #e2e8f0', background: '#f8fafc',
                                        fontSize: '13px', color: '#0D1B3E', lineHeight: 1.6, resize: 'none',
                                        outline: 'none', fontFamily: 'inherit', boxSizing: 'border-box',
                                        transition: 'border-color 0.15s',
                                    }}
                                    onFocus={e => (e.currentTarget.style.borderColor = '#337AFF')}
                                    onBlur={e => (e.currentTarget.style.borderColor = '#e2e8f0')}
                                />
                            ) : (
                                /* ── AI-generated description ── */
                                <>
                                    <div style={{
                                        background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: '10px',
                                        padding: '12px', flex: 1, minHeight: '80px', overflowY: 'auto',
                                        marginBottom: '10px',
                                    }}>
                                        {!analysisResult ? (
                                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: '#94a3b8', textAlign: 'center' }}>
                                                <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ marginBottom: '8px', opacity: 0.5 }}><path d="M2 12h4l3-9 5 18 3-9h5" /></svg>
                                                <p style={{ fontSize: '12px', fontWeight: 500 }}>No description generated yet.</p>
                                                <p style={{ fontSize: '11px', marginTop: '2px', opacity: 0.7 }}>
                                                    {isDigitalProduct
                                                        ? 'Analyse your website to auto-generate a product description.'
                                                        : 'Analyse your product image to auto-generate a description.'}
                                                </p>
                                            </div>
                                        ) : (
                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                                                {typeof analysisResult === 'object' ? (
                                                    Object.keys(analysisResult).map((key) => {
                                                        const isColorScheme = key === 'color_scheme' && Array.isArray(analysisResult[key]);
                                                        return (
                                                            <div key={key} style={{ background: '#fff', padding: '8px 10px', borderRadius: '6px', border: '1px solid #f1f5f9' }}>
                                                                <span style={{ display: 'block', fontSize: '9px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '3px' }}>
                                                                    {key.replace(/_/g, ' ')}
                                                                </span>
                                                                {isColorScheme ? (
                                                                    <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap', marginTop: '4px' }}>
                                                                        {analysisResult[key].map((color: any, idx: number) => (
                                                                            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                                                                <div title={color.hex} style={{ width: '16px', height: '16px', borderRadius: '3px', backgroundColor: color.hex, border: '1px solid #e2e8f0' }} />
                                                                                <span style={{ fontSize: '11px', color: '#1e293b' }}>{color.name}</span>
                                                                            </div>
                                                                        ))}
                                                                    </div>
                                                                ) : (
                                                                    <div style={{ fontSize: '12px', color: '#1e293b', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
                                                                        {typeof analysisResult[key] === 'object'
                                                                            ? JSON.stringify(analysisResult[key], null, 2)
                                                                            : String(analysisResult[key])}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        );
                                                    })
                                                ) : (
                                                    <div style={{ fontSize: '12px', whiteSpace: 'pre-wrap', color: '#1e293b' }}>{String(analysisResult)}</div>
                                                )}
                                            </div>
                                        )}
                                    </div>

                                    {/* Analyze button */}
                                    <button
                                        onClick={handleAnalyze}
                                        disabled={analyzeDisabled}
                                        style={{
                                            width: '100%', padding: '10px', borderRadius: '10px', fontWeight: 600, fontSize: '13px',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px',
                                            transition: 'all 0.2s', border: 'none', cursor: analyzeDisabled ? 'not-allowed' : 'pointer',
                                            background: analyzeDisabled
                                                ? '#f1f5f9'
                                                : 'linear-gradient(to right, #2563eb, #4f46e5)',
                                            color: analyzeDisabled ? '#94a3b8' : '#fff',
                                            boxShadow: analyzeDisabled ? 'none' : '0 4px 14px rgba(37, 99, 235, 0.3)',
                                            flexShrink: 0,
                                        }}
                                    >
                                        {analyzing ? (
                                            <>
                                                <svg style={{ animation: 'spin 1s linear infinite', height: '16px', width: '16px' }} fill="none" viewBox="0 0 24 24">
                                                    <circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                                    <path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                                </svg>
                                                {isDigitalProduct ? 'Analysing website…' : 'Analysing product image…'}
                                            </>
                                        ) : (
                                            <>
                                                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                                    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><circle cx="12" cy="12" r="4" />
                                                </svg>
                                                {analysisResult
                                                    ? (isDigitalProduct ? 'Re-analyse Website' : 'Re-analyse Product Image')
                                                    : (isDigitalProduct ? 'Analyse Website with AI' : 'Analyse Product Image with AI')}
                                            </>
                                        )}
                                    </button>
                                </>
                            )}
                        </div>
                    </div>
                    </div>{/* end scrollable content */}

                    {/* Footer — always pinned at bottom */}
                    <div style={{
                        display: 'flex', justifyContent: 'flex-end', gap: '10px',
                        padding: '14px 24px', borderTop: '1px solid rgba(0,0,0,0.06)',
                        flexShrink: 0, background: '#fff',
                    }}>
                        <button onClick={onClose} style={{
                            padding: '9px 20px', borderRadius: '10px',
                            border: '1px solid rgba(0,0,0,0.08)',
                            background: 'white', color: '#5A6178',
                            fontSize: '13px', fontWeight: 600, cursor: 'pointer',
                        }}>{t('common.cancel')}</button>
                        <button
                            onClick={handleSubmit}
                            disabled={!name.trim()}
                            style={{
                                padding: '9px 24px', borderRadius: '10px', border: 'none',
                                background: !name.trim() ? 'rgba(51,122,255,0.4)' : 'linear-gradient(135deg, #337AFF, #6C5CE7)',
                                color: 'white', fontSize: '13px', fontWeight: 700,
                                cursor: !name.trim() ? 'default' : 'pointer', transition: 'all 0.2s',
                            }}
                        >
                            {isEditing ? t('product.saveChanges') : isDigitalCreate ? t('product.createProduct') : t('product.saveProduct')}
                        </button>
                    </div>
                </div>
            </div>

            <MediaPreviewModal
                isOpen={!!previewAssetUrl}
                onClose={() => setPreviewAssetUrl(null)}
                src={previewAssetUrl || ''}
                type="image"
            />

            <style>{`
                @keyframes pmFadeIn { from { opacity: 0; } to { opacity: 1; } }
                @keyframes pmScaleIn {
                    from { opacity: 0; transform: translate(-50%, -50%) scale(0.95); }
                    to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
                }
                @keyframes pmStepFade {
                    from { opacity: 0; transform: scale(0.98); }
                    to { opacity: 1; transform: scale(1); }
                }
                @keyframes spin {
                    from { transform: rotate(0deg); }
                    to { transform: rotate(360deg); }
                }
            `}</style>
        </>,
        document.body
    );
}
