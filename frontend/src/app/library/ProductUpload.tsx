'use client';

import { useState, useRef } from 'react';
import { apiFetch } from '@/lib/utils';

// Standard file upload component that supports drag & drop and signed URL upload
export function ProductUpload({ onUploadSuccess }: { onUploadSuccess: () => void }) {
    const [uploading, setUploading] = useState(false);
    const [preview, setPreview] = useState<string | null>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);
    const [name, setName] = useState('');

    async function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];

            // Set preview
            const reader = new FileReader();
            reader.onload = (ev) => setPreview(ev.target?.result as string);
            reader.readAsDataURL(file);

            // Default name
            if (!name) {
                setName(file.name.split('.')[0]);
            }
        }
    }

    async function handleUpload() {
        if (!fileInputRef.current?.files?.[0]) return;

        try {
            setUploading(true);
            const file = fileInputRef.current.files[0];

            // 1. Upload file server-side (server normalizes format to PNG)
            const formData = new FormData();
            formData.append('file', file);
            const { public_url } = await apiFetch<{ public_url: string, path: string }>('/api/products/upload', {
                method: 'POST',
                body: formData,
            });

            // 2. Create database record
            console.log('Creating product in DB:', { name, image_url: public_url });
            try {
                const product = await apiFetch('/api/products', {
                    method: 'POST',
                    body: JSON.stringify({
                        name: name,
                        image_url: public_url
                    })
                });
                console.log('Product created:', product);
            } catch (dbErr) {
                console.error('DB Create Error:', dbErr);
                alert('Image uploaded but failed to save product to DB. Check console.');
                throw dbErr;
            }

            // Reset
            setPreview(null);
            setName('');
            if (fileInputRef.current) fileInputRef.current.value = '';
            onUploadSuccess();

        } catch (err) {
            console.error('Upload failed:', err);
            alert('Upload failed. See console.');
        } finally {
            setUploading(false);
        }
    }

    return (
        <div className="bg-white rounded-2xl shadow-sm border border-[#E8ECF4] p-6 space-y-4">
            <h3 className="text-lg font-semibold text-[#1A1A1F]">Add New Product</h3>

            <div className="flex flex-col gap-4">
                <div
                    className="border-2 border-dashed border-[#E8ECF4] rounded-xl p-8 text-center cursor-pointer hover:bg-[#F8FAFC] transition"
                    onClick={() => fileInputRef.current?.click()}
                >
                    {preview ? (
                        <div className="relative w-32 h-32 mx-auto">
                            <img src={preview} alt="Preview" className="w-full h-full object-cover rounded-lg" />
                            <button
                                onClick={(e) => { e.stopPropagation(); setPreview(null); }}
                                className="absolute -top-2 -right-2 bg-red-500 text-white rounded-full p-1 w-6 h-6 flex items-center justify-center text-xs"
                            >
                                ×
                            </button>
                        </div>
                    ) : (
                        <div className="text-[#4A5568]">
                            <span className="text-4xl block mb-2 text-[#94A3B8] flex justify-center">
                                <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" /></svg>
                            </span>
                            <span className="text-sm">Click to upload product image</span>
                        </div>
                    )}
                    <input
                        type="file"
                        ref={fileInputRef}
                        onChange={handleFileSelect}
                        className="hidden"
                        accept="image/*"
                    />
                </div>

                {preview && (
                    <div className="space-y-3">
                        <input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="Product Name"
                            className="input-field w-full"
                        />
                        <button
                            onClick={handleUpload}
                            disabled={uploading || !name.trim()}
                            className="btn-primary w-full"
                        >
                            {uploading ? 'Uploading...' : 'Save Product'}
                        </button>
                    </div>
                )}
            </div>
        </div>
    );
}
