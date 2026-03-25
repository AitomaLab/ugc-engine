import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Product } from '@/lib/types';
import Select from '@/components/ui/Select';
import MediaPreviewModal from '@/components/ui/MediaPreviewModal';
import { apiFetch } from '@/lib/utils';
import './ProductModal.css';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';

interface ProductModalProps {
    isOpen: boolean;
    onClose: () => void;
    product: Product | null;
    onSave: () => void;
    defaultType?: string;
}

export default function ProductModal({ isOpen, onClose, product, onSave, defaultType }: ProductModalProps) {
    const isEditing = !!product;
    // Digital creation mode: opened from Digital tab with no existing product
    const isDigitalCreate = !isEditing && defaultType === 'digital';

    const [name, setName] = useState(product?.name || '');
    const [type, setType] = useState(product?.type || defaultType || 'physical');
    const [imageUrl, setImageUrl] = useState(product?.image_url || '');
    const [websiteUrl, setWebsiteUrl] = useState(product?.website_url || '');
    const [uploading, setUploading] = useState(false);

    // Clip upload state (digital creation mode only)
    const [clipVideoUrl, setClipVideoUrl] = useState('');
    const [clipName, setClipName] = useState('');
    const [dragActive, setDragActive] = useState(false);
    const clipInputRef = useRef<HTMLInputElement>(null);

    // AI Analysis State
    const [analyzing, setAnalyzing] = useState(false);
    const [analysisResult, setAnalysisResult] = useState<any>(product?.visual_description || null);
    const [previewAssetUrl, setPreviewAssetUrl] = useState<string | null>(null);

    const fileInputRef = useRef<HTMLInputElement>(null);
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
        setMounted(true);
    }, []);

    // Initial load sync
    if (!isOpen || !mounted) return null;

    const handleUploadClick = () => {
        fileInputRef.current?.click();
    };

    const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setUploading(true);
        try {
            // Get Signed URL
            const signRes = await apiFetch<{ signed_url: string; public_url: string }>('/api/products/upload', {
                method: 'POST',
                body: JSON.stringify({ file_name: file.name, content_type: file.type }),
            });

            // Upload to Supabase
            const uploadRes = await fetch(signRes.signed_url, {
                method: 'PUT',
                headers: { 'Content-Type': file.type },
                body: file,
            });

            if (!uploadRes.ok) throw new Error("Upload failed");

            setImageUrl(signRes.public_url);
        } catch (err) {
            console.error('Upload Error:', err);
            alert('Failed to upload image. Check console for details.');
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
            console.log('[ProductModal] Starting clip upload:', file.name, file.size);
            const cleanName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_');
            const fileName = `clip_${Date.now()}_${cleanName}`;
            const signedRes = await apiFetch<{ signed_url: string; path: string }>('/assets/signed-url', {
                method: 'POST',
                body: JSON.stringify({ bucket: 'app-clips', file_name: fileName }),
            });
            console.log('[ProductModal] Signed URL response:', signedRes);
            const uploadRes = await fetch(signedRes.signed_url, {
                method: 'PUT',
                body: file,
                headers: { 'Content-Type': file.type },
            });
            if (!uploadRes.ok) throw new Error('Upload failed');
            const publicUrl = `${SUPABASE_URL}/storage/v1/object/public/app-clips/${signedRes.path}`;
            console.log('[ProductModal] Clip uploaded successfully, URL:', publicUrl);
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

    function handleClipFileChange(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0];
        if (file) uploadClipVideo(file);
    }

    function handleClipDrop(e: React.DragEvent) {
        e.preventDefault();
        setDragActive(false);
        const file = e.dataTransfer.files?.[0];
        if (file) uploadClipVideo(file);
    }

    // ── AI Analysis ──
    const handleAnalyze = async () => {
        if (!product?.id) {
            alert("Please save the product first before analyzing.");
            return;
        }

        setAnalyzing(true);
        try {
            if (product.type === 'digital' || type === 'digital') {
                // Digital product: scrape website URL
                const result = await apiFetch<any>(`/api/products/${product.id}/analyze-digital`, {
                    method: 'POST',
                });
                setAnalysisResult(result.analysis || result);
            } else {
                // Physical product: image vision analysis
                const result = await apiFetch<any>('/api/products/analyze', {
                    method: 'POST',
                    body: JSON.stringify({ product_id: product.id }),
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
    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        try {
            if (isDigitalCreate) {
                // Digital creation: create product → create linked clip
                console.log('[ProductModal] Creating digital product:', { name, websiteUrl, clipVideoUrl, clipName });
                const newProduct = await apiFetch<{ id: string }>('/api/products', {
                    method: 'POST',
                    body: JSON.stringify({
                        name,
                        type: 'digital',
                        image_url: imageUrl || '',
                        website_url: websiteUrl || undefined,
                    }),
                });
                console.log('[ProductModal] Product created:', newProduct);

                // Create linked clip if a video was uploaded
                if (clipVideoUrl) {
                    const productId = newProduct?.id;
                    console.log('[ProductModal] Creating clip:', { clipName, clipVideoUrl, productId });
                    try {
                        await apiFetch('/app-clips', {
                            method: 'POST',
                            body: JSON.stringify({
                                name: clipName || name,
                                video_url: clipVideoUrl,
                                product_id: productId,
                            }),
                        });
                        console.log('[ProductModal] Clip created successfully');
                    } catch (clipErr: any) {
                        console.error('[ProductModal] Clip creation failed:', clipErr);
                        alert(`Product created, but clip creation failed: ${clipErr.message}`);
                    }
                } else {
                    console.log('[ProductModal] No clipVideoUrl - skipping clip creation');
                }
            } else if (!isEditing) {
                // Regular (physical) creation
                await apiFetch('/api/products', {
                    method: 'POST',
                    body: JSON.stringify({
                        name,
                        type,
                        image_url: imageUrl,
                        website_url: websiteUrl || undefined,
                    }),
                });
            } else {
                // Update existing
                await apiFetch(`/api/products/${product!.id}`, {
                    method: 'PUT',
                    body: JSON.stringify({
                        name,
                        type,
                        image_url: imageUrl,
                        website_url: websiteUrl || undefined,
                    }),
                });
            }
            onSave();
            onClose();
            // For digital products with clips: the first-frame extraction runs
            // in the background and takes a few seconds. Schedule a second
            // refresh so the preview image appears automatically.
            if (isDigitalCreate && clipVideoUrl) {
                setTimeout(() => { onSave(); }, 4000);
            }
        } catch (err) {
            console.error(err);
            alert('Failed to save product.');
        }
    };

    // ── Determine right panel labels based on product type ──
    const isDigitalProduct = type === 'digital' || isDigitalCreate;
    const aiTitle = isDigitalProduct ? 'AI Website Analysis' : 'AI Vision Analysis';
    const aiDesc = isDigitalProduct
        ? 'Scrape and analyze your digital product\'s website to extract features, positioning, and marketing copy.'
        : 'Extract visual properties, brand colors, and aesthetic positioning from your product image using GPT-4o.';
    const aiBtnLabel = isDigitalProduct ? 'Analyze Website with AI' : 'Analyze Image with AI';
    const aiDisabled = isDigitalProduct
        ? (!isEditing || analyzing)
        : (!imageUrl || analyzing || !isEditing);

    return createPortal(
        <div className="pm-overlay">
            <div className="pm-container">

                {/* Header */}
                <div className="pm-header">
                    <h2>{isEditing ? 'Asset Settings & Analysis' : isDigitalCreate ? 'New Digital Product' : 'Add New Product'}</h2>
                    <button onClick={onClose} className="pm-close-btn" title="Close">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6L6 18M6 6l12 12" /></svg>
                    </button>
                </div>

                {/* Body */}
                <div className="pm-body custom-scrollbar">
                    <form id="product-form" onSubmit={handleSubmit} className="pm-grid">

                        {/* Left Col: Core Details & Image/Clip */}
                        <div>
                            <div className="pm-form-group">
                                <label className="pm-label">Product Name</label>
                                <input
                                    required
                                    value={name}
                                    onChange={e => setName(e.target.value)}
                                    placeholder={isDigitalCreate ? "Ex: My App Pro" : "Ex: Moisturizing Conditioner"}
                                    className="pm-input"
                                />
                            </div>

                            {/* Asset Type — hidden in digital creation mode */}
                            {!isDigitalCreate && (
                                <div className="pm-form-group">
                                    <label className="pm-label">Asset Type</label>
                                    <Select
                                        value={type}
                                        onChange={setType}
                                        options={[
                                            { value: 'physical', label: 'Physical Product' },
                                            { value: 'digital', label: 'Digital Product / App' }
                                        ]}
                                        className="pm-input"
                                    />
                                </div>
                            )}

                            <div className="pm-form-group">
                                <label className="pm-label">Website URL</label>
                                <input
                                    value={websiteUrl}
                                    onChange={e => setWebsiteUrl(e.target.value)}
                                    placeholder="https://yourproduct.com"
                                    className="pm-input"
                                    type="url"
                                />
                            </div>

                            {/* ── Digital creation: App Clip Upload ── */}
                            {isDigitalCreate ? (
                                <div className="pm-form-group">
                                    <label className="pm-label">
                                        App Clip
                                        <span style={{ fontWeight: 400, color: 'var(--text-3)', marginLeft: '6px' }}>(first frame → preview image)</span>
                                    </label>
                                    <div className="pm-image-upload">
                                        <input type="file" ref={clipInputRef} style={{ display: 'none' }} accept="video/*" onChange={handleClipFileChange} />

                                        {clipVideoUrl ? (
                                            <div style={{ position: 'relative', borderRadius: '10px', overflow: 'hidden', aspectRatio: '16/9', background: '#000' }}>
                                                <video src={clipVideoUrl} style={{ width: '100%', height: '100%', objectFit: 'contain' }} controls />
                                                <button type="button" onClick={() => { setClipVideoUrl(''); setClipName(''); }}
                                                    style={{ position: 'absolute', top: '8px', right: '8px', width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(0,0,0,0.6)', color: 'white', border: 'none', cursor: 'pointer', fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                                    &times;
                                                </button>
                                            </div>
                                        ) : (
                                            <div
                                                onClick={() => clipInputRef.current?.click()}
                                                onDragOver={e => { e.preventDefault(); setDragActive(true); }}
                                                onDragLeave={() => setDragActive(false)}
                                                onDrop={handleClipDrop}
                                                style={{
                                                    border: `2px dashed ${dragActive ? 'var(--blue)' : '#e2e8f0'}`,
                                                    borderRadius: '10px', padding: '32px 20px', textAlign: 'center', cursor: 'pointer',
                                                    background: dragActive ? 'rgba(51,122,255,0.04)' : '#f8fafc',
                                                    transition: 'all 0.15s',
                                                }}
                                            >
                                                {uploading ? (
                                                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                                                        <div style={{ width: '24px', height: '24px', border: '2px solid #e2e8f0', borderTopColor: 'var(--blue)', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                                                        <span style={{ fontSize: '12px', color: '#64748b' }}>Uploading clip...</span>
                                                    </div>
                                                ) : (
                                                    <>
                                                        <div style={{ width: 48, height: 48, borderRadius: '50%', backgroundColor: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#3b82f6', margin: '0 auto 12px auto' }}>
                                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" /></svg>
                                                        </div>
                                                        <p style={{ fontSize: '14px', fontWeight: 700, color: '#334155' }}>Drop a video clip here or <span style={{ color: '#3b82f6' }}>browse</span></p>
                                                        <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>MP4, MOV, WebM — max 200 MB</p>
                                                        <p style={{ fontSize: '11px', color: '#94a3b8', marginTop: '6px' }}>The first frame will be used as the product preview image</p>
                                                    </>
                                                )}
                                            </div>
                                        )}
                                        <button
                                            type="button"
                                            onClick={() => clipInputRef.current?.click()}
                                            disabled={uploading}
                                            className="pm-upload-btn"
                                        >
                                            {clipVideoUrl ? 'Replace Clip' : 'Browse Videos'}
                                        </button>
                                    </div>
                                </div>
                            ) : (
                                /* ── Physical / edit mode: Image Upload ── */
                                <div className="pm-form-group">
                                    <label className="pm-label">
                                        Preview Image{type === 'digital' && <span style={{ fontWeight: 400, color: 'var(--text-3)', marginLeft: '6px' }}>(optional)</span>}
                                    </label>
                                    <div className="pm-image-upload">
                                        <input type="file" ref={fileInputRef} className="hidden" style={{ display: 'none' }} accept="image/*" onChange={handleFileChange} />

                                        {imageUrl ? (
                                            <div
                                                className="pm-preview"
                                                onClick={() => setPreviewAssetUrl(imageUrl)}
                                                style={{ cursor: 'zoom-in' }}
                                            >
                                                <img src={imageUrl} alt="Preview" />
                                                {uploading && (
                                                    <div className="pm-uploading-overlay">
                                                        <span>Uploading...</span>
                                                    </div>
                                                )}
                                            </div>
                                        ) : (
                                            <div style={{ padding: '32px 0' }}>
                                                {uploading ? (
                                                    <span style={{ color: 'var(--blue)', fontWeight: 700 }}>Uploading...</span>
                                                ) : (
                                                    <>
                                                        <div style={{ width: 48, height: 48, borderRadius: '50%', backgroundColor: '#eff6ff', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#3b82f6', margin: '0 auto 12px auto' }}>
                                                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4M17 8l-5-5-5 5M12 3v12" /></svg>
                                                        </div>
                                                        <p style={{ fontSize: '14px', fontWeight: 700, color: '#334155' }}>Click to upload image</p>
                                                        <p style={{ fontSize: '12px', color: '#94a3b8', marginTop: '4px' }}>PNG, JPG up to 10MB</p>
                                                    </>
                                                )}
                                            </div>
                                        )}
                                        <button
                                            type="button"
                                            onClick={handleUploadClick}
                                            disabled={uploading}
                                            className="pm-upload-btn"
                                        >
                                            {imageUrl ? 'Replace Image' : 'Browse Files'}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Right Col: AI Analysis */}
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <div>
                                <label className="pm-label pm-ai-gradient-text">{aiTitle}</label>
                                <p className="pm-ai-desc">{aiDesc}</p>
                            </div>

                            {/* Analysis Container */}
                            <div className="pm-analysis-container">
                                {!analysisResult ? (
                                    <div className="pm-analysis-empty">
                                        <div className="pm-analysis-empty-icon">
                                            {isDigitalProduct ? (
                                                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" /></svg>
                                            ) : (
                                                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 12h4l3-9 5 18 3-9h5" /></svg>
                                            )}
                                        </div>
                                        <p style={{ fontSize: '14px', fontWeight: 500 }}>No analysis data yet.</p>
                                        <p style={{ fontSize: '12px', marginTop: '4px' }}>
                                            {isDigitalProduct
                                                ? 'Save the product first, then run the AI analyzer to scrape website data.'
                                                : 'Run the AI analyzer to extract product metadata.'}
                                        </p>
                                    </div>
                                ) : (
                                    <div className="pm-analysis-content">
                                        {typeof analysisResult === 'object' ? (
                                            Object.keys(analysisResult).map((key) => {
                                                const isColorScheme = key === 'color_scheme' && Array.isArray(analysisResult[key]);
                                                return (
                                                    <div key={`k_${key}`} className="pm-analysis-item">
                                                        <span style={{ display: 'block', fontSize: '10px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '4px' }}>
                                                            {key.replace(/_/g, ' ')}
                                                        </span>
                                                        {isColorScheme ? (
                                                            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '8px' }}>
                                                                {analysisResult[key].map((color: any, idx: number) => (
                                                                    <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                                                        <div title={color.hex} style={{ width: '24px', height: '24px', borderRadius: '4px', backgroundColor: color.hex, border: '1px solid #e2e8f0', boxShadow: '0 1px 2px rgba(0,0,0,0.05)' }} />
                                                                        <span style={{ fontSize: '13px', color: '#1e293b' }}>
                                                                            <strong style={{ fontWeight: 600 }}>{color.name}</strong> <span style={{ color: '#64748b', fontSize: '12px' }}>{color.hex}</span>
                                                                        </span>
                                                                    </div>
                                                                ))}
                                                            </div>
                                                        ) : (
                                                            <div className="pm-analysis-scrollable" style={{ color: '#1e293b', wordBreak: 'break-word', whiteSpace: 'pre-wrap' }}>
                                                                {typeof analysisResult[key] === 'object'
                                                                    ? JSON.stringify(analysisResult[key], null, 2)
                                                                    : String(analysisResult[key])}
                                                            </div>
                                                        )}
                                                    </div>
                                                );
                                            })
                                        ) : (
                                            <div className="pm-analysis-item pm-analysis-scrollable" style={{ whiteSpace: 'pre-wrap' }}>
                                                {String(analysisResult)}
                                            </div>
                                        )}
                                    </div>
                                )}
                            </div>

                            {/* AI Action Button */}
                            <button
                                type="button"
                                onClick={handleAnalyze}
                                disabled={aiDisabled}
                                className={`pm-ai-btn ${aiDisabled ? 'disabled' : 'active'}`}
                            >
                                {analyzing ? (
                                    <>
                                        <svg style={{ animation: 'spin 1s linear infinite', height: '20px', width: '20px' }} fill="none" viewBox="0 0 24 24"><circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                                        {isDigitalProduct ? 'Analyzing Website...' : 'Analyzing Asset...'}
                                    </>
                                ) : (
                                    <>
                                        {isDigitalProduct ? (
                                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10" /><line x1="2" y1="12" x2="22" y2="12" /><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" /></svg>
                                        ) : (
                                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><circle cx="12" cy="12" r="4"></circle></svg>
                                        )}
                                        {aiBtnLabel}
                                        {!isEditing && <span style={{ fontSize: '10px', marginLeft: '4px', opacity: 0.7 }}>(Save first)</span>}
                                    </>
                                )}
                            </button>
                        </div>
                    </form>
                </div>

                {/* Footer */}
                <div className="pm-footer">
                    <button type="button" onClick={onClose} className="pm-btn-cancel">
                        Cancel
                    </button>
                    <button type="submit" form="product-form" className="pm-btn-save">
                        {isEditing ? 'Save Changes' : isDigitalCreate ? 'Create Product' : 'Save Product'}
                    </button>
                </div>
            </div>

            <MediaPreviewModal
                isOpen={!!previewAssetUrl}
                onClose={() => setPreviewAssetUrl(null)}
                src={previewAssetUrl || ''}
                type="image"
            />
        </div>,
        document.body
    );
}
