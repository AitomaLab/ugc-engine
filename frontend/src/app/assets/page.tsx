'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Influencer {
    id: string;
    name: string;
    description?: string;
    personality?: string;
    style?: string;
    speaking_style?: string;
    target_audience?: string;
    image_url?: string;
    elevenlabs_voice_id?: string;
}

interface Script {
    id: string;
    text: string;
    category?: string;
}

interface AppClipItem {
    id: string;
    name: string;
    description?: string;
    video_url: string;
    duration_seconds?: number;
}

type Tab = 'influencers' | 'scripts' | 'clips';

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function AssetsPage() {
    const [activeTab, setActiveTab] = useState<Tab>('influencers');

    const tabs: { key: Tab; label: string; icon: string }[] = [
        { key: 'influencers', label: 'Influencers', icon: '👤' },
        { key: 'scripts', label: 'Scripts', icon: '✍️' },
        { key: 'clips', label: 'App Clips', icon: '📱' },
    ];

    return (
        <div>
            <h1 className="text-3xl font-bold gradient-text mb-2">Asset Libraries</h1>
            <p className="text-slate-400 mb-8">Manage your influencers, scripts, and app clips in one place.</p>

            {/* Tab Header */}
            <div className="flex gap-2 mb-8 border-b border-slate-800 pb-1">
                {tabs.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`px-5 py-3 rounded-t-lg font-medium text-sm transition-all ${activeTab === tab.key
                                ? 'bg-slate-800 text-white border-b-2 border-blue-500'
                                : 'text-slate-400 hover:text-white hover:bg-slate-800/50'
                            }`}
                    >
                        {tab.icon} {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            {activeTab === 'influencers' && <InfluencersTab />}
            {activeTab === 'scripts' && <ScriptsTab />}
            {activeTab === 'clips' && <ClipsTab />}
        </div>
    );
}

// ===========================================================================
// Influencers Tab
// ===========================================================================
function InfluencersTab() {
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({ name: '', description: '', personality: '', style: '', speaking_style: '', target_audience: '', image_url: '', elevenlabs_voice_id: '' });

    const loadData = useCallback(async () => {
        try {
            const data = await apiFetch<Influencer[]>('/influencers');
            setInfluencers(data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, []);

    useEffect(() => { loadData(); }, [loadData]);

    const handleCreate = async () => {
        try {
            await apiFetch('/influencers', { method: 'POST', body: JSON.stringify(form) });
            setShowForm(false);
            setForm({ name: '', description: '', personality: '', style: '', speaking_style: '', target_audience: '', image_url: '', elevenlabs_voice_id: '' });
            loadData();
        } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Failed'); }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this influencer?')) return;
        try {
            await apiFetch(`/influencers/${id}`, { method: 'DELETE' });
            loadData();
        } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Failed'); }
    };

    if (loading) return <div className="text-slate-400 animate-pulse">Loading influencers...</div>;

    return (
        <div>
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-semibold text-white">{influencers.length} Influencers</h2>
                <button onClick={() => setShowForm(!showForm)} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-all">
                    {showForm ? 'Cancel' : '+ Add Influencer'}
                </button>
            </div>

            {showForm && (
                <div className="glass-panel rounded-xl p-6 mb-6 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <input placeholder="Name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none" />
                        <input placeholder="ElevenLabs Voice ID" value={form.elevenlabs_voice_id} onChange={(e) => setForm({ ...form, elevenlabs_voice_id: e.target.value })} className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none" />
                        <input placeholder="Image URL (Supabase Storage)" value={form.image_url} onChange={(e) => setForm({ ...form, image_url: e.target.value })} className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none col-span-2" />
                        <input placeholder="Personality" value={form.personality} onChange={(e) => setForm({ ...form, personality: e.target.value })} className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none" />
                        <input placeholder="Style" value={form.style} onChange={(e) => setForm({ ...form, style: e.target.value })} className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none" />
                        <textarea placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none col-span-2" rows={2} />
                    </div>
                    <button onClick={handleCreate} disabled={!form.name} className="px-6 py-3 bg-green-600 hover:bg-green-500 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg font-medium transition-all">
                        Create Influencer
                    </button>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {influencers.map((inf) => (
                    <div key={inf.id} className="glass-panel rounded-xl p-5 flex gap-4 glow-hover transition-all">
                        {inf.image_url ? (
                            <img src={inf.image_url} alt={inf.name} className="w-16 h-16 rounded-full object-cover border-2 border-slate-700" />
                        ) : (
                            <div className="w-16 h-16 rounded-full bg-slate-700 flex items-center justify-center text-2xl">{inf.name[0]}</div>
                        )}
                        <div className="flex-1 min-w-0">
                            <h3 className="font-bold text-white text-lg">{inf.name}</h3>
                            {inf.personality && <p className="text-slate-400 text-sm truncate">{inf.personality}</p>}
                            {inf.elevenlabs_voice_id && <p className="text-blue-400 text-xs mt-1 font-mono truncate">Voice: {inf.elevenlabs_voice_id}</p>}
                        </div>
                        <button onClick={() => handleDelete(inf.id)} className="text-red-400 hover:text-red-300 text-sm self-start">🗑️</button>
                    </div>
                ))}
            </div>

            {influencers.length === 0 && <p className="text-slate-500 text-center py-12">No influencers yet. Add your first one above.</p>}
        </div>
    );
}

// ===========================================================================
// Scripts Tab
// ===========================================================================
function ScriptsTab() {
    const [scripts, setScripts] = useState<Script[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({ text: '', category: '' });

    const loadData = useCallback(async () => {
        try {
            const data = await apiFetch<Script[]>('/scripts');
            setScripts(data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, []);

    useEffect(() => { loadData(); }, [loadData]);

    const handleCreate = async () => {
        try {
            await apiFetch('/scripts', { method: 'POST', body: JSON.stringify(form) });
            setShowForm(false);
            setForm({ text: '', category: '' });
            loadData();
        } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Failed'); }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this script?')) return;
        try {
            await apiFetch(`/scripts/${id}`, { method: 'DELETE' });
            loadData();
        } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Failed'); }
    };

    if (loading) return <div className="text-slate-400 animate-pulse">Loading scripts...</div>;

    return (
        <div>
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-semibold text-white">{scripts.length} Scripts</h2>
                <button onClick={() => setShowForm(!showForm)} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-all">
                    {showForm ? 'Cancel' : '+ Add Script'}
                </button>
            </div>

            {showForm && (
                <div className="glass-panel rounded-xl p-6 mb-6 space-y-4">
                    <textarea placeholder="Script text / hook *" value={form.text} onChange={(e) => setForm({ ...form, text: e.target.value })} className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none" rows={3} />
                    <input placeholder="Category (e.g. Travel, Finance, Fashion)" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none" />
                    <button onClick={handleCreate} disabled={!form.text} className="px-6 py-3 bg-green-600 hover:bg-green-500 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg font-medium transition-all">
                        Add Script
                    </button>
                </div>
            )}

            <div className="space-y-3">
                {scripts.map((s) => (
                    <div key={s.id} className="glass-panel rounded-xl p-5 flex items-start gap-4 glow-hover transition-all">
                        <div className="flex-1 min-w-0">
                            <p className="text-white">{s.text}</p>
                            {s.category && <span className="inline-block mt-2 px-3 py-1 bg-blue-500/20 text-blue-400 rounded-full text-xs font-medium">{s.category}</span>}
                        </div>
                        <button onClick={() => handleDelete(s.id)} className="text-red-400 hover:text-red-300 text-sm shrink-0">🗑️</button>
                    </div>
                ))}
            </div>

            {scripts.length === 0 && <p className="text-slate-500 text-center py-12">No scripts yet. Add hooks and scripts for your videos.</p>}
        </div>
    );
}

// ===========================================================================
// App Clips Tab
// ===========================================================================
function ClipsTab() {
    const [clips, setClips] = useState<AppClipItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [showForm, setShowForm] = useState(false);
    const [form, setForm] = useState({ name: '', description: '', video_url: '', duration_seconds: '' });

    const loadData = useCallback(async () => {
        try {
            const data = await apiFetch<AppClipItem[]>('/app-clips');
            setClips(data);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, []);

    useEffect(() => { loadData(); }, [loadData]);

    const handleCreate = async () => {
        try {
            await apiFetch('/app-clips', {
                method: 'POST',
                body: JSON.stringify({
                    ...form,
                    duration_seconds: form.duration_seconds ? parseInt(form.duration_seconds) : null,
                }),
            });
            setShowForm(false);
            setForm({ name: '', description: '', video_url: '', duration_seconds: '' });
            loadData();
        } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Failed'); }
    };

    const handleDelete = async (id: string) => {
        if (!confirm('Delete this app clip?')) return;
        try {
            await apiFetch(`/app-clips/${id}`, { method: 'DELETE' });
            loadData();
        } catch (e: unknown) { alert(e instanceof Error ? e.message : 'Failed'); }
    };

    if (loading) return <div className="text-slate-400 animate-pulse">Loading clips...</div>;

    return (
        <div>
            <div className="flex justify-between items-center mb-6">
                <h2 className="text-xl font-semibold text-white">{clips.length} App Clips</h2>
                <button onClick={() => setShowForm(!showForm)} className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded-lg text-sm font-medium transition-all">
                    {showForm ? 'Cancel' : '+ Add Clip'}
                </button>
            </div>

            {showForm && (
                <div className="glass-panel rounded-xl p-6 mb-6 space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <input placeholder="Clip Name *" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none" />
                        <input placeholder="Duration (sec)" value={form.duration_seconds} onChange={(e) => setForm({ ...form, duration_seconds: e.target.value })} className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none" type="number" />
                        <input placeholder="Video URL (Supabase Storage) *" value={form.video_url} onChange={(e) => setForm({ ...form, video_url: e.target.value })} className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none col-span-2" />
                        <textarea placeholder="Description" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} className="bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white placeholder-slate-500 focus:border-blue-500 outline-none col-span-2" rows={2} />
                    </div>
                    <button onClick={handleCreate} disabled={!form.name || !form.video_url} className="px-6 py-3 bg-green-600 hover:bg-green-500 disabled:bg-slate-700 disabled:text-slate-500 rounded-lg font-medium transition-all">
                        Add Clip
                    </button>
                </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {clips.map((clip) => (
                    <div key={clip.id} className="glass-panel rounded-xl p-5 glow-hover transition-all">
                        <div className="flex justify-between items-start">
                            <div>
                                <h3 className="font-bold text-white">{clip.name}</h3>
                                {clip.description && <p className="text-slate-400 text-sm mt-1">{clip.description}</p>}
                                {clip.duration_seconds && <span className="inline-block mt-2 px-3 py-1 bg-purple-500/20 text-purple-400 rounded-full text-xs">{clip.duration_seconds}s</span>}
                            </div>
                            <button onClick={() => handleDelete(clip.id)} className="text-red-400 hover:text-red-300 text-sm">🗑️</button>
                        </div>
                        <p className="text-slate-500 text-xs mt-3 truncate font-mono">{clip.video_url}</p>
                    </div>
                ))}
            </div>

            {clips.length === 0 && <p className="text-slate-500 text-center py-12">No app clips yet. Upload mobile app screen recordings.</p>}
        </div>
    );
}
