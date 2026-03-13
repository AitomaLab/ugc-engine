'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import MediaPreviewModal from '@/components/ui/MediaPreviewModal';
import Select from '@/components/ui/Select';
import { apiFetch } from '@/lib/utils';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';

interface Clip {
  id: string;
  name: string;
  aspect_ratio?: string;
  duration?: number;
  created_at?: string;
  thumbnail_url?: string;
  video_url?: string;
  campaign_name?: string;
  product_id?: string;
}

interface Product {
  id: string;
  name: string;
  type?: string;
}

/* ------------------------------------------------------------------ */
/*  Upload / URL Modal                                                 */
/* ------------------------------------------------------------------ */
function AppClipModal({ isOpen, onClose, onSaved }: { isOpen: boolean; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState('');
  const [videoUrl, setVideoUrl] = useState('');
  const [mode, setMode] = useState<'upload' | 'url'>('upload');
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    if (isOpen) { setName(''); setVideoUrl(''); setError(null); setMode('upload'); }
  }, [isOpen]);

  if (!isOpen) return null;

  async function uploadFile(file: File) {
    if (!file.type.startsWith('video/')) { setError('Please select a video file.'); return; }
    if (file.size > 200 * 1024 * 1024) { setError('Video must be under 200 MB.'); return; }

    try {
      setUploading(true);
      setError(null);

      const cleanName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_');
      const fileName = `clip_${Date.now()}_${cleanName}`;

      const { signed_url, path } = await apiFetch<{ signed_url: string; path: string }>('/assets/signed-url', {
        method: 'POST',
        body: JSON.stringify({ bucket: 'app-clips', file_name: fileName }),
      });

      const uploadRes = await fetch(signed_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': file.type },
      });
      if (!uploadRes.ok) throw new Error('Upload failed');

      const publicUrl = `${SUPABASE_URL}/storage/v1/object/public/app-clips/${path}`;
      setVideoUrl(publicUrl);
      if (!name) setName(file.name.replace(/\.[^.]+$/, ''));
    } catch (err) {
      console.error('Upload error:', err);
      setError('Failed to upload video. Please try again.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) uploadFile(file);
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) uploadFile(file);
  }

  async function handleSave() {
    if (!name.trim()) { setError('Please enter a name.'); return; }
    if (!videoUrl.trim()) { setError('Please upload a video or paste a URL.'); return; }
    try {
      setSaving(true);
      setError(null);
      await apiFetch('/app-clips', {
        method: 'POST',
        body: JSON.stringify({ name: name.trim(), video_url: videoUrl.trim() }),
      });
      onSaved();
      onClose();
    } catch (err: any) {
      console.error('Save error:', err);
      setError(err.message || 'Failed to save clip.');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-overlay">
      <div className="modal-box">
        {/* Header */}
        <div className="modal-header">
          <h3>New App Clip</h3>
          <button className="modal-close" onClick={onClose}>
            <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* Name */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>Clip Name</label>
            <input
              className="input-field"
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Product Demo Clip"
            />
          </div>

          {/* Mode tabs */}
          <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)', marginBottom: '16px' }}>
            <button
              onClick={() => setMode('upload')}
              style={{ flex: 'none', padding: '8px 16px', fontSize: '12px', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', borderBottom: mode === 'upload' ? '2px solid var(--blue)' : '2px solid transparent', color: mode === 'upload' ? 'var(--blue)' : 'var(--text-3)', transition: 'all 0.15s' }}
            >
              Upload Video
            </button>
            <button
              onClick={() => setMode('url')}
              style={{ flex: 'none', padding: '8px 16px', fontSize: '12px', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer', borderBottom: mode === 'url' ? '2px solid var(--blue)' : '2px solid transparent', color: mode === 'url' ? 'var(--blue)' : 'var(--text-3)', transition: 'all 0.15s' }}
            >
              Paste URL
            </button>
          </div>

          {/* Upload mode */}
          {mode === 'upload' && (
            <div>
              {videoUrl && mode === 'upload' ? (
                <div style={{ position: 'relative', borderRadius: '10px', overflow: 'hidden', aspectRatio: '16/9', background: '#000' }}>
                  <video src={videoUrl} style={{ width: '100%', height: '100%', objectFit: 'contain' }} controls />
                  <button
                    onClick={() => { setVideoUrl(''); }}
                    style={{ position: 'absolute', top: '8px', right: '8px', width: '24px', height: '24px', borderRadius: '50%', background: 'rgba(0,0,0,0.6)', color: 'white', border: 'none', cursor: 'pointer', fontSize: '14px', display: 'flex', alignItems: 'center', justifyContent: 'center' }}
                  >&times;</button>
                </div>
              ) : (
                <div
                  onClick={() => fileInputRef.current?.click()}
                  onDragOver={e => { e.preventDefault(); setDragActive(true); }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={handleDrop}
                  style={{
                    border: `2px dashed ${dragActive ? 'var(--blue)' : 'var(--border)'}`,
                    borderRadius: '10px',
                    padding: '32px 20px',
                    textAlign: 'center',
                    cursor: 'pointer',
                    background: dragActive ? 'rgba(51,122,255,0.04)' : 'var(--blue-light)',
                    transition: 'all 0.15s',
                  }}
                >
                  {uploading ? (
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '24px', height: '24px', border: '2px solid var(--border)', borderTopColor: 'var(--blue)', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
                      <span style={{ fontSize: '12px', color: 'var(--text-2)' }}>Uploading...</span>
                    </div>
                  ) : (
                    <>
                      <svg viewBox="0 0 24 24" style={{ width: '28px', height: '28px', stroke: 'var(--text-3)', fill: 'none', strokeWidth: 1.5, margin: '0 auto 8px' }}>
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
                      </svg>
                      <p style={{ fontSize: '13px', color: 'var(--text-2)', margin: 0 }}>
                        Drop a video here or <span style={{ color: 'var(--blue)', fontWeight: 600 }}>browse</span>
                      </p>
                      <p style={{ fontSize: '11px', color: 'var(--text-3)', margin: '4px 0 0' }}>MP4, MOV, WebM — max 200 MB</p>
                    </>
                  )}
                </div>
              )}
              <input ref={fileInputRef} type="file" accept="video/*" style={{ display: 'none' }} onChange={handleFileChange} />
            </div>
          )}

          {/* URL mode */}
          {mode === 'url' && (
            <div>
              <input
                className="input-field"
                type="url"
                value={videoUrl}
                onChange={e => setVideoUrl(e.target.value)}
                placeholder="https://example.com/video.mp4"
              />
              <p style={{ fontSize: '11px', color: 'var(--text-3)', margin: '6px 0 0' }}>Direct link to a publicly accessible video file.</p>
              {videoUrl && videoUrl.startsWith('http') && (
                <div style={{ marginTop: '12px', borderRadius: '10px', overflow: 'hidden', aspectRatio: '16/9', background: '#000' }}>
                  <video src={videoUrl} style={{ width: '100%', height: '100%', objectFit: 'contain' }} controls />
                </div>
              )}
            </div>
          )}

          {/* Error */}
          {error && (
            <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px', padding: '8px 12px', marginTop: '12px', fontSize: '12px', color: 'var(--red)' }}>
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button
            className="btn-primary"
            onClick={handleSave}
            disabled={saving || uploading || !name.trim() || !videoUrl.trim()}
            style={{ opacity: (saving || uploading || !name.trim() || !videoUrl.trim()) ? 0.5 : 1 }}
          >
            {saving ? 'Saving...' : 'Save Clip'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main Page                                                          */
/* ------------------------------------------------------------------ */
export default function AppClipsPage() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [previewAssetUrl, setPreviewAssetUrl] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);

  const fetchClips = useCallback(async () => {
    try {
      const data = await apiFetch<Clip[]>('/app-clips');
      setClips(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  const fetchProducts = useCallback(async () => {
    try {
      const data = await apiFetch<Product[]>('/api/products');
      console.log('App Clips: fetched products', data?.length);
      setProducts(data || []);
    } catch (e) { console.error('App Clips: failed to fetch products', e); }
  }, []);

  useEffect(() => {
    fetchClips();
    fetchProducts();
  }, [fetchClips, fetchProducts]);

  async function handleDelete(id: string) {
    if (!confirm('Delete this app clip? This cannot be undone.')) return;
    try {
      await apiFetch(`/app-clips/${id}`, { method: 'DELETE' });
      setClips(prev => prev.filter(c => c.id !== id));
    } catch (err) { console.error('Delete error:', err); }
  }

  const filtered = clips.filter(c =>
    (c.name || '').toLowerCase().includes(search.toLowerCase())
  );

  const formatDate = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'numeric', day: 'numeric', year: 'numeric' });

  return (
    <div className='content-area'>
      <div className='page-header'>
        <h1>App Clips</h1>
        <p>Short-form clips optimised for app store previews and ads.</p>
      </div>

      <div className='asset-toolbar'>
        <div className='asset-toolbar-left'>
          <div className='search-box'>
            <svg viewBox='0 0 24 24'><circle cx='11' cy='11' r='8' /><line x1='21' y1='21' x2='16.65' y2='16.65' /></svg>
            <input type='text' placeholder='Search app clips...' value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>
        <button className='btn-create' onClick={() => setModalOpen(true)}>
          <svg viewBox='0 0 24 24'><line x1='12' y1='5' x2='12' y2='19' /><line x1='5' y1='12' x2='19' y2='12' /></svg>
          New App Clip
        </button>
      </div>

      {loading ? (
        <div className='empty-state'><div className='empty-title'>Loading clips...</div></div>
      ) : filtered.length === 0 ? (
        <div className='empty-state'>
          <div className='empty-icon'>
            <svg viewBox='0 0 24 24'><rect x='5' y='2' width='14' height='20' rx='2' /><line x1='12' y1='18' x2='12.01' y2='18' /></svg>
          </div>
          <div className='empty-title'>No app clips yet</div>
          <div className='empty-sub'>App clips are short-form versions of your videos optimised for app store previews.</div>
          <button className='btn-primary' onClick={() => setModalOpen(true)}>Add Clip</button>
        </div>
      ) : (
        <div className='video-grid'>
          {filtered.map((clip, i) => (
            <div key={clip.id} className='video-card'>
              <div
                className={`video-thumb grad-${(i % 5) + 1}`}
                style={{
                  backgroundImage: clip.thumbnail_url ? `url(${clip.thumbnail_url})` : 'none',
                  cursor: (clip.video_url || clip.thumbnail_url) ? 'zoom-in' : 'default'
                }}
                onClick={() => {
                  const url = clip.video_url || clip.thumbnail_url;
                  if (url) setPreviewAssetUrl(url);
                }}
              >
                <button className="card-delete-btn" onClick={(e) => { e.stopPropagation(); handleDelete(clip.id); }} title="Delete clip">
                  <svg viewBox="0 0 24 24"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                </button>
                {clip.video_url && (
                  <video src={clip.video_url} style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0 }} muted loop playsInline />
                )}
                <span className='status-pill done absolute top-2 right-2 px-2 py-0.5 rounded-full text-[10px] font-bold bg-[var(--blue)] text-white z-10'>{clip.duration ? `${clip.duration}s` : 'Clip'}</span>
              </div>
              <div className='video-info'>
                <div className='video-name'>{clip.name || clip.campaign_name || 'Untitled Clip'}</div>
                <div className='video-date'>{clip.created_at ? formatDate(clip.created_at) : ''}  {clip.aspect_ratio || '9:16'}</div>
                <Select
                  value={clip.product_id || ''}
                  onChange={async (val) => {
                    const newProductId = val || null;
                    try {
                      await apiFetch(`/api/app-clips/${clip.id}`, {
                        method: 'PATCH',
                        body: JSON.stringify({ product_id: newProductId }),
                      });
                      fetchClips();
                    } catch (err) { console.error('Link error:', err); }
                  }}
                  placeholder="No product linked"
                  className="filter-select"
                  style={{ width: '100%', marginTop: '6px' }}
                  options={[
                    { value: '', label: 'No product linked' },
                    ...products.filter(p => p.type === 'digital').map(p => ({ value: p.id, label: p.name })),
                  ]}
                />
              </div>
              <div className='video-info' style={{ display: 'flex', gap: '8px', paddingTop: 0, paddingBottom: '12px', marginTop: 'auto' }}>
                <button style={{ flex: 1, padding: '6px 0', backgroundColor: 'var(--surface-hover)', color: 'var(--blue)', borderRadius: '4px', fontSize: '12px', fontWeight: 600, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', border: '1px solid rgba(51,122,255,0.15)', cursor: 'pointer' }} onClick={() => window.open(clip.video_url || '')}>
                  <svg viewBox='0 0 24 24' style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' /><polyline points='7 10 12 15 17 10' /><line x1='12' y1='15' x2='12' y2='3' /></svg>
                  Save
                </button>
                <button style={{ flex: 1, padding: '6px 0', backgroundColor: 'transparent', color: 'var(--text-2)', borderRadius: '4px', fontSize: '12px', fontWeight: 600, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', border: '1px solid var(--border)', cursor: 'pointer' }}>
                  <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" /></svg>
                  Share
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      <AppClipModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={() => { fetchClips(); setModalOpen(false); }}
      />

      <MediaPreviewModal
        isOpen={!!previewAssetUrl}
        onClose={() => setPreviewAssetUrl(null)}
        src={previewAssetUrl || ''}
        type="mixed"
      />
    </div>
  );
}
