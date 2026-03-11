import { useState, useRef, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Product } from '@/lib/types';
import Select from '@/components/ui/Select';
import { apiFetch } from '@/lib/utils';
import './ProductModal.css';

interface ProductModalProps {
    isOpen: boolean;
    onClose: () => void;
    product: Product | null;
    onSave: () => void;
}

export default function ProductModal({ isOpen, onClose, product, onSave }: ProductModalProps) {
    const isEditing = !!product;
    const [name, setName] = useState(product?.name || '');
    const [type, setType] = useState(product?.type || 'physical');
    const [imageUrl, setImageUrl] = useState(product?.image_url || '');
    const [uploading, setUploading] = useState(false);

    // AI Analysis State
    const [analyzing, setAnalyzing] = useState(false);
    const [analysisResult, setAnalysisResult] = useState<any>(product?.visual_description || null);

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
                body: JSON.stringify({ bucket: 'product-images', file_name: file.name }),
            });

            if (!signRes.signed_url) throw new Error("Could not get signed URL");

            // Upload directly to Supabase via signed URL
            const uploadRes = await fetch(signRes.signed_url, {
                method: 'PUT',
                body: file,
                headers: { 'Content-Type': file.type }
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

    const handleAnalyze = async () => {
        if (!product?.id) {
            alert("Please save the product first before analyzing.");
            return;
        }

        setAnalyzing(true);
        try {
            const result = await apiFetch<any>('/api/products/analyze', {
                method: 'POST',
                body: JSON.stringify({ product_id: product.id }),
            });
            setAnalysisResult(result);
        } catch (err: any) {
            console.error(err);
            alert(err.message || 'Failed to analyze image.');
        } finally {
            setAnalyzing(false);
        }
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();

        try {
            if (!isEditing) {
                // Create
                await apiFetch('/api/products', {
                    method: 'POST',
                    body: JSON.stringify({
                        name,
                        type,
                        image_url: imageUrl,
                        product_type: type
                    }),
                });
            } else {
                // Currently backend doesn't have PUT /api/products/{id}.
                // We'll mimic save by closing. Analysis auto-saves to DB.
            }
            onSave();
            onClose();
        } catch (err) {
            console.error(err);
            alert('Failed to save product.');
        }
    };

    return createPortal(
        <div className="pm-overlay">
            <div className="pm-container">

                {/* Header */}
                <div className="pm-header">
                    <h2>{isEditing ? 'Asset Settings & Analysis' : 'Add New Product'}</h2>
                    <button onClick={onClose} className="pm-close-btn" title="Close">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M18 6L6 18M6 6l12 12" /></svg>
                    </button>
                </div>

                {/* Body */}
                <div className="pm-body custom-scrollbar">
                    <form id="product-form" onSubmit={handleSubmit} className="pm-grid">

                        {/* Left Col: Core Details & Image */}
                        <div>
                            <div className="pm-form-group">
                                <label className="pm-label">Product Name</label>
                                <input
                                    required
                                    value={name}
                                    onChange={e => setName(e.target.value)}
                                    placeholder="Ex: Moisturizing Conditioner"
                                    className="pm-input"
                                />
                            </div>

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

                            <div className="pm-form-group">
                                <label className="pm-label">Preview Image</label>
                                <div className="pm-image-upload">
                                    <input type="file" ref={fileInputRef} className="hidden" style={{ display: 'none' }} accept="image/*" onChange={handleFileChange} />

                                    {imageUrl ? (
                                        <div className="pm-preview">
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
                        </div>

                        {/* Right Col: AI Analysis */}
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                            <div>
                                <label className="pm-label pm-ai-gradient-text">AI Vision Analysis</label>
                                <p className="pm-ai-desc">
                                    Extract visual properties, brand colors, and aesthetic positioning from your product image using GPT-4o.
                                </p>
                            </div>

                            {/* Analysis Container */}
                            <div className="pm-analysis-container">
                                {!analysisResult ? (
                                    <div className="pm-analysis-empty">
                                        <div className="pm-analysis-empty-icon">
                                            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M2 12h4l3-9 5 18 3-9h5" /></svg>
                                        </div>
                                        <p style={{ fontSize: '14px', fontWeight: 500 }}>No analysis data yet.</p>
                                        <p style={{ fontSize: '12px', marginTop: '4px' }}>Run the AI analyzer to extract product metadata.</p>
                                    </div>
                                ) : (
                                    <div className="pm-analysis-content">
                                        {/* Parse JSON if it's an object, or show raw text */}
                                        {typeof analysisResult === 'object' ? (
                                            Object.keys(analysisResult).map((key) => (
                                                <div key={key} className="pm-analysis-item" key={`k_${key}`}>
                                                    <span style={{ display: 'block', fontSize: '10px', fontWeight: 700, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.1em', marginBottom: '4px' }}>
                                                        {key.replace(/_/g, ' ')}
                                                    </span>
                                                    <span style={{ color: '#1e293b', wordBreak: 'break-word' }}>
                                                        {typeof analysisResult[key] === 'object'
                                                            ? JSON.stringify(analysisResult[key], null, 2)
                                                            : String(analysisResult[key])}
                                                    </span>
                                                </div>
                                            ))
                                        ) : (
                                            <div className="pm-analysis-item" style={{ whiteSpace: 'pre-wrap' }}>
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
                                disabled={!imageUrl || analyzing || !isEditing}
                                className={`pm-ai-btn ${(!imageUrl || !isEditing) ? 'disabled' : 'active'}`}
                            >
                                {analyzing ? (
                                    <>
                                        <svg style={{ animation: 'spin 1s linear infinite', height: '20px', width: '20px' }} fill="none" viewBox="0 0 24 24"><circle style={{ opacity: 0.25 }} cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle><path style={{ opacity: 0.75 }} fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
                                        Analyzing Asset...
                                    </>
                                ) : (
                                    <>
                                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><circle cx="12" cy="12" r="4"></circle></svg>
                                        Analyze Image with AI
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
                    {!isEditing && (
                        <button type="submit" form="product-form" className="pm-btn-save">
                            Save Product
                        </button>
                    )}
                </div>
            </div>
        </div>,
        document.body
    );
}
