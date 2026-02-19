'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch, formatDate, getApiUrl } from '@/lib/utils';
import { Influencer, Script, AppClipItem, VideoJob } from '@/lib/types';
import { InfluencerModal } from './InfluencerModal';
import { ProductUpload } from './ProductUpload';

type Tab = 'videos' | 'influencers' | 'scripts' | 'clips' | 'products';

// ---------------------------------------------------------------------------
// Main Library Page
// ---------------------------------------------------------------------------

export default function LibraryPage() {
    const [tab, setTab] = useState<Tab>('videos');
    const [searchQuery, setSearchQuery] = useState('');

    const tabs: { key: Tab; label: string; icon: string }[] = [
        { key: 'videos', label: 'Videos', icon: '🎬' },
        { key: 'influencers', label: 'Influencers', icon: '👤' },
        { key: 'scripts', label: 'Scripts', icon: '📝' },
        { key: 'clips', label: 'App Clips', icon: '📱' },
        { key: 'products', label: 'Products', icon: '📦' },
    ];

    return (
        <div className="space-y-8 animate-slide-up">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                    <h2 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-slate-400">
                        Asset Library
                    </h2>
                    <p className="text-slate-400 mt-1">Manage your video assets, influencers, and scripts.</p>
                </div>

                <div className="relative max-w-md w-full md:w-auto">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">🔍</span>
                    <input
                        type="text"
                        placeholder="Search assets..."
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="input-field pl-9 w-full"
                    />
                </div>
            </div>

            {/* Tabs */}
            <div className="flex overflow-x-auto gap-2 pb-2 scrollbar-none border-b border-white/5">
                {tabs.map((t) => (
                    <button
                        key={t.key}
                        onClick={() => setTab(t.key)}
                        className={`
                            flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all whitespace-nowrap
                            ${tab === t.key
                                ? 'bg-primary-500 text-white shadow-lg shadow-primary-500/20'
                                : 'text-slate-400 hover:text-white hover:bg-white/5'
                            }
                        `}
                    >
                        <span>{t.icon}</span>
                        {t.label}
                    </button>
                ))}
            </div>

            {/* ... */}

            {/* Tab Content */}
            {tab === 'videos' && <VideosTab searchQuery={searchQuery} />}
            {tab === 'influencers' && <InfluencersTab searchQuery={searchQuery} />}
            {tab === 'scripts' && <ScriptsTab searchQuery={searchQuery} />}
            {tab === 'clips' && <ClipsTab searchQuery={searchQuery} />}
            {tab === 'products' && <ProductsTab searchQuery={searchQuery} />}
        </div>
    );
}

// ===========================================================================
// Videos Tab
// ===========================================================================

function VideosTab({ searchQuery }: { searchQuery: string }) {
    const [jobs, setJobs] = useState<VideoJob[]>([]);
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [loading, setLoading] = useState(true);
    const [selectedVideo, setSelectedVideo] = useState<VideoJob | null>(null);
    const [sortBy, setSortBy] = useState<'newest' | 'oldest'>('newest');
    const [filterInfluencer, setFilterInfluencer] = useState('all');

    const fetchData = useCallback(async () => {
        try {
            const [jobsData, infData] = await Promise.all([
                apiFetch<VideoJob[]>('/jobs?limit=200'),
                apiFetch<Influencer[]>('/influencers'),
            ]);
            setJobs(jobsData);
            setInfluencers(infData);
        } catch (err) {
            console.error('Videos tab fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    const influencerMap = new Map(influencers.map((i) => [i.id, i]));

    // Filter completed videos
    let videos = jobs.filter((j) => j.status === 'success' && j.final_video_url);

    // Search
    if (searchQuery) {
        const q = searchQuery.toLowerCase();
        videos = videos.filter((v) => {
            const inf = influencerMap.get(v.influencer_id || '');
            return (
                inf?.name?.toLowerCase().includes(q) ||
                v.campaign_name?.toLowerCase().includes(q) ||
                v.model_api?.toLowerCase().includes(q) ||
                v.id.toLowerCase().includes(q)
            );
        });
    }

    // Filter by influencer
    if (filterInfluencer !== 'all') {
        videos = videos.filter((v) => v.influencer_id === filterInfluencer);
    }

    // Sort
    videos.sort((a, b) => {
        const da = new Date(a.created_at || 0).getTime();
        const db = new Date(b.created_at || 0).getTime();
        return sortBy === 'newest' ? db - da : da - db;
    });

    if (loading) return <div className="text-slate-500 text-sm italic animate-pulse py-12 text-center">Loading videos...</div>;

    return (
        <div className="space-y-4">
            {/* Filters */}
            <div className="flex items-center gap-3 flex-wrap">
                <select
                    value={filterInfluencer}
                    onChange={(e) => setFilterInfluencer(e.target.value)}
                    className="input-field w-auto text-xs"
                >
                    <option value="all">All Influencers</option>
                    {influencers.map((inf) => (
                        <option key={inf.id} value={inf.id}>{inf.name}</option>
                    ))}
                </select>
                <select
                    value={sortBy}
                    onChange={(e) => setSortBy(e.target.value as 'newest' | 'oldest')}
                    className="input-field w-auto text-xs"
                >
                    <option value="newest">Newest first</option>
                    <option value="oldest">Oldest first</option>
                </select>
                <span className="text-xs text-slate-500 ml-auto">{videos.length} video{videos.length !== 1 ? 's' : ''}</span>
            </div>

            {/* Video Grid */}
            {videos.length === 0 ? (
                <div className="text-center py-20 text-slate-500 text-sm italic">
                    No videos yet. Go to <a href="/create" className="text-blue-400 underline">Create</a> to generate your first video!
                </div>
            ) : (
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 video-grid">
                    {videos.map((video) => {
                        const inf = influencerMap.get(video.influencer_id || '');
                        return (
                            <div
                                key={video.id}
                                className="video-card cursor-pointer"
                                onClick={() => setSelectedVideo(video)}
                            >
                                <div className="relative aspect-[9/16] bg-slate-800/50 overflow-hidden">
                                    <video
                                        src={video.final_video_url}
                                        muted
                                        loop
                                        playsInline
                                        preload="metadata"
                                        className="w-full h-full object-cover"
                                        onMouseEnter={(e) => (e.target as HTMLVideoElement).play().catch(() => { })}
                                        onMouseLeave={(e) => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0; }}
                                    />
                                    <div className="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded-md font-medium">
                                        15s
                                    </div>
                                </div>
                                <div className="p-3">
                                    <p className="text-xs font-medium text-slate-200 truncate">{inf?.name ?? 'Video'}</p>
                                    <p className="text-[10px] text-slate-500 mt-0.5">{new Date(video.created_at || '').toLocaleDateString()}</p>
                                </div>
                            </div>
                        );
                    })}
                </div>
            )}

            {/* Video Detail Modal */}
            {selectedVideo && (
                <VideoDetailModal
                    video={selectedVideo}
                    influencer={influencerMap.get(selectedVideo.influencer_id || '')}
                    onClose={() => setSelectedVideo(null)}
                />
            )}
        </div>
    );
}

// ===========================================================================
// Video Detail Modal
// ===========================================================================

function VideoDetailModal({
    video,
    influencer,
    onClose,
}: {
    video: VideoJob;
    influencer?: Influencer;
    onClose: () => void;
}) {
    const [copied, setCopied] = useState(false);

    useEffect(() => {
        function handleEsc(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
        window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [onClose]);

    function copyUrl() {
        if (video.final_video_url) {
            navigator.clipboard.writeText(video.final_video_url);
            setCopied(true);
            setTimeout(() => setCopied(false), 2000);
        }
    }

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content p-0" onClick={(e) => e.stopPropagation()}>
                {/* Player */}
                <div className="relative bg-black rounded-t-[20px] overflow-hidden">
                    <video
                        src={video.final_video_url}
                        controls
                        autoPlay
                        className="w-full max-h-[50vh] mx-auto"
                    />
                    <button
                        onClick={onClose}
                        className="absolute top-3 right-3 w-8 h-8 rounded-full bg-black/60 text-white flex items-center justify-center hover:bg-black/80 transition-colors"
                    >
                        ✕
                    </button>
                </div>

                {/* Info */}
                <div className="p-6 space-y-5">
                    <div className="flex items-center justify-between">
                        <div>
                            <h3 className="font-semibold text-lg text-slate-100">
                                {influencer?.name ?? 'Untitled Video'}
                            </h3>
                            <p className="text-xs text-slate-500 mt-0.5">
                                {formatDate(video.created_at)}
                            </p>
                        </div>
                        <div className="flex gap-2">
                            <a
                                href={video.final_video_url}
                                download
                                target="_blank"
                                rel="noopener noreferrer"
                                className="btn-primary text-xs px-4 py-2"
                            >
                                ⬇ Download
                            </a>
                            <button onClick={copyUrl} className="btn-secondary text-xs px-4 py-2">
                                {copied ? '✓ Copied!' : '🔗 Share'}
                            </button>
                        </div>
                    </div>

                    {/* Metadata */}
                    <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                            <p className="text-[10px] uppercase text-slate-500 font-semibold mb-1">Influencer</p>
                            <p className="text-slate-300">{influencer?.name ?? '—'}</p>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase text-slate-500 font-semibold mb-1">AI Model</p>
                            <p className="text-slate-300">{video.model_api ?? '—'}</p>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase text-slate-500 font-semibold mb-1">Campaign</p>
                            <p className="text-slate-300">{video.campaign_name ?? 'Single Generation'}</p>
                        </div>
                        <div>
                            <p className="text-[10px] uppercase text-slate-500 font-semibold mb-1">Job ID</p>
                            <p className="text-slate-300 font-mono text-xs">{video.id.substring(0, 12)}...</p>
                        </div>
                    </div>

                    {/* Schedule Placeholder */}
                    <button className="btn-secondary w-full opacity-50 cursor-not-allowed" disabled>
                        📅 Schedule to Social Media (Coming Soon)
                    </button>
                </div>
            </div>
        </div>
    );
}

// ===========================================================================
// Influencers Tab
// ===========================================================================

function InfluencersTab({ searchQuery }: { searchQuery: string }) {
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [loading, setLoading] = useState(true);
    const [isModalOpen, setIsModalOpen] = useState(false);
    const [editingInfluencer, setEditingInfluencer] = useState<Influencer | null>(null);

    const fetchData = useCallback(async () => {
        try {
            const data = await apiFetch<Influencer[]>('/influencers');
            setInfluencers(data);
        } catch (err) {
            console.error('Influencers fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    function openCreateModal() {
        setEditingInfluencer(null);
        setIsModalOpen(true);
    }

    function openEditModal(inf: Influencer) {
        setEditingInfluencer(inf);
        setIsModalOpen(true);
    }

    async function handleDelete(id: string) {
        if (!confirm('Delete this influencer?')) return;
        try {
            await apiFetch(`/influencers/${id}`, { method: 'DELETE' });
            fetchData();
        } catch (err) { console.error(err); }
    }

    let filtered = influencers;
    if (searchQuery) {
        const q = searchQuery.toLowerCase();
        filtered = influencers.filter((i) =>
            i.name.toLowerCase().includes(q) || i.description?.toLowerCase().includes(q) || i.style?.toLowerCase().includes(q)
        );
    }

    if (loading) return <div className="text-slate-500 text-sm italic animate-pulse py-12 text-center">Loading influencers...</div>;

    return (
        <div className="space-y-6">
            <div className="flex justify-between items-center">
                <p className="text-slate-400 text-sm">Manage your AI influencers.</p>
                <button onClick={openCreateModal} className="btn-primary px-4 py-2">
                    + Add Influencer
                </button>
            </div>

            {filtered.length === 0 ? (
                <div className="text-center py-20 text-slate-500 text-sm italic bg-slate-900/30 rounded-2xl border border-white/5">
                    No influencers found. Create one to get started!
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                    {filtered.map((inf) => (
                        <div key={inf.id} className="glass-panel-light p-4 flex flex-col gap-3 group relative hover:bg-white/5 transition-colors">
                            <div className="flex items-start gap-4">
                                <div className="w-14 h-14 rounded-xl bg-slate-800 border border-white/10 overflow-hidden flex-shrink-0">
                                    {inf.image_url ? (
                                        <img src={inf.image_url} alt={inf.name} className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-2xl">👤</div>
                                    )}
                                </div>
                                <div className="min-w-0 flex-1">
                                    <div className="flex justify-between items-start">
                                        <h4 className="font-semibold text-slate-200 truncate">{inf.name}</h4>
                                        {inf.style && (
                                            <span className="text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-full border border-blue-500/20">
                                                {inf.style}
                                            </span>
                                        )}
                                    </div>
                                    <p className="text-xs text-slate-500 line-clamp-2 mt-1 leading-relaxed">
                                        {inf.description || 'No description'}
                                    </p>
                                </div>
                            </div>

                            <div className="flex justify-end gap-2 mt-auto pt-2 border-t border-white/5">
                                <button
                                    onClick={() => openEditModal(inf)}
                                    className="text-xs text-slate-400 hover:text-white px-3 py-1.5 rounded-lg hover:bg-white/5 transition"
                                >
                                    Edit
                                </button>
                                <button
                                    onClick={() => handleDelete(inf.id)}
                                    className="text-xs text-red-400 hover:text-red-300 px-3 py-1.5 rounded-lg hover:bg-red-500/10 transition"
                                >
                                    Delete
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            <InfluencerModal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                initialData={editingInfluencer}
                onSave={fetchData}
            />
        </div>
    );
}

// ===========================================================================
// Scripts Tab
// ===========================================================================

function ScriptsTab({ searchQuery }: { searchQuery: string }) {
    const [scripts, setScripts] = useState<Script[]>([]);
    const [loading, setLoading] = useState(true);
    const [text, setText] = useState('');
    const [category, setCategory] = useState('');
    const API_URL = getApiUrl();

    const fetchData = useCallback(async () => {
        try {
            const data = await apiFetch<Script[]>('/scripts');
            setScripts(data);
        } catch (err) {
            console.error('Scripts fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    async function handleCreate() {
        if (!text.trim()) return;
        try {
            await apiFetch('/scripts', {
                method: 'POST',
                body: JSON.stringify({ text, category: category || undefined }),
            });
            setText(''); setCategory('');
            fetchData();
        } catch (err) { console.error(err); }
    }

    async function handleDelete(id: string) {
        if (!confirm('Delete this script?')) return;
        try {
            await apiFetch(`/scripts/${id}`, { method: 'DELETE' });
            fetchData();
        } catch (err) { console.error(err); }
    }

    async function handleGenerateAI() {
        try {
            const res = await fetch(`${API_URL}/ai/hook`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ category: category || 'General' }),
            });
            if (res.ok) {
                const data = await res.json();
                setText(data.hook || '');
            }
        } catch { /* silent */ }
    }

    let filtered = scripts;
    if (searchQuery) {
        const q = searchQuery.toLowerCase();
        filtered = scripts.filter((s) =>
            s.text.toLowerCase().includes(q) || s.category?.toLowerCase().includes(q)
        );
    }

    if (loading) return <div className="text-slate-500 text-sm italic animate-pulse py-12 text-center">Loading scripts...</div>;

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Create Form */}
            <div className="glass-panel p-6 space-y-4 h-fit">
                <h4 className="font-semibold text-sm text-slate-200">Add Script</h4>
                <textarea
                    value={text}
                    onChange={(e) => setText(e.target.value)}
                    placeholder="Enter script text..."
                    rows={5}
                    className="input-field resize-none"
                />
                <input
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    placeholder="Category (e.g., Travel, Fashion)"
                    className="input-field"
                />
                <div className="flex gap-2">
                    <button onClick={handleCreate} className="btn-primary flex-1" disabled={!text.trim()}>Add Script</button>
                    <button onClick={handleGenerateAI} className="btn-secondary text-xs">✨ AI Generate</button>
                </div>
            </div>

            {/* List */}
            <div className="lg:col-span-2 space-y-3">
                {filtered.length === 0 ? (
                    <p className="text-slate-500 text-sm italic text-center py-12">No scripts found.</p>
                ) : (
                    filtered.map((script) => (
                        <div key={script.id} className="glass-panel-light p-4">
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex-1 min-w-0">
                                    <p className="text-sm text-slate-300 leading-relaxed">
                                        {script.text.substring(0, 120)}{script.text.length > 120 ? '...' : ''}
                                    </p>
                                    {script.category && (
                                        <span className="inline-block mt-2 text-[10px] bg-blue-500/10 text-blue-400 px-2 py-0.5 rounded-md font-medium">
                                            {script.category}
                                        </span>
                                    )}
                                </div>
                                <button onClick={() => handleDelete(script.id)} className="btn-danger flex-shrink-0">Delete</button>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}

// ===========================================================================
// App Clips Tab
// ===========================================================================

function ClipsTab({ searchQuery }: { searchQuery: string }) {
    const [clips, setClips] = useState<AppClipItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [name, setName] = useState('');
    const [videoUrl, setVideoUrl] = useState('');
    const [description, setDescription] = useState('');

    const fetchData = useCallback(async () => {
        try {
            const data = await apiFetch<AppClipItem[]>('/app-clips');
            setClips(data);
        } catch (err) {
            console.error('Clips fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    async function handleCreate() {
        if (!name.trim() || !videoUrl.trim()) return;
        try {
            await apiFetch('/app-clips', {
                method: 'POST',
                body: JSON.stringify({ name, video_url: videoUrl, description }),
            });
            setName(''); setVideoUrl(''); setDescription('');
            fetchData();
        } catch (err) { console.error(err); }
    }

    async function handleDelete(id: string) {
        if (!confirm('Delete this app clip?')) return;
        try {
            await apiFetch(`/app-clips/${id}`, { method: 'DELETE' });
            fetchData();
        } catch (err) { console.error(err); }
    }

    let filtered = clips;
    if (searchQuery) {
        const q = searchQuery.toLowerCase();
        filtered = clips.filter((c) =>
            c.name.toLowerCase().includes(q) || c.description?.toLowerCase().includes(q)
        );
    }

    if (loading) return <div className="text-slate-500 text-sm italic animate-pulse py-12 text-center">Loading clips...</div>;

    return (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Create Form */}
            <div className="glass-panel p-6 space-y-4 h-fit">
                <h4 className="font-semibold text-sm text-slate-200">Add App Clip</h4>
                <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Clip Name" className="input-field" />
                <input value={videoUrl} onChange={(e) => setVideoUrl(e.target.value)} placeholder="Video URL (mp4)" className="input-field" />
                <input value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" className="input-field" />
                <button onClick={handleCreate} className="btn-primary w-full" disabled={!name.trim() || !videoUrl.trim()}>Add Clip</button>
            </div>

            {/* List */}
            <div className="lg:col-span-2 space-y-3">
                {filtered.length === 0 ? (
                    <p className="text-slate-500 text-sm italic text-center py-12">No app clips found.</p>
                ) : (
                    filtered.map((clip) => (
                        <div key={clip.id} className="glass-panel-light p-4 flex items-center gap-4">
                            <div className="w-16 h-10 rounded-lg bg-slate-800/50 overflow-hidden flex-shrink-0">
                                <video src={clip.video_url} muted className="w-full h-full object-cover" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="font-medium text-sm text-slate-200">{clip.name}</p>
                                {clip.description && <p className="text-xs text-slate-500 truncate">{clip.description}</p>}
                            </div>
                            <button onClick={() => handleDelete(clip.id)} className="btn-danger">Delete</button>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
// ===========================================================================
// Products Tab
// ===========================================================================

interface Product {
    id: string;
    name: string;
    description?: string;
    category?: string;
    image_url: string;
    visual_description?: {
        brand_name?: string;
        visual_description?: string;
        color_scheme?: { hex: string; name: string }[];
        font_style?: string;
    };
}

function ProductsTab({ searchQuery }: { searchQuery: string }) {
    const [products, setProducts] = useState<Product[]>([]);
    const [loading, setLoading] = useState(true);
    const [analyzingIds, setAnalyzingIds] = useState<Set<string>>(new Set());
    const [viewingAnalysis, setViewingAnalysis] = useState<Product | null>(null);

    const fetchData = useCallback(async () => {
        try {
            const data = await apiFetch<Product[]>('/api/products');
            setProducts(Array.isArray(data) ? data : []);
        } catch (err) {
            console.error('Products fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    async function handleDelete(id: string) {
        if (!confirm('Delete this product?')) return;
        try {
            await apiFetch(`/api/products/${id}`, { method: 'DELETE' });
            fetchData();
        } catch (err) { console.error(err); }
    }

    async function handleAnalyze(product: Product) {
        setAnalyzingIds(prev => new Set(prev).add(product.id));
        try {
            const result = await apiFetch<any>('/api/products/analyze', {
                method: 'POST',
                body: JSON.stringify({ product_id: product.id }),
            });
            // Update local state immediately
            setProducts(prev => prev.map(p =>
                p.id === product.id ? { ...p, visual_description: result } : p
            ));

            // If we are currently viewing this product, update the modal too
            if (viewingAnalysis?.id === product.id) {
                setViewingAnalysis(prev => prev ? { ...prev, visual_description: result } : null);
            }
        } catch (err) {
            console.error('Analysis error:', err);
            // Don't alert, just log. UI allows retry.
        } finally {
            setAnalyzingIds(prev => {
                const next = new Set(prev);
                next.delete(product.id);
                return next;
            });
        }
    }

    let filtered = products;
    if (searchQuery) {
        const q = searchQuery.toLowerCase();
        filtered = products.filter((p) => p.name.toLowerCase().includes(q));
    }

    if (loading) return <div className="text-slate-500 text-sm italic animate-pulse py-12 text-center">Loading products...</div>;

    return (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
            {/* Upload Area */}
            <div className="lg:col-span-1">
                <ProductUpload onUploadSuccess={fetchData} />
            </div>

            {/* Product Grid */}
            <div className="lg:col-span-3">
                {filtered.length === 0 ? (
                    <div className="text-center py-20 text-slate-500 text-sm italic bg-slate-900/30 rounded-2xl border border-white/5">
                        No products found. Upload one to get started!
                    </div>
                ) : (
                    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                        {filtered.map((p) => (
                            <div key={p.id} className="glass-panel-light p-3 flex flex-col gap-2 relative group hover:bg-white/5 transition-colors">
                                <div className="aspect-[3/4] rounded-lg overflow-hidden bg-slate-800 relative">
                                    <img src={p.image_url} alt={p.name} className="w-full h-full object-cover" />

                                    {/* Overlay Actions */}
                                    <div className="absolute inset-0 bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col items-center justify-center gap-2">
                                        <button
                                            onClick={() => handleDelete(p.id)}
                                            className="bg-red-500/80 text-white px-3 py-1 rounded text-xs hover:bg-red-600 w-24"
                                        >
                                            Delete
                                        </button>

                                        {!p.visual_description ? (
                                            <button
                                                onClick={() => handleAnalyze(p)}
                                                disabled={analyzingIds.has(p.id)}
                                                className="bg-purple-500/80 text-white px-3 py-1 rounded text-xs hover:bg-purple-600 w-24 disabled:opacity-50"
                                            >
                                                {analyzingIds.has(p.id) ? 'Analyzing...' : '✨ Analyze'}
                                            </button>
                                        ) : (
                                            <button
                                                onClick={() => setViewingAnalysis(p)}
                                                className="bg-slate-500/80 text-white px-3 py-1 rounded text-xs hover:bg-slate-600 w-24"
                                            >
                                                View Info
                                            </button>
                                        )}
                                    </div>

                                    {/* Badge for Analyzed */}
                                    {p.visual_description && (
                                        <div className="absolute top-1 right-1 bg-green-500/20 text-green-400 p-1 rounded-full border border-green-500/30" title="AI Analyzed">
                                            ✅
                                        </div>
                                    )}
                                </div>

                                <div>
                                    <h4 className="font-medium text-slate-200 text-sm truncate" title={p.name}>{p.name}</h4>
                                    {p.category && <p className="text-xs text-slate-500">{p.category}</p>}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {/* Analysis Modal */}
            {viewingAnalysis && (
                <ProductAnalysisModal
                    product={viewingAnalysis}
                    onClose={() => setViewingAnalysis(null)}
                    onReanalyze={() => handleAnalyze(viewingAnalysis)}
                    isAnalyzing={analyzingIds.has(viewingAnalysis.id)}
                />
            )}
        </div>
    );
}

function ProductAnalysisModal({
    product,
    onClose,
    onReanalyze,
    isAnalyzing
}: {
    product: Product;
    onClose: () => void;
    onReanalyze: () => void;
    isAnalyzing: boolean;
}) {
    // Determine if we have valid data or just empty/partial
    const vd = product.visual_description || {};
    const hasData = vd.brand_name || vd.visual_description;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
            {/* Backdrop with blur */}
            <div className="absolute inset-0 bg-black/60 backdrop-blur-sm transition-opacity" />

            <div
                className="bg-[#0f1115] border border-white/10 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl relative animate-in fade-in zoom-in-95 duration-200"
                onClick={e => e.stopPropagation()}
            >
                {/* Header */}
                <div className="p-5 border-b border-white/5 flex justify-between items-center bg-gradient-to-r from-purple-500/10 to-transparent">
                    <div className="flex items-center gap-2">
                        <span className="text-lg">👁️</span>
                        <h3 className="text-lg font-bold text-white">Visual Analysis</h3>
                    </div>
                    <button onClick={onClose} className="text-slate-400 hover:text-white p-1 hover:bg-white/10 rounded-full transition-colors">
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                </div>

                <div className="p-6 space-y-6">
                    {/* Top Section: Image & Brand */}
                    <div className="flex gap-5">
                        <div className="w-24 h-24 rounded-xl bg-slate-800 border border-white/10 overflow-hidden flex-shrink-0 shadow-lg">
                            <img src={product.image_url} className="w-full h-full object-cover" />
                        </div>
                        <div className="flex-1 min-w-0 flex flex-col justify-center">
                            <h4 className="text-xl font-bold text-white truncate">
                                {vd.brand_name || <span className="text-slate-500 italic">Unknown Brand</span>}
                            </h4>
                            <p className="text-slate-400 text-sm truncate opacity-80">{product.name}</p>

                            {/* Re-analyze Button */}
                            <button
                                onClick={onReanalyze}
                                disabled={isAnalyzing}
                                className="mt-3 text-xs flex items-center gap-1.5 text-purple-400 hover:text-purple-300 transition-colors w-fit disabled:opacity-50"
                            >
                                <span className={isAnalyzing ? "animate-spin" : ""}>{isAnalyzing ? '↻' : '✨'}</span>
                                {isAnalyzing ? 'Analyzing...' : 'Re-analyze Image'}
                            </button>
                        </div>
                    </div>

                    {/* Details Grid */}
                    <div className="space-y-4">
                        <div className="bg-white/5 p-4 rounded-xl border border-white/5">
                            <p className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2 flex items-center gap-2">
                                📝 Visual Description
                            </p>
                            <div className="max-h-40 overflow-y-auto custom-scrollbar pr-2">
                                <p className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
                                    {vd.visual_description || "No description generated yet."}
                                </p>
                            </div>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="bg-white/5 p-4 rounded-xl border border-white/5">
                                <p className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2">Typography</p>
                                <p className="text-sm text-slate-300 font-medium">{vd.font_style || 'N/A'}</p>
                            </div>
                            <div className="bg-white/5 p-4 rounded-xl border border-white/5">
                                <p className="text-[10px] uppercase tracking-wider text-slate-500 font-bold mb-2">Colors</p>
                                <div className="flex flex-wrap gap-2">
                                    {vd.color_scheme && vd.color_scheme.length > 0 ? (
                                        vd.color_scheme.map((c: any, i: number) => (
                                            <div key={i} className="flex items-center gap-2 bg-black/40 pr-2 pl-1 py-1 rounded-md border border-white/5">
                                                <div className="w-4 h-4 rounded-full border border-white/10 shadow-sm" style={{ backgroundColor: c.hex }}></div>
                                                <span className="text-[10px] font-mono text-slate-400">{c.name}</span>
                                            </div>
                                        ))
                                    ) : (
                                        <span className="text-sm text-slate-500 italic">N/A</span>
                                    )}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Footer hint */}
                {!hasData && !isAnalyzing && (
                    <div className="bg-yellow-500/10 border-t border-yellow-500/20 p-3 text-center">
                        <p className="text-xs text-yellow-200/80">
                            Analysis incomplete? Try re-analyzing to get better results.
                        </p>
                    </div>
                )}
            </div>
        </div>
    );
}
