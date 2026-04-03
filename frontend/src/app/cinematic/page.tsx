'use client';

import { Suspense, useState, useEffect, useRef, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiFetch } from '@/lib/utils';
import type { ProductShot } from '@/lib/types';
import Select from '@/components/ui/Select';
import MediaPreviewModal from '@/components/ui/MediaPreviewModal';

const SHOT_STYLES = [
  { key: 'hero', label: 'Hero', icon: <svg viewBox="0 0 24 24"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /><polyline points="10 17 15 12 10 7" /><line x1="15" y1="12" x2="3" y2="12" /></svg> },
  { key: 'macro_detail', label: 'Macro Detail', icon: <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" /></svg> },
  { key: 'elevated', label: 'Elevated', icon: <svg viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5z" /><path d="M2 17l10 5 10-5" /><path d="M12 12v10" /></svg> },
  { key: 'moody_dramatic', label: 'Moody', icon: <svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" /></svg> },
  { key: 'floating', label: 'Floating', icon: <svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7" /><polyline points="2 17 12 22 22 17" /><polyline points="2 12 12 17 22 12" /></svg> },
  { key: 'lifestyle', label: 'Lifestyle', icon: <svg viewBox="0 0 24 24"><path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><polyline points="9 22 9 12 15 12 15 22" /></svg> },
  { key: 'silhouette', label: 'Silhouette', icon: <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><circle cx="12" cy="12" r="6" /></svg> },
  { key: 'overhead', label: 'Overhead', icon: <svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2" /><line x1="3" y1="9" x2="21" y2="9" /><line x1="9" y1="21" x2="9" y2="9" /></svg> },
];

function CinematicContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [products, setProducts] = useState<any[]>([]);
  const [selectedProductId, setSelectedProductId] = useState<string>('');
  const [selectedStyles, setSelectedStyles] = useState<Set<string>>(new Set(['hero']));
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [previewAssetUrl, setPreviewAssetUrl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [productShots, setProductShots] = useState<ProductShot[]>([]);
  const [animatingIds, setAnimatingIds] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<'images' | 'videos'>('images');

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

  // Re-fetch when user switches projects
  useEffect(() => {
    const handler = () => {
      setProducts([]);
      setProductShots([]);
      setSelectedProductId('');
      setUploadedImage(null);
      fetchProducts();
    };
    window.addEventListener('projectChanged', handler);
    return () => window.removeEventListener('projectChanged', handler);
  }, [fetchProducts]);

  const fetchShots = useCallback(async (pid: string) => {
    if (!pid) {
      setProductShots([]);
      return;
    }
    try {
      const data = await apiFetch<ProductShot[]>(`/api/products/${pid}/shots`);
      setProductShots(data || []);
    } catch (e) {
      console.error(e);
      setProductShots([]);
    }
  }, []);

  useEffect(() => {
    fetchShots(selectedProductId);
  }, [selectedProductId, fetchShots]);

  // Poll for generating shots
  useEffect(() => {
    if (!selectedProductId || productShots.length === 0) return;
    const hasPending = productShots.some(s => s.status.includes('pending') || s.status.includes('processing') || s.status === 'image_completed');
    if (!hasPending) return;

    const interval = setInterval(() => {
      fetchShots(selectedProductId);
    }, 4000);
    return () => clearInterval(interval);
  }, [productShots, selectedProductId, fetchShots]);

  const selectedProduct = products.find((p: any) => p.id === selectedProductId);
  const existingShots: ProductShot[] = productShots;

  const handleProductChange = async (value: string) => {
    const pId = value;
    setSelectedProductId(pId);
    const prod = products.find((p: any) => p.id === pId);
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
    if (selectedStyles.size === 0) {
      setError("Please select at least one shot style.");
      return;
    }
    setGenerating(true);
    setError(null);
    try {
      // Generate one shot per selected style
      for (const style of selectedStyles) {
        await apiFetch(`/api/products/${selectedProductId}/shots`, {
          method: 'POST',
          body: JSON.stringify({ shot_type: style, variations: 1 }),
        });
      }
      // Refresh shots
      await fetchShots(selectedProductId);
    } catch (e: any) {
      setError(e.message ?? 'Generation failed. Please try again.');
    }
    setGenerating(false);
  };

  const handleAnimate = async (shotId: string) => {
    setAnimatingIds(prev => new Set(prev).add(shotId));
    try {
      await apiFetch(`/api/shots/${shotId}/animate`, { method: 'POST' });
      setProductShots(prev => prev.map(s =>
        s.id === shotId ? { ...s, status: 'animation_pending' as const } : s
      ));
    } catch (err) {
      console.error('Animate error:', err);
      setError('Failed to start animation. Please try again.');
    } finally {
      setAnimatingIds(prev => {
        const next = new Set(prev);
        next.delete(shotId);
        return next;
      });
    }
  };

  const handleDownload = (url: string) => {
    window.open(url, '_blank');
  };

  async function handleDeleteShot(shotId: string) {
    if (!confirm('Delete this shot? This cannot be undone.')) return;
    try {
      await apiFetch(`/api/shots/${shotId}`, { method: 'DELETE' });
      setProductShots(prev => prev.filter(s => s.id !== shotId));
    } catch (err) { console.error('Delete error:', err); }
  }

  // Derived lists for dual-section grid
  const imageShots = existingShots.filter(s => s.image_url || s.status === 'image_pending');
  const videoShots = existingShots.filter(s => s.status === 'animation_completed' || s.status === 'animation_pending');
  const failedShots = existingShots.filter(s => s.status === 'failed');

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
          <Select
            className="input-field w-full"
            value={selectedProductId}
            onChange={handleProductChange}
            placeholder="Select a physical product..."
            options={[
              { value: '', label: 'Select a physical product...' },
              ...products.map((p: any) => ({ value: p.id, label: p.name }))
            ]}
          />
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
                className={`shot-type-card ${selectedStyles.has(style.key) ? 'selected' : ''}`}
                onClick={() => {
                  setSelectedStyles(prev => {
                    const next = new Set(prev);
                    if (next.has(style.key)) {
                      next.delete(style.key);
                    } else {
                      next.add(style.key);
                    }
                    return next;
                  });
                }}
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
          disabled={generating || !selectedProductId || selectedStyles.size === 0}
        >
          <svg style={{ width: 16, height: 16, stroke: 'white', fill: 'none', strokeWidth: 2 }} viewBox="0 0 24 24"><polygon points="13,2 3,14 12,14 11,22 21,10 12,10" /></svg>
          {generating ? 'Generating...' : `Generate ${selectedStyles.size} Shot${selectedStyles.size !== 1 ? 's' : ''}`}
          <span className="credit-cost">{selectedStyles.size * 13} <img src="/star-white.png" alt="credits" style={{ height: 12, width: 12, verticalAlign: 'middle', marginLeft: 2, display: 'inline' }} /></span>
        </button>
      </div>

      {/* Right Workspace */}
      <div className="cinematic-workspace">
        <h2 style={{ fontSize: '18px', fontWeight: 700, marginBottom: '20px' }}>
          {selectedProduct ? `Shots for ${selectedProduct.name}` : 'Select a product to view existing shots'}
        </h2>

        {existingShots.length > 0 ? (
          <>
            {/* Tab bar */}
            <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: '20px' }}>
              <button
                onClick={() => setActiveTab('images')}
                style={{ flex: 'none', padding: '10px 20px', fontSize: '13px', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', borderBottom: activeTab === 'images' ? '2px solid var(--blue)' : '2px solid transparent', color: activeTab === 'images' ? 'var(--blue)' : 'var(--text-3)', transition: 'all 0.15s' }}
              >
                Cinematic Images ({imageShots.length})
              </button>
              <button
                onClick={() => setActiveTab('videos')}
                style={{ flex: 'none', padding: '10px 20px', fontSize: '13px', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', borderBottom: activeTab === 'videos' ? '2px solid #a78bfa' : '2px solid transparent', color: activeTab === 'videos' ? '#a78bfa' : 'var(--text-3)', transition: 'all 0.15s' }}
              >
                Cinematic Videos ({videoShots.length})
              </button>
            </div>

            {/* Images tab */}
            {activeTab === 'images' && (
              imageShots.length > 0 ? (
                <div className="video-grid">
                  {imageShots.map(shot => {
                    const canAnimate = shot.status === 'image_completed';
                    const isAnimatingShot = shot.status === 'animation_pending' || animatingIds.has(shot.id);
                    const hasVideo = shot.status === 'animation_completed';
                    return (
                      <div key={`img-${shot.id}`} className="video-card">
                        <div className="video-thumb" style={{ backgroundColor: 'var(--surface-hover)' }}>
                          <button className="card-delete-btn" onClick={() => handleDeleteShot(shot.id)} title="Delete shot">
                            <svg viewBox="0 0 24 24"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                          </button>
                          {shot.image_url ? (
                            <img
                              src={shot.image_url}
                              style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0, cursor: 'pointer' }}
                              alt="Shot Preview"
                              onClick={() => setPreviewAssetUrl(shot.image_url!)}
                            />
                          ) : (
                            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '8px' }}>
                              <div style={{ width: '24px', height: '24px', border: '2px solid var(--border)', borderTopColor: 'var(--blue)', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                              <span style={{ fontSize: '10px', color: 'var(--text-3)' }}>Generating...</span>
                            </div>
                          )}
                          {isAnimatingShot && shot.image_url && (
                            <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '8px' }}>
                              <div style={{ width: '24px', height: '24px', border: '2px solid rgba(255,255,255,0.2)', borderTopColor: '#a78bfa', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                              <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.7)' }}>Animating...</span>
                            </div>
                          )}
                          <span className="status-pill" style={{
                            position: 'absolute', top: '8px', right: '8px', fontWeight: 700, color: 'white',
                            background: hasVideo ? '#22c55e' : canAnimate ? 'var(--blue)' : isAnimatingShot ? '#a78bfa' : shot.status === 'failed' ? 'var(--red)' : '#eab308',
                          }}>
                            {hasVideo ? 'Video Ready' : canAnimate ? 'Done' : isAnimatingShot ? 'Animating' : shot.status === 'failed' ? 'Failed' : 'Processing'}
                          </span>
                        </div>
                        <div className="video-info" style={{ paddingBottom: '12px' }}>
                          <div className="video-name" style={{ fontWeight: 700 }}>{shot.shot_type.replace(/_/g, ' ')}</div>
                          <div className="video-date" style={{ marginTop: '4px' }}>{new Date(shot.created_at).toLocaleDateString()}</div>
                        </div>
                        <div className="video-info" style={{ display: 'flex', gap: '8px', paddingTop: 0, paddingBottom: '12px', marginTop: 'auto', flexWrap: 'wrap' }}>
                          {shot.image_url && (
                            <button
                              style={{ flex: 1, padding: '6px 0', backgroundColor: 'var(--surface-hover)', color: 'var(--blue)', borderRadius: '4px', fontSize: '12px', fontWeight: 600, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', border: '1px solid rgba(51,122,255,0.15)', cursor: 'pointer' }}
                              onClick={() => handleDownload(shot.image_url!)}
                            >
                              <svg viewBox='0 0 24 24' style={{ width: '12px', height: '12px', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' /><polyline points='7 10 12 15 17 10' /><line x1='12' y1='15' x2='12' y2='3' /></svg>
                              Download
                            </button>
                          )}
                          {canAnimate && (
                            <button
                              style={{ flex: 1, padding: '6px 0', backgroundColor: 'var(--blue)', color: 'white', borderRadius: '4px', fontSize: '12px', fontWeight: 600, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', border: 'none', cursor: 'pointer', opacity: animatingIds.has(shot.id) ? 0.6 : 1 }}
                              onClick={() => handleAnimate(shot.id)}
                              disabled={animatingIds.has(shot.id)}
                            >
                              <svg viewBox="0 0 24 24" style={{ width: '12px', height: '12px', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><polygon points="5 3 19 12 5 21 5 3" /></svg>
                              {animatingIds.has(shot.id) ? 'Queuing...' : 'Animate'}
                              <span style={{ marginLeft: '4px', fontSize: '10px', opacity: 0.85, display: 'inline-flex', alignItems: 'center', gap: '2px' }}>51 <img src="/star-white.png" alt="credits" style={{ height: 10, width: 10 }} /></span>
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-title">No cinematic images yet</div>
                  <div className="empty-sub">Generate shots using the controls on the left.</div>
                </div>
              )
            )}

            {/* Videos tab */}
            {activeTab === 'videos' && (
              videoShots.length > 0 ? (
                <div className="video-grid">
                  {videoShots.map(shot => {
                    const isReady = shot.status === 'animation_completed' && shot.video_url;
                    return (
                      <div key={`vid-${shot.id}`} className="video-card">
                        <div className="video-thumb" style={{ backgroundColor: 'var(--surface-hover)' }}>
                          <button className="card-delete-btn" onClick={() => handleDeleteShot(shot.id)} title="Delete shot">
                            <svg viewBox="0 0 24 24"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                          </button>
                          {shot.video_url ? (
                            <video
                              src={shot.video_url}
                              style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0, cursor: 'pointer' }}
                              autoPlay muted loop playsInline
                              poster={shot.image_url}
                              onClick={() => setPreviewAssetUrl(shot.video_url!)}
                            />
                          ) : shot.image_url ? (
                            <>
                              <img src={shot.image_url} style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0 }} alt="Shot Preview" />
                              <div style={{ position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '8px' }}>
                                <div style={{ width: '24px', height: '24px', border: '2px solid rgba(255,255,255,0.2)', borderTopColor: '#a78bfa', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                                <span style={{ fontSize: '10px', color: 'rgba(255,255,255,0.7)' }}>Animating...</span>
                              </div>
                            </>
                          ) : (
                            <div style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: '8px' }}>
                              <div style={{ width: '24px', height: '24px', border: '2px solid var(--border)', borderTopColor: '#a78bfa', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                              <span style={{ fontSize: '10px', color: 'var(--text-3)' }}>Animating...</span>
                            </div>
                          )}
                          <span className="status-pill" style={{
                            position: 'absolute', top: '8px', right: '8px', fontWeight: 700, color: 'white',
                            background: isReady ? '#22c55e' : '#a78bfa',
                          }}>
                            {isReady ? 'Video Ready' : 'Animating'}
                          </span>
                        </div>
                        <div className="video-info" style={{ paddingBottom: '12px' }}>
                          <div className="video-name" style={{ fontWeight: 700 }}>{shot.shot_type.replace(/_/g, ' ')}</div>
                          <div className="video-date" style={{ marginTop: '4px' }}>{new Date(shot.created_at).toLocaleDateString()}</div>
                        </div>
                        <div className="video-info" style={{ display: 'flex', gap: '8px', paddingTop: 0, paddingBottom: '12px', marginTop: 'auto', flexWrap: 'wrap' }}>
                          {shot.video_url ? (
                            <>
                              <button
                                style={{ flex: 1, padding: '6px 0', backgroundColor: 'var(--surface-hover)', color: 'var(--blue)', borderRadius: '4px', fontSize: '12px', fontWeight: 600, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', border: '1px solid rgba(51,122,255,0.15)', cursor: 'pointer' }}
                                onClick={() => handleDownload(shot.video_url!)}
                              >
                                <svg viewBox='0 0 24 24' style={{ width: '12px', height: '12px', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' /><polyline points='7 10 12 15 17 10' /><line x1='12' y1='15' x2='12' y2='3' /></svg>
                                Download
                              </button>
                              <button
                                style={{ flex: 1, padding: '6px 0', backgroundColor: 'transparent', color: 'var(--text-2)', borderRadius: '4px', fontSize: '12px', fontWeight: 600, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', border: '1px solid var(--border)', cursor: 'pointer' }}
                                onClick={() => router.push(`/create?product_id=${shot.product_id}`)}
                              >
                                <svg viewBox="0 0 24 24" style={{ width: '12px', height: '12px', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" /><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" /></svg>
                                Use
                              </button>
                            </>
                          ) : (
                            <button style={{ width: '100%', padding: '6px 0', backgroundColor: 'transparent', color: 'var(--text-3)', borderRadius: '20px', fontSize: '12px', fontWeight: 600, border: '1px solid var(--border)', opacity: 0.6, cursor: 'not-allowed' }} disabled>
                              Animating...
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="empty-state">
                  <div className="empty-title">No cinematic videos yet</div>
                  <div className="empty-sub">Animate a product shot to create a cinematic video.</div>
                </div>
              )
            )}

            {/* Failed shots (shown on both tabs) */}
            {failedShots.length > 0 && (
              <div style={{ marginTop: '24px', borderTop: '1px solid var(--border)', paddingTop: '16px' }}>
                <div style={{ fontSize: '10px', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--red)', fontWeight: 700, marginBottom: '10px' }}>
                  Failed ({failedShots.length})
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                  {failedShots.map(shot => (
                    <div key={shot.id} style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'rgba(239,68,68,0.05)', border: '1px solid rgba(239,68,68,0.1)', borderRadius: '8px', padding: '8px 12px' }}>
                      <span style={{ fontSize: '11px', color: 'var(--red)', textTransform: 'capitalize' }}>{shot.shot_type.replace(/_/g, ' ')}</span>
                      {shot.error_message && <span style={{ fontSize: '10px', color: 'var(--text-3)' }} title={shot.error_message}>— {shot.error_message.slice(0, 50)}</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
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

      <MediaPreviewModal
        isOpen={!!previewAssetUrl}
        onClose={() => setPreviewAssetUrl(null)}
        src={previewAssetUrl || ''}
        type="mixed"
      />
    </div>
  );
}

export default function CinematicPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <CinematicContent />
    </Suspense>
  );
}
