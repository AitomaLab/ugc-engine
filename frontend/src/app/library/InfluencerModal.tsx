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
                setDescription(initialData.description || '');
                setStyle(initialData.style || '');
                setImageUrl(initialData.image_url || '');
                setVoiceId(initialData.elevenlabs_voice_id || '');
            } else {
                // Create mode: reset
                setName('');
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in duration-200">
            <div className="bg-slate-900 border border-slate-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl animate-in zoom-in-95 duration-200">

                {/* Header */}
                <div className="p-6 border-b border-white/5 flex justify-between items-center bg-white/5">
                    <h3 className="text-lg font-semibold text-white">
                        {initialData ? 'Edit Influencer' : 'Add New Influencer'}
                    </h3>
                    <button onClick={onClose} className="text-slate-400 hover:text-white transition">✕</button>
                </div>

                {/* Body */}
                <div className="p-6 space-y-5 max-h-[80vh] overflow-y-auto">

                    {/* Name */}
                    <div className="space-y-1">
                        <label className="text-xs font-medium text-slate-400">Name <span className="text-pink-500">*</span></label>
                        <input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            className="input-field w-full"
                            placeholder="e.g. Sofia"
                        />
                    </div>

                    {/* Category (Style) */}
                    <div className="space-y-1">
                        <label className="text-xs font-medium text-slate-400">Category</label>
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
                    <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-400">Profile Image</label>

                        <div className="flex items-center gap-4">
                            {/* Preview */}
                            <div className="w-20 h-20 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center overflow-hidden shrink-0 relative group">
                                {imageUrl ? (
                                    <img src={imageUrl} alt="Preview" className="w-full h-full object-cover" />
                                ) : (
                                    <span className="text-2xl text-slate-600">👤</span>
                                )}
                                {uploading && (
                                    <div className="absolute inset-0 bg-black/60 flex items-center justify-center">
                                        <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                                    </div>
                                )}
                            </div>

                            {/* Controls */}
                            <div className="flex-1 space-y-2">
                                <input
                                    type="file"
                                    ref={fileInputRef}
                                    onChange={handleFileSelect}
                                    className="hidden"
                                    accept="image/*"
                                />
                                <div className="flex gap-2">
                                    <button
                                        onClick={() => fileInputRef.current?.click()}
                                        disabled={uploading}
                                        className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs rounded-lg transition border border-slate-700"
                                    >
                                        {uploading ? 'Uploading...' : 'Upload Image'}
                                    </button>
                                    {imageUrl && (
                                        <button
                                            onClick={() => setImageUrl('')}
                                            className="px-3 py-1.5 text-red-400 hover:bg-red-500/10 text-xs rounded-lg transition"
                                        >
                                            Remove
                                        </button>
                                    )}
                                </div>
                                <input
                                    value={imageUrl}
                                    onChange={(e) => setImageUrl(e.target.value)}
                                    placeholder="Or paste image URL..."
                                    className="input-field w-full text-xs py-1.5"
                                />
                            </div>
                        </div>
                    </div>

                    {/* Description */}
                    <div className="space-y-1">
                        <label className="text-xs font-medium text-slate-400">Description</label>
                        <textarea
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            className="input-field w-full h-20 resize-none"
                            placeholder="Brief bio or visual description..."
                        />
                    </div>

                    {/* Voice ID */}
                    <div className="space-y-1">
                        <label className="text-xs font-medium text-slate-400">ElevenLabs Voice ID</label>
                        <input
                            value={voiceId}
                            onChange={(e) => setVoiceId(e.target.value)}
                            className="input-field w-full font-mono text-xs"
                            placeholder="e.g. hpp4J3VqNfWAUOO0d1Us"
                        />
                    </div>
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/5 bg-slate-900/50 flex justify-end gap-3">
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
