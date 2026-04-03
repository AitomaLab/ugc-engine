'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/utils';
import { Influencer } from '@/lib/types';
import { InfluencerModal } from '@/app/library/InfluencerModal';
import Select from '@/components/ui/Select';
import { useProgressiveList } from '@/hooks/useProgressiveList';
import { useTranslation } from '@/lib/i18n';

// IDs of looks currently being generated (polling for completion)
const pendingLookIds = new Set<string>();

// ─────────────────────────────────────────────────────────────────────────────
// AI Clones Tab Component
// ─────────────────────────────────────────────────────────────────────────────

const SUPABASE_URL_CLONES = process.env.NEXT_PUBLIC_SUPABASE_URL || '';

function AiClonesTab() {
  const { t } = useTranslation();
  const [clones, setClones] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedCloneId, setSelectedCloneId] = useState<string>('');
  const [looks, setLooks] = useState<any[]>([]);
  const [looksLoading, setLooksLoading] = useState(false);

  // Setup form state (shown when no clone exists yet)
  const [setupName, setSetupName] = useState('My AI Clone');
  const [setupVoiceId, setSetupVoiceId] = useState('');
  const [setupGender, setSetupGender] = useState('male');
  const [setupImageFile, setSetupImageFile] = useState<File | null>(null);
  const [setupImagePreview, setSetupImagePreview] = useState('');
  const [setupSaving, setSetupSaving] = useState(false);
  const [setupError, setSetupError] = useState('');
  const setupFileRef = useRef<HTMLInputElement>(null);

  // Upload state
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // AI Look generation modal state
  const [showGenModal, setShowGenModal] = useState(false);
  const [genPrompt, setGenPrompt] = useState('');
  const [genLabel, setGenLabel] = useState('AI Generated Look');
  const [genBaseLookId, setGenBaseLookId] = useState('');
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState('');

  // Edit clone state
  const [editName, setEditName] = useState('');
  const [editVoiceId, setEditVoiceId] = useState('');
  const [editGender, setEditGender] = useState('male');
  const [editSaving, setEditSaving] = useState(false);
  const [showEdit, setShowEdit] = useState(false);

  // Fetch clones on mount
  useEffect(() => {
    apiFetch<any[]>('/api/clones')
      .then(data => {
        setClones(data);
        if (data.length > 0) {
          setSelectedCloneId(data[0].id);
          setEditName(data[0].name);
          setEditVoiceId(data[0].elevenlabs_voice_id);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  // Fetch looks when selectedCloneId changes
  useEffect(() => {
    if (!selectedCloneId) { setLooks([]); return; }
    setLooksLoading(true);
    apiFetch<any[]>(`/api/clones/${selectedCloneId}/looks`)
      .then(setLooks)
      .catch(() => setLooks([]))
      .finally(() => setLooksLoading(false));
  }, [selectedCloneId]);

  // Auto-select base look for generation modal
  // Poll a pending look until its image_url is populated
  // eslint-disable-next-line react-hooks/exhaustive-deps
  function startPollingLook(lookId: string) {
    const interval = setInterval(async () => {
      try {
        const look = await apiFetch<any>(`/api/clones/looks/${lookId}`);
        if (look.image_url && look.image_url !== 'error' && look.image_url !== 'pending') {
          setLooks(prev => prev.map(l => l.id === lookId ? look : l));
          pendingLookIds.delete(lookId);
          clearInterval(interval);
        } else if (look.image_url === 'error') {
          setLooks(prev => prev.map(l => l.id === lookId ? { ...l, image_url: 'error' } : l));
          pendingLookIds.delete(lookId);
          clearInterval(interval);
        }
      } catch {
        // Ignore transient errors, keep polling
      }
    }, 5000);
    // Safety: stop polling after 6 minutes max
    setTimeout(() => { clearInterval(interval); pendingLookIds.delete(lookId); }, 360000);
  }

  useEffect(() => {
    if (looks.length > 0 && !genBaseLookId) {
      const baseLook = looks.find(l => l.is_base);
      setGenBaseLookId(baseLook ? baseLook.id : looks[0].id);
    }
    // Resume polling for any pending looks (e.g. user navigated away and came back)
    looks.forEach(look => {
      if ((!look.image_url || look.image_url === 'pending') && !pendingLookIds.has(look.id)) {
        pendingLookIds.add(look.id);
        startPollingLook(look.id);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [looks, genBaseLookId]);

  // Handle setup image file selection
  function handleSetupImagePick(file: File) {
    if (!file.type.startsWith('image/')) return;
    setSetupImageFile(file);
    setSetupImagePreview(URL.createObjectURL(file));
  }

  async function uploadImageFile(file: File, cloneId: string, label: string, isBase: boolean) {
    const cleanName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_');
    const fileName = `clone_look_${Date.now()}_${cleanName}`;
    const { signed_url, path } = await apiFetch<{ signed_url: string; path: string }>('/assets/signed-url', {
      method: 'POST',
      body: JSON.stringify({ bucket: 'clone-looks', file_name: fileName }),
    });
    const uploadRes = await fetch(signed_url, {
      method: 'PUT',
      body: file,
      headers: { 'Content-Type': file.type },
    });
    if (!uploadRes.ok) throw new Error('Upload failed');
    const imageUrl = `${SUPABASE_URL_CLONES}/storage/v1/object/public/clone-looks/${path}`;
    const newLook = await apiFetch<any>('/api/clones/looks', {
      method: 'POST',
      body: JSON.stringify({ clone_id: cloneId, label, image_url: imageUrl, is_base: isBase }),
    });
    return newLook;
  }

  async function handleSetupSave() {
    if (!setupVoiceId.trim()) { setSetupError('Please enter your ElevenLabs Voice ID.'); return; }
    if (!setupImageFile) { setSetupError('Please upload a reference photo of yourself.'); return; }
    setSetupSaving(true);
    setSetupError('');
    try {
      // 1. Create the clone
      const clone = await apiFetch<any>('/api/clones', {
        method: 'POST',
        body: JSON.stringify({ name: setupName, elevenlabs_voice_id: setupVoiceId, gender: setupGender }),
      });
      // 2. Upload the first look
      const label = setupImageFile.name.replace(/\.[^.]+$/, '') || 'Base Look';
      const firstLook = await uploadImageFile(setupImageFile, clone.id, label, true);
      setClones([clone]);
      setSelectedCloneId(clone.id);
      setEditName(clone.name);
      setEditVoiceId(clone.elevenlabs_voice_id);
      setEditGender(clone.gender || 'male');
      setLooks([firstLook]);
    } catch (err: any) {
      setSetupError(err.message || 'Failed to create clone');
    } finally {
      setSetupSaving(false);
    }
  }

  async function handleEditSave() {
    setEditSaving(true);
    try {
      const updated = await apiFetch<any>(`/api/clones/${selectedCloneId}`, {
        method: 'PATCH',
        body: JSON.stringify({ name: editName, elevenlabs_voice_id: editVoiceId, gender: editGender }),
      });
      setClones(prev => prev.map(c => c.id === selectedCloneId ? updated : c));
      setShowEdit(false);
    } catch (err: any) {
      alert(err.message || 'Failed to update clone');
    } finally {
      setEditSaving(false);
    }
  }

  async function handleUploadLook(file: File) {
    if (!file.type.startsWith('image/')) { alert('Please select an image file.'); return; }
    setUploading(true);
    try {
      const label = file.name.replace(/\.[^.]+$/, '') || 'Look';
      const newLook = await uploadImageFile(file, selectedCloneId, label, looks.length === 0);
      setLooks(prev => [...prev, newLook]);
    } catch (err: any) {
      alert(err.message || 'Upload failed');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleDeleteLook(lookId: string) {
    if (!confirm('Delete this look? This cannot be undone.')) return;
    try {
      await apiFetch(`/api/clones/looks/${lookId}`, { method: 'DELETE' });
      setLooks(prev => prev.filter(l => l.id !== lookId));
    } catch (err: any) {
      alert(err.message || 'Delete failed');
    }
  }

  async function handleGenerateLook() {
    if (!genPrompt.trim()) { setGenError('Please describe the outfit and background.'); return; }
    if (!genBaseLookId) { setGenError('Please select a base look to transform.'); return; }
    setGenerating(true);
    setGenError('');
    try {
      // Backend returns immediately with a pending look (image_url=null)
      const newLook = await apiFetch<any>('/api/clones/looks/generate', {
        method: 'POST',
        body: JSON.stringify({
          clone_id: selectedCloneId,
          base_look_id: genBaseLookId,
          prompt: genPrompt,
          label: genLabel.trim() || 'AI Generated Look',
        }),
      });
      // Add the pending look to the grid immediately
      setLooks(prev => [...prev, newLook]);
      // Close modal and reset form
      setGenPrompt('');
      setGenLabel('AI Generated Look');
      setShowGenModal(false);
      // Start polling for this look
      if (!newLook.image_url || newLook.image_url === 'pending' || newLook.image_url === 'error') {
        pendingLookIds.add(newLook.id);
        startPollingLook(newLook.id);
      }
    } catch (err: any) {
      setGenError(err.message || 'Generation failed');
    } finally {
      setGenerating(false);
    }
  }

  if (loading) {
    return <div className='empty-state'><div className='empty-title'>{t('common.loading')}</div></div>;
  }

  // ── No clone set up yet — includes image upload ───────────────────────────
  if (clones.length === 0) {
    return (
      <div style={{ maxWidth: '520px', margin: '40px auto', padding: '32px', background: 'var(--surface)', borderRadius: '16px', border: '1px solid var(--border-soft)' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-1)', marginBottom: '8px' }}>
          {t('clones.setupTitle')}
        </h2>
        <p style={{ fontSize: '13px', color: 'var(--text-3)', marginBottom: '24px' }}>
          {t('clones.setupDesc')}
        </p>

        {/* Reference Photo Upload */}
        <div style={{ marginBottom: '20px' }}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '8px' }}>{t('clones.referencePhoto')} *</label>
          <div
            onClick={() => setupFileRef.current?.click()}
            style={{
              width: '140px', aspectRatio: '9/16', borderRadius: '12px',
              border: setupImagePreview ? '2px solid var(--blue)' : '2px dashed var(--border-soft)',
              background: setupImagePreview ? 'transparent' : 'var(--surface-hover)',
              cursor: 'pointer', position: 'relative', overflow: 'hidden',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'border-color 0.2s',
            }}
          >
            {setupImagePreview ? (
              <img src={setupImagePreview} alt="Preview" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' }} />
            ) : (
              <div style={{ textAlign: 'center', padding: '12px' }}>
                <svg viewBox='0 0 24 24' style={{ width: '24px', height: '24px', stroke: 'var(--text-3)', fill: 'none', strokeWidth: 1.5, margin: '0 auto 8px' }}>
                  <rect x='3' y='3' width='18' height='18' rx='2' /><circle cx='8.5' cy='8.5' r='1.5' /><path d='M21 15l-5-5L5 21' />
                </svg>
                <div style={{ fontSize: '11px', color: 'var(--text-3)', lineHeight: 1.4 }}>{t('clones.clickUpload')}<br/>{t('clones.clearPortrait')}</div>
              </div>
            )}
          </div>
          <input ref={setupFileRef} type='file' accept='image/*' style={{ display: 'none' }}
            onChange={e => { const f = e.target.files?.[0]; if (f) handleSetupImagePick(f); }}
          />
          <p style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '6px', maxWidth: '200px' }}>
            {t('clones.photoTip')}
          </p>
        </div>

        <div style={{ marginBottom: '16px' }}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>{t('clones.cloneName')}</label>
          <input className='input-field' type='text' value={setupName} onChange={e => setSetupName(e.target.value)} placeholder={t('clones.cloneNamePlaceholder')} />
        </div>
        <div style={{ marginBottom: '16px' }}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>{t('clones.gender')} *</label>
          <div style={{ display: 'flex', gap: '8px' }}>
            {['male', 'female'].map(g => (
              <button key={g} onClick={() => setSetupGender(g)} style={{
                flex: 1, padding: '8px 0', borderRadius: '8px', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
                border: setupGender === g ? '2px solid var(--blue)' : '1px solid var(--border-soft)',
                background: setupGender === g ? 'rgba(59,130,246,0.1)' : 'var(--surface-hover)',
                color: setupGender === g ? 'var(--blue)' : 'var(--text-2)',
                transition: 'all 0.15s',
              }}>{g === 'male' ? t('clones.male') : t('clones.female')}</button>
            ))}
          </div>
        </div>
        <div style={{ marginBottom: '20px' }}>
          <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>{t('clones.voiceId')} *</label>
          <input className='input-field' type='text' value={setupVoiceId} onChange={e => setSetupVoiceId(e.target.value)} placeholder={t('clones.voiceIdPlaceholder')} />
          <p style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '4px' }}>
            {t('clones.voiceIdTip')}
          </p>
        </div>
        {setupError && (
          <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px', padding: '8px 12px', marginBottom: '16px', fontSize: '12px', color: 'var(--red)' }}>
            {setupError}
          </div>
        )}
        <button className='btn-primary' onClick={handleSetupSave} disabled={setupSaving} style={{ width: '100%' }}>
          {setupSaving ? t('clones.creating') : t('clones.createClone')}
        </button>
      </div>
    );
  }

  // ── Clone exists — show management UI ─────────────────────────────────────
  const currentClone = clones.find(c => c.id === selectedCloneId) || clones[0];

  return (
    <div>
      {/* ── Clone profile header ── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', padding: '16px 20px', background: 'var(--surface)', borderRadius: '12px', border: '1px solid var(--border-soft)' }}>
        <div>
          <div style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-1)' }}>{currentClone.name}</div>
          <div style={{ fontSize: '12px', color: 'var(--text-3)', marginTop: '2px' }}>
            Voice ID: <code style={{ fontSize: '11px', background: 'var(--surface-hover)', padding: '1px 6px', borderRadius: '4px' }}>{currentClone.elevenlabs_voice_id}</code>
          </div>
        </div>
        <button className='btn-secondary' onClick={() => setShowEdit(!showEdit)} style={{ fontSize: '12px' }}>
          {t('clones.editProfile')}
        </button>
      </div>

      {/* ── Edit form (collapsible) ── */}
      {showEdit && (
        <div style={{ marginBottom: '24px', padding: '16px 20px', background: 'var(--surface)', borderRadius: '12px', border: '1px solid var(--border-soft)' }}>
          <div style={{ marginBottom: '12px' }}>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>{t('clones.cloneName')}</label>
            <input className='input-field' type='text' value={editName} onChange={e => setEditName(e.target.value)} />
          </div>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>{t('clones.voiceId')}</label>
            <input className='input-field' type='text' value={editVoiceId} onChange={e => setEditVoiceId(e.target.value)} />
          </div>
          <div style={{ marginBottom: '12px' }}>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>{t('clones.gender')}</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              {['male', 'female'].map(g => (
                <button key={g} onClick={() => setEditGender(g)} style={{
                  flex: 1, padding: '8px 0', borderRadius: '8px', fontSize: '13px', fontWeight: 600, cursor: 'pointer',
                  border: editGender === g ? '2px solid var(--blue)' : '1px solid var(--border-soft)',
                  background: editGender === g ? 'rgba(59,130,246,0.1)' : 'var(--surface-hover)',
                  color: editGender === g ? 'var(--blue)' : 'var(--text-2)',
                  transition: 'all 0.15s',
                }}>{g === 'male' ? t('clones.male') : t('clones.female')}</button>
              ))}
            </div>
          </div>
          <div style={{ display: 'flex', gap: '8px' }}>
            <button className='btn-primary' onClick={handleEditSave} disabled={editSaving}>{editSaving ? t('clones.saving') : t('clones.saveChanges')}</button>
            <button className='btn-secondary' onClick={() => setShowEdit(false)}>{t('common.cancel')}</button>
          </div>
        </div>
      )}

      {/* ── Looks section — header with two action buttons ── */}
      <div style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <h3 style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-1)', margin: 0 }}>
            {t('clones.myLooks')} ({looks.length})
          </h3>
          <div style={{ display: 'flex', gap: '8px' }}>
            {/* Generate New Look CTA — opens modal */}
            {looks.length > 0 && (
              <button
                className='btn-secondary'
                onClick={() => { setGenError(''); setShowGenModal(true); }}
                style={{ fontSize: '12px' }}
              >
                <svg viewBox='0 0 24 24' style={{ width: '14px', height: '14px', stroke: 'currentColor', fill: 'none', strokeWidth: 2 }}>
                  <polygon points='13,2 3,14 12,14 11,22 21,10 12,10' />
                </svg>
                {t('clones.generateNewLook')}
              </button>
            )}
            {/* Upload Look CTA */}
            <button
              className='btn-create'
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              <svg viewBox='0 0 24 24'><line x1='12' y1='5' x2='12' y2='19' /><line x1='5' y1='12' x2='19' y2='12' /></svg>
              {uploading ? t('clones.uploading') : t('clones.uploadLook')}
            </button>
            <input
              ref={fileInputRef}
              type='file'
              accept='image/*'
              style={{ display: 'none' }}
              onChange={e => { const f = e.target.files?.[0]; if (f) handleUploadLook(f); }}
            />
          </div>
        </div>

        {/* ── Looks grid — big icard-style cards like AI Influencers ── */}
        {looksLoading ? (
          <div className='empty-state'><div className='empty-title'>{t('clones.loadingLooks')}</div></div>
        ) : looks.length === 0 ? (
          <div className='empty-state'>
            <div className='empty-icon'>
              <svg viewBox='0 0 24 24'><circle cx='12' cy='8' r='4' /><path d='M4 20c0-4 3.6-7 8-7s8 3 8 7' /></svg>
            </div>
            <div className='empty-title'>{t('clones.noLooks')}</div>
            <div className='empty-sub'>{t('clones.noLooksSub')}</div>
            <button className='btn-primary' onClick={() => fileInputRef.current?.click()}>{t('clones.uploadFirst')}</button>
          </div>
        ) : (
          <div className='influencers-grid'>
            {looks.map(look => {
              const isPending = !look.image_url || look.image_url === 'pending';
              const isFailed = look.image_url === 'error';
              const isReady = look.image_url && !isFailed && !isPending;

              return (
                <div key={look.id} className='icard' style={{ cursor: 'default', position: 'relative' }}>
                  {isPending ? (
                    /* ── Generating placeholder ── */
                    <div className='icard-thumb' style={{
                      background: 'linear-gradient(135deg, var(--surface-hover) 0%, var(--surface) 50%, var(--surface-hover) 100%)',
                      backgroundSize: '200% 200%',
                      animation: 'shimmer 2s ease-in-out infinite',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                      gap: '12px', position: 'relative',
                    }}>
                      <div style={{
                        width: '36px', height: '36px',
                        border: '3px solid var(--border-soft)',
                        borderTopColor: 'var(--blue)',
                        borderRadius: '50%',
                        animation: 'spin 1s linear infinite',
                      }} />
                      <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)' }}>{t('clones.generating')}</span>
                      <span style={{ fontSize: '10px', color: 'var(--text-3)', textAlign: 'center', maxWidth: '120px', lineHeight: 1.3 }}>
                        {t('clones.generatingTime')}
                      </span>
                      <span className='icard-name'>{look.label}</span>
                    </div>
                  ) : isFailed ? (
                    /* ── Failed state ── */
                    <div className='icard-thumb' style={{
                      background: 'var(--surface-hover)',
                      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                      gap: '8px', position: 'relative',
                    }}>
                      <svg viewBox='0 0 24 24' style={{ width: '32px', height: '32px', stroke: 'var(--red)', fill: 'none', strokeWidth: 1.5 }}>
                        <circle cx='12' cy='12' r='10' /><path d='M15 9l-6 6M9 9l6 6' />
                      </svg>
                      <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--red)' }}>{t('clones.generationFailed')}</span>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleDeleteLook(look.id); }}
                        style={{ fontSize: '11px', color: 'var(--text-3)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
                      >{t('clones.remove')}</button>
                      <span className='icard-name'>{look.label}</span>
                    </div>
                  ) : (
                    /* ── Ready state (normal) ── */
                    <div className='icard-thumb' style={{ backgroundImage: `url(${look.image_url})`, position: 'relative' }}>
                      <span className='icard-name'>{look.label}</span>
                      <button className="card-delete-btn" onClick={(e) => { e.stopPropagation(); handleDeleteLook(look.id); }} title="Delete look">
                        <svg viewBox="0 0 24 24"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                      </button>
                    </div>
                  )}
                  <div className='icard-info' style={{ paddingBottom: '0' }}>
                    <div className='icard-tags'>
                      {look.is_base && <span className='icard-tag'>{t('clones.base')}</span>}
                      {isPending && <span className='icard-tag' style={{ background: 'rgba(59,130,246,0.15)', color: 'var(--blue)' }}>{t('clones.generatingTag')}</span>}
                    </div>
                  </div>
                  {isReady && (
                    <div style={{ display: 'flex', borderTop: '1px solid var(--border-soft)', marginTop: '12px' }}>
                      <Link href={`/create?creator_mode=ai_clone`} style={{ flex: 1, padding: '12px', textAlign: 'center', fontSize: '13px', fontWeight: 600, color: 'var(--blue)', textDecoration: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }}>
                        <svg viewBox='0 0 24 24' style={{ width: '14px', height: '14px', fill: 'currentColor' }}><polygon points='5,3 19,12 5,21' /></svg>
                        {t('clones.useInVideo')}
                      </Link>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* ── AI Look Generation Modal ── */}
      {showGenModal && (
        <div style={{
          position: 'fixed', inset: 0, zIndex: 1000,
          background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '20px',
        }} onClick={e => { if (e.target === e.currentTarget && !generating) setShowGenModal(false); }}>
          <div style={{
            background: 'var(--bg)', borderRadius: '16px',
            border: '1px solid var(--border-soft)',
            padding: '28px', width: '100%', maxWidth: '480px',
            boxShadow: '0 20px 60px rgba(0,0,0,0.3)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-1)', margin: 0 }}>
                {t('clones.genModalTitle')}
              </h3>
              {!generating && (
                <button onClick={() => setShowGenModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '18px', color: 'var(--text-3)', padding: '4px' }}>✕</button>
              )}
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-3)', marginBottom: '16px' }}>
              {t('clones.genModalDesc')}
            </p>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>{t('clones.baseLook')}</label>
              <select
                className='input-field'
                value={genBaseLookId}
                onChange={e => setGenBaseLookId(e.target.value)}
                style={{ width: '100%' }}
              >
                {looks.map(l => (
                  <option key={l.id} value={l.id}>{l.label}{l.is_base ? ` ${t('clones.baseSuffix')}` : ''}</option>
                ))}
              </select>
            </div>

            <div style={{ marginBottom: '12px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>{t('clones.describeLook')}</label>
              <textarea
                className='input-field'
                rows={3}
                value={genPrompt}
                onChange={e => setGenPrompt(e.target.value)}
                placeholder={t('clones.describePlaceholder')}
                style={{ resize: 'vertical', fontSize: '13px' }}
              />
            </div>

            <div style={{ marginBottom: '16px' }}>
              <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>{t('clones.lookLabel')}</label>
              <input
                className='input-field'
                type='text'
                value={genLabel}
                onChange={e => setGenLabel(e.target.value)}
                placeholder={t('clones.lookLabelPlaceholder')}
              />
            </div>

            {genError && (
              <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px', padding: '8px 12px', marginBottom: '12px', fontSize: '12px', color: 'var(--red)' }}>
                {genError}
              </div>
            )}

            <button
              className='btn-primary'
              onClick={handleGenerateLook}
              disabled={generating || !genPrompt.trim() || !genBaseLookId}
              style={{ width: '100%' }}
            >
              {generating ? (
                <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                  <span style={{ width: '14px', height: '14px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%', animation: 'spin 1s linear infinite', display: 'inline-block' }} />
                  {t('clones.submitting')}
                </span>
              ) : t('clones.generateWithAi')}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}


export default function InfluencersPage() {
  const { t } = useTranslation();
  const [influencers, setInfluencers] = useState<Influencer[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [genderFilter, setGenderFilter] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Influencer | null>(null);
  const [activeTab, setActiveTab] = useState<'influencers' | 'ai_clones'>('influencers');

  const fetchInfluencers = useCallback(async () => {
    try {
      const data = await apiFetch<Influencer[]>('/influencers');
      setInfluencers(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchInfluencers(); }, [fetchInfluencers]);

  // Re-fetch when user switches projects
  useEffect(() => {
    const handler = () => { setLoading(true); fetchInfluencers(); };
    window.addEventListener('projectChanged', handler);
    return () => window.removeEventListener('projectChanged', handler);
  }, [fetchInfluencers]);

  async function handleDelete(id: string) {
    if (!confirm('Delete this influencer? This cannot be undone.')) return;
    try {
      await apiFetch(`/influencers/${id}`, { method: 'DELETE' });
      setInfluencers(prev => prev.filter(i => i.id !== id));
    } catch (err) { console.error('Delete error:', err); }
  }

  const filtered = influencers.filter(inf =>
    inf.name.toLowerCase().includes(search.toLowerCase()) &&
    (genderFilter === '' || inf.gender === genderFilter)
  );

  const { visibleItems: visibleInfluencers, sentinelRef, hasMore } = useProgressiveList(filtered, 16);

  return (
    <div className='content-area'>
      <div className='page-header'>
        <h1>{t('influencers.title')}</h1>
        <p>{t('influencers.subtitle')}</p>
      </div>

      {/* Tab bar — same style as products/page.tsx */}
      <div style={{ display: 'flex', gap: '0', marginBottom: '24px', borderBottom: '1px solid var(--border-soft)' }}>
        <button
          onClick={() => setActiveTab('influencers')}
          style={{
            padding: '10px 20px', fontSize: '13px', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer',
            borderBottom: activeTab === 'influencers' ? '2px solid var(--blue)' : '2px solid transparent',
            color: activeTab === 'influencers' ? 'var(--blue)' : 'var(--text-3)', transition: 'all 0.15s',
          }}
        >
          {t('influencers.influencersTab')}
        </button>
        <button
          onClick={() => setActiveTab('ai_clones')}
          style={{
            padding: '10px 20px', fontSize: '13px', fontWeight: 600, background: 'none', border: 'none', cursor: 'pointer',
            borderBottom: activeTab === 'ai_clones' ? '2px solid var(--blue)' : '2px solid transparent',
            color: activeTab === 'ai_clones' ? 'var(--blue)' : 'var(--text-3)', transition: 'all 0.15s',
          }}
        >
          {t('influencers.clonesTab')}
        </button>
      </div>

      {activeTab === 'influencers' && (
        <>
          <div className='asset-toolbar'>
            <div className='asset-toolbar-left'>
              <div className='search-box'>
                <svg viewBox='0 0 24 24'><circle cx='11' cy='11' r='8' /><line x1='21' y1='21' x2='16.65' y2='16.65' /></svg>
                <input type='text' placeholder={t('common.search') + '...'} value={search} onChange={e => setSearch(e.target.value)} />
              </div>
              <Select
                className='filter-select'
                value={genderFilter}
                onChange={setGenderFilter}
                options={[
                  { value: '', label: t('influencers.allTypes') },
                  { value: 'Female', label: t('influencers.female') },
                  { value: 'Male', label: t('influencers.male') }
                ]}
              />
            </div>
            <button className='btn-create' onClick={() => { setEditTarget(null); setModalOpen(true); }}>
              <svg viewBox='0 0 24 24'><line x1='12' y1='5' x2='12' y2='19' /><line x1='5' y1='12' x2='19' y2='12' /></svg>
              {t('influencers.create')}
            </button>
          </div>

          {loading ? (
            <div className='empty-state'><div className='empty-title'>{t('common.loading')}</div></div>
          ) : filtered.length === 0 ? (
            <div className='empty-state'>
              <div className='empty-icon'><svg viewBox='0 0 24 24'><circle cx='12' cy='8' r='4' /><path d='M4 20c0-4 3.6-7 8-7s8 3 8 7' /></svg></div>
              <div className='empty-title'>{t('influencers.noInfluencers')}</div>
              <div className='empty-sub'>{t('influencers.addFirst')}</div>
              <button className='btn-primary' onClick={() => { setEditTarget(null); setModalOpen(true); }}>{t('influencers.addInfluencer')}</button>
            </div>
          ) : (
            <>
            <div className='influencers-grid'>
              {visibleInfluencers.map(inf => (
                <div key={inf.id} className='icard' style={{ cursor: 'default' }}>
                  <div className='icard-thumb' style={inf.image_url ? { backgroundImage: `url(${inf.image_url})`, position: 'relative' } : { background: 'linear-gradient(160deg,#1a1a2e,#0f3460)', position: 'relative' }}>
                    <span className='icard-name'>{inf.name}</span>
                    <button className="card-delete-btn" onClick={(e) => { e.stopPropagation(); handleDelete(inf.id); }} title="Delete influencer">
                      <svg viewBox="0 0 24 24"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                    </button>
                  </div>
                  <div className='icard-info' style={{ paddingBottom: '0' }}>
                    <div className='icard-tags'>
                      {inf.gender && <span className='icard-tag'>{inf.gender}</span>}
                      {inf.style && <span className='icard-tag'>{inf.style}</span>}
                    </div>
                  </div>
                  <div style={{ display: 'flex', borderTop: '1px solid var(--border-soft)', marginTop: '12px' }}>
                    <Link href={`/create?influencer_id=${inf.id}`} style={{ flex: 1, padding: '12px', textAlign: 'center', fontSize: '13px', fontWeight: 600, color: 'var(--blue)', textDecoration: 'none', borderRight: '1px solid var(--border-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }} className='hover:bg-[rgba(51,122,255,0.05)] transition-colors'>
                      <svg viewBox='0 0 24 24' style={{ width: '14px', height: '14px', fill: 'currentColor' }}><polygon points='5,3 19,12 5,21' /></svg>
                      {t('influencers.useVideo')}
                    </Link>
                    <button onClick={() => { setEditTarget(inf); setModalOpen(true); }} style={{ flex: 1, padding: '12px', textAlign: 'center', fontSize: '13px', fontWeight: 600, color: 'var(--text-2)', textDecoration: 'none', border: 'none', background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }} className='hover:bg-[rgba(0,0,0,0.02)] transition-colors'>
                      <svg viewBox='0 0 24 24' style={{ width: '14px', height: '14px', stroke: 'currentColor', fill: 'none', strokeWidth: '2' }}><path d='M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z' /></svg>
                      {t('common.edit')}
                    </button>
                  </div>
                </div>
              ))}
            </div>
            {hasMore && <div ref={sentinelRef} style={{ height: '1px', marginTop: '8px' }} />}
            </>
          )}

          <InfluencerModal
            isOpen={modalOpen}
            onClose={() => setModalOpen(false)}
            initialData={editTarget}
            onSave={() => { fetchInfluencers(); setModalOpen(false); }}
          />
        </>
      )}

      {activeTab === 'ai_clones' && (
        <AiClonesTab />
      )}
    </div>
  );
}
