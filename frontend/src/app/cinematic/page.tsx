'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiFetch } from '@/lib/utils';
import type { Product, ProductShot } from '@/lib/types';

const SHOT_STYLES = [
  { key: 'hero', label: 'Hero', icon: <svg viewBox="0 0 24 24"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /><polyline points="10 17 15 12 10 7" /><line x1="15" y1="12" x2="3" y2="12" /></svg> },
  { key: 'macro', label: 'Macro Detail', icon: <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg> },
  { key: 'floating', label: 'Floating', icon: <svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></svg> },
  { key: 'moody', label: 'Moody', icon: <svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg> },
];

export default function CinematicPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [products, setProducts] = useState<any[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<string>('');
  const [selectedStyle, setSelectedStyle] = useState('hero');
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchProducts = useCallback(async () => {
    try {
      const data = await apiFetch<any[]>('/api/products');
      setProducts(data || []);

      const targetProductId = searchParams.get('product_id');
      if (targetProductId) {
        setSelectedProductId(targetProductId);
        const prod = (data || []).find((p: any) => p.id === targetProductId);
        if (prod && prod.image_url) {
          setUploadedImage(prod.image_url);
        }
      }
    } catch (e) { console.error(e); }
  }, [searchParams]);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const selectedProduct = products.find((p: any) => p.id === selectedProductId);
  const existingShots: ProductShot[] = selectedProduct?.cinematic_shots || [];

  const handleProductChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const pid = e.target.value;
    setSelectedProductId(pid);
    const prod = products.find((p: any) => p.id === pid);
    if (prod && prod.image_url) {
      setUploadedImage(prod.image_url);
      setUploadedFile(null); // Clear file upload since we use DB image
    } else {
      setUploadedImage(null);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadedFile(file);
    const reader = new FileReader();
    reader.onload = ev => setUploadedImage(ev.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    setUploadedFile(file);
    const reader = new FileReader();
    reader.onload = ev => setUploadedImage(ev.target?.result as string);
    reader.readAsDataURL(file);
  }, []);

  const handleGenerate = async () => {
    if (!selectedProductId) {
      setError("Please select a product first.");
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      const payload = { shot_type: selectedStyle, variations: 1 };
      await apiFetch(`/api/products/${selectedProductId}/shots`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      // Refresh shots
      await fetchProducts();
    } catch (e: any) {
      setError(e.message ?? 'Generation failed. Please try again.');
    }
    setGenerating(false);
  };

  return (
    <div className="cinematic-layout">
      {/* Left Config Panel */}
      <div className="config-panel">
        <div style={{ fontSize: '15px', fontWeight: 800, color: 'var(--text-1)', marginBottom: '20px', letterSpacing: '-0.3px' }}>
          Cinematic Shots
        </div>

        {/* Product Selection */}
        <div className="config-section">
          <div className="config-label">Target Product</div>
          <select value={selectedProductId} onChange={handleProductChange} className="input-field w-full">
            <option value="">Select a physical product...</option>
            {products.map((p: any) => (
              <option key={p.id} value={p.id}>{p.name}</option>
            ))}
          </select>
        </div>

        {/* Product Image Override */}
        <div className="config-section">
          <div className="config-label">Source Image</div>
          <div
            className="upload-zone"
            onClick={() => fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={e => e.preventDefault()}
          >
            {uploadedImage ? (
              <img src={uploadedImage} alt="Product" style={{ width: '100%', borderRadius: 'var(--radius-sm)', objectFit: 'cover', maxHeight: '160px' }} />
            ) : (
              <>
                <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
                <p>Drop image here or <span>browse</span></p>
              </>
            )}
          </div>
          <input ref={fileInputRef} type="file" accept="image/*" style={{ display: 'none' }} onChange={handleFileChange} />
        </div>

        {/* Shot Style Selector */}
        <div className="config-section">
          <div className="config-label">Shot Style</div>
          <div className="shot-type-grid">
            {SHOT_STYLES.map(style => (
              <div
                key={style.key}
                className={`shot-type-card ${selectedStyle === style.key ? 'selected' : ''}`}
                onClick={() => setSelectedStyle(style.key)}
              >
                <div className="shot-icon">{style.icon}</div>
                <div className="shot-label">{style.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Prompt */}
        <div className="config-section">
          <div className="config-label">Additional Prompt (Optional)</div>
          <textarea
            className="config-textarea"
            rows={3}
            placeholder="Describe the scene, lighting, or mood..."
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
          />
        </div>

        {error && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: 'var(--radius-sm)', padding: '10px 12px', marginBottom: '12px', fontSize: '12px', color: 'var(--red)' }}>
            {error}
          </div>
        )}

        <button
          className="btn-generate"
          onClick={handleGenerate}
          disabled={generating || !selectedProductId}
        >
          <svg style={{ width: 16, height: 16, stroke: 'white', fill: 'none', strokeWidth: 2 }} viewBox="0 0 24 24"><polygon points="13,2 3,14 12,14 11,22 21,10 12,10" /></svg>
          {generating ? 'Queuing Generation...' : 'Generate New Shot'}
          <span className="credit-cost">50 cr</span>
        </button>
      </div>

      {/* Right Workspace */}
      <div className="cinematic-workspace" style={{ padding: '32px', overflowY: 'auto' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '24px' }}>
          {selectedProduct ? `Shots for ${selectedProduct.name}` : 'Select a product to view existing shots'}
        </h2>

        {existingShots.length > 0 ? (
          <div className="video-grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))' }}>
            {existingShots.map(shot => {
              const statusClass = shot.status.includes('completed') ? 'done' : shot.status.includes('failed') ? 'failed' : 'processing';
              const statusLabel = shot.status.includes('completed') ? 'Done' : shot.status.includes('failed') ? 'Failed' : 'Processing';
              return (
                <div key={shot.id} className="video-card">
                  <div className="video-thumb" style={{ backgroundColor: 'var(--surface-hover)' }}>
                    {shot.video_url ? (
                      <video src={shot.video_url} style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0 }} autoPlay muted loop playsInline />
                    ) : shot.image_url ? (
                      <img src={shot.image_url} style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0 }} alt="Shot Preview" />
                    ) : (
                      <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-3)', fontSize: '11px' }}>No Preview</div>
                    )}
                    <span className={`status-pill ${statusClass} absolute top-2 right-2 px-2 py-0.5 rounded-full text-[10px] font-bold z-10`} style={{ background: statusClass === 'done' ? 'var(--blue)' : 'var(--red)', color: 'white' }}>{statusLabel}</span>
                  </div>
                  <div className="video-info" style={{ padding: '12px' }}>
                    <div className="video-name" style={{ fontSize: '12px', fontWeight: 600 }}>{shot.shot_type.replace('_', ' ')}</div>
                    <div className="video-date" style={{ fontSize: '10px', color: 'var(--text-3)' }}>{new Date(shot.created_at).toLocaleDateString()}</div>
                  </div>
                  <div className="video-info flex p-2 border-t border-[var(--border-soft)]">
                    <button className="flex-1 py-1.5 bg-[var(--surface-hover)] hover:bg-[var(--blue-light)] hover:text-[var(--blue)] text-[var(--text-2)] rounded text-xs font-semibold" onClick={() => shot.video_url && window.open(shot.video_url)}>
                      Download
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="empty-state" style={{ marginTop: '40px' }}>
            <div className="shot-preview" style={{ width: '100px', height: '100px', background: 'linear-gradient(135deg, #eef2ff 0%, #f8f9ff 100%)', borderRadius: '50%', margin: '0 auto 16px' }}>
              <svg viewBox="0 0 24 24" style={{ width: 40, height: 40, stroke: 'var(--text-3)', fill: 'none', strokeWidth: 1.25, display: 'block', margin: '30px auto' }}><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /><polyline points="10 17 15 12 10 7" /><line x1="15" y1="12" x2="3" y2="12" /></svg>
            </div>
            <div className="empty-title">No cinematic shots yet</div>
            <div className="empty-sub">Generate your first cinematic shot using the controls on the left.</div>
          </div>
        )}
      </div>
    </div>
  );
}
