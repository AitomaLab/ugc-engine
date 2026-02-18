'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch, formatDate, getApiUrl } from '@/lib/utils';
import { Influencer, Script, AppClipItem, VideoJob } from '@/lib/types';
import { InfluencerModal } from './InfluencerModal';

type Tab = 'videos' | 'influencers' | 'scripts' | 'clips';

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
    ];

    return (
        <div className="space-y-8 animate-slide-up">
            <header>
                <h2 className="text-3xl font-bold tracking-tight">
                    <span className="gradient-text">Library</span>
                </h2>
                <p className="text-slate-400 mt-2 text-sm">
                    Your complete creative universe — videos, influencers, scripts, and clips.
                </p>
            </header>

            {/* Global Search */}
            <div className="relative">
                <svg
                    className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500"
                    width="16"
                    height="16"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                >
                    <circle cx="11" cy="11" r="8" />
                    <path d="M21 21l-4.3-4.3" />
                </svg>
                <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search across all assets..."
                    className="input-field pl-11"
                    id="library-search"
                />
            </div>

            {/* Tabs */}
            <div className="flex gap-1 p-1 bg-slate-900/60 rounded-xl w-fit">
                {tabs.map((t) => (
                    <button
                        key={t.key}
                        onClick={() => setTab(t.key)}
                        className={`tab-button flex items-center gap-2 ${tab === t.key ? 'active' : ''}`}
                    >
                        <span className="text-sm">{t.icon}</span>
                        {t.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            {tab === 'videos' && <VideosTab searchQuery={searchQuery} />}
            {tab === 'influencers' && <InfluencersTab searchQuery={searchQuery} />}
            {tab === 'scripts' && <ScriptsTab searchQuery={searchQuery} />}
            {tab === 'clips' && <ClipsTab searchQuery={searchQuery} />}
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
