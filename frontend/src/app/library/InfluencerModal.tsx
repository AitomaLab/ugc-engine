'use client';

import { useState, useEffect, useRef } from 'react';
import { Influencer } from '@/lib/types';
import { apiFetch } from '@/lib/utils';

// Supabase URL for constructing public image URLs
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL || '';

interface InfluencerModalProps {
    isOpen: boolean;
    onClose: () => void;
    initialData: Influencer | null;
    onSave: () => void;
}

const PRESET_CATEGORIES = ['Travel', 'Fashion', 'Tech', 'Fitness', 'Food', 'General'];

export function InfluencerModal({ isOpen, onClose, initialData, onSave }: InfluencerModalProps) {
    const [name, setName] = useState('');
    const [gender, setGender] = useState('Female');
    const [description, setDescription] = useState('');
    const [style, setStyle] = useState(''); // Category
    const [imageUrl, setImageUrl] = useState('');
    const [voiceId, setVoiceId] = useState('');

    const [uploading, setUploading] = useState(false);
    const [saving, setSaving] = useState(false);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // Reset or populate form when opening/changing data
    useEffect(() => {
        if (isOpen) {
            if (initialData) {
                setName(initialData.name);
                setGender(initialData.gender || 'Female');
                setDescription(initialData.description || '');
                setStyle(initialData.style || '');
                setImageUrl(initialData.image_url || '');
                setVoiceId(initialData.elevenlabs_voice_id || '');
            } else {
                // Create mode: reset
                setName('');
                setGender('Female');
                setDescription('');
                setStyle('');
                setImageUrl('');
                setVoiceId('');
            }
        }
    }, [isOpen, initialData]);

    if (!isOpen) return null;

    async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
        if (!e.target.files || e.target.files.length === 0) return;
        const file = e.target.files[0];

        // Validation
        if (!file.type.startsWith('image/')) {
            alert('Please upload an image file');
            return;
        }
        if (file.size > 5 * 1024 * 1024) { // 5MB limit
            alert('Image must be under 5MB');
            return;
        }

        try {
            setUploading(true);

            // 1. Get signed URL from backend
            const cleanName = file.name.replace(/[^a-zA-Z0-9.-]/g, '_');
            const fileName = `inf_${Date.now()}_${cleanName}`;

            const { signed_url, path } = await apiFetch<{ signed_url: string, path: string }>('/assets/signed-url', {
                method: 'POST',
                body: JSON.stringify({ bucket: 'influencer-images', file_name: fileName }),
            });

            // 2. Upload to Supabase Storage directly
            const uploadRes = await fetch(signed_url, {
                method: 'PUT',
                body: file,
                headers: { 'Content-Type': file.type },
            });

            if (!uploadRes.ok) throw new Error('Upload failed');

            // 3. Construct Public URL
            const publicUrl = `${SUPABASE_URL}/storage/v1/object/public/influencer-images/${path}`;
            setImageUrl(publicUrl);
        } catch (err) {
            console.error('Upload Error:', err);
            alert('Failed to upload image. Please try again.');
        } finally {
            setUploading(false);
            // Reset input so same file can be selected again if needed
            if (fileInputRef.current) fileInputRef.current.value = '';
        }
    }

    async function handleSave() {
        if (!name.trim()) return;

        try {
            setSaving(true);
            const payload = {
                name,
                gender,
                description,
                style, // Category
                image_url: imageUrl,
                elevenlabs_voice_id: voiceId,
            };

            if (initialData) {
                // Update
                await apiFetch(`/influencers/${initialData.id}`, {
                    method: 'PUT',
                    body: JSON.stringify(payload),
                });
            } else {
                // Create
                await apiFetch('/influencers', {
                    method: 'POST',
                    body: JSON.stringify(payload),
                });
            }

            onSave();
            onClose();
        } catch (err) {
            console.error('Save Error:', err);
            alert('Failed to save influencer.');
        } finally {
            setSaving(false);
        }
    }

    return (
        <div className="modal-overlay">
            <div className="modal-box">

                {/* Header */}
                <div className="modal-header">
                    <h3 className="">
                        {initialData ? 'Edit Influencer' : 'Add New Influencer'}
                    </h3>
                    <button onClick={onClose} className="modal-close">
                        <svg viewBox="0 0 24 24"><path d="M18 6L6 18M6 6l12 12" /></svg>
                    </button>
                </div>

                {/* Body */}
                <div className="modal-body space-y-5">

                    {/* Name */}
                    <div className="space-y-1">
                        <label className="form-label">Name <span className="required">*</span></label>
                        <input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="input-field w-full"
                            placeholder="e.g. Sofia"
                        />
                    </div>

                    {/* Gender */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <label className="form-label" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase' }}>Sex <span className="required" style={{ color: 'var(--red)' }}>*</span></label>
                        <div style={{ display: 'flex', gap: '8px' }}>
                            {['Male', 'Female'].map(g => (
                                <button
                                    key={g}
                                    type="button"
                                    onClick={() => setGender(g)}
                                    style={{
                                        flex: 1, padding: '8px 16px', borderRadius: 'var(--radius-sm)', fontSize: '13px', fontWeight: 500, transition: 'all 0.15s',
                                        border: `1px solid ${gender === g ? 'var(--blue)' : 'var(--border)'}`,
                                        background: gender === g ? 'var(--blue)' : 'var(--surface)',
                                        color: gender === g ? 'white' : 'var(--text-2)'
                                    }}
                                >
                                    {g}
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Category (Style) */}
                    <div className="space-y-1">
                        <label className="form-label">Category</label>
                        <div className="relative">
                            <input
                                value={style}
                                onChange={(e) => setStyle(e.target.value)}
                                list="categories-list"
                                className="input-field w-full"
                                placeholder="Select or type category..."
                            />
                            <datalist id="categories-list">
                                {PRESET_CATEGORIES.map(c => <option key={c} value={c} />)}
                            </datalist>
                        </div>
                    </div>

                    {/* Image Upload */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                        <label className="form-label" style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-3)', textTransform: 'uppercase' }}>Profile Image</label>

                        <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                            {/* Preview */}
                            <div style={{ width: '80px', height: '80px', borderRadius: '50%', backgroundColor: 'var(--surface-hover)', border: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden', position: 'relative', flexShrink: 0 }}>
                                {imageUrl ? (
                                    <img src={imageUrl} alt="Preview" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                ) : (
                                    <span style={{ color: 'var(--text-3)' }}>
                                        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" /></svg>
                                    </span>
                                )}
                                {uploading && (
                                    <div style={{ position: 'absolute', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                        <div style={{ width: '20px', height: '20px', border: '2px solid rgba(255,255,255,0.3)', borderTopColor: 'white', borderRadius: '50%', animation: 'spin 1s linear infinite' }}></div>
                                    </div>
                                )}
                            </div>

                            {/* Controls */}
                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    onChange={handleFileSelect}
                                    style={{ display: 'none' }}
                                    accept="image/*"
                                />
                                <div style={{ display: 'flex', gap: '8px' }}>
                                    <button
                                        onClick={() => fileInputRef.current?.click()}
                                        disabled={uploading}
                                        style={{ padding: '6px 12px', fontSize: '12px', fontWeight: 600, borderRadius: 'var(--radius-sm)', border: '1px solid var(--border)', background: 'var(--surface)', color: 'var(--text-2)', cursor: 'pointer' }}
                                    >
                                        {uploading ? 'Uploading...' : 'Upload Image'}
                                    </button>
                                    {imageUrl && (
                                        <button
                                            onClick={() => setImageUrl('')}
                                            style={{ padding: '6px 12px', fontSize: '12px', fontWeight: 600, borderRadius: 'var(--radius-sm)', border: 'none', background: 'rgba(239, 68, 68, 0.1)', color: 'var(--red)', cursor: 'pointer' }}
                                        >
                                            Remove
                                        </button>
                                    )}
                                </div>
                                <input
                                    value={imageUrl}
                                    onChange={(e) => setImageUrl(e.target.value)}
                                    placeholder="Or paste image URL..."
                                    className="input-field w-full"
                                    style={{ fontSize: '12px', padding: '6px 10px', width: '100%' }}
                                />
                            </div>
                        </div>
                    </div>

                    {/* Description */}
                    <div className="space-y-1">
                        <label className="form-label">Description</label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            className="input-field w-full h-20 resize-none"
                            placeholder="Brief bio or visual description..."
                        />
                    </div>

                    {/* Voice ID */}
                    <div className="space-y-1">
                        <label className="form-label">ElevenLabs Voice ID</label>
                        <input
                            value={voiceId}
                            onChange={(e) => setVoiceId(e.target.value)}
                            className="input-field w-full font-mono text-xs"
                            placeholder="e.g. hpp4J3VqNfWAUOO0d1Us"
                        />
                    </div>
                </div>

                {/* Footer */}
                <div className="modal-footer">
                    <button onClick={onClose} className="btn-secondary">Cancel</button>
                    <button
                        onClick={handleSave}
                        disabled={saving || !name.trim()}
                        className="btn-primary"
                    >
                        {saving ? 'Saving...' : (initialData ? 'Save Changes' : 'Create Influencer')}
                    </button>
                </div>
            </div>
        </div>
    );
}
