"use client";

import { useState, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Influencer {
    id: string;
    name: string;
    category: string;
}

interface AppClip {
    id: string;
    name: string;
    category: string;
}

export default function ManagePage() {
    const [activeTab, setActiveTab] = useState<"influencers" | "clips">("influencers");
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [clips, setClips] = useState<AppClip[]>([]);
    const [loading, setLoading] = useState(true);

    const [infForm, setInfForm] = useState({
        name: "",
        gender: "Female",
        accent: "Castilian Spanish (Spain)",
        tone: "Enthusiastic",
        visual_description: "",
        reference_image_url: "",
        category: "Travel"
    });

    const [clipForm, setClipForm] = useState({
        name: "",
        category: "Travel",
        video_url: "",
        duration: 4.0
    });

    const fetchData = async () => {
        setLoading(true);
        try {
            const infResp = await fetch(`${API_URL}/influencers`);
            const clipResp = await fetch(`${API_URL}/app_clips`);
            if (infResp.ok) setInfluencers(await infResp.json());
            if (clipResp.ok) setClips(await clipResp.json());
        } catch (err) {
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const addInfluencer = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const resp = await fetch(`${API_URL}/influencers`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(infForm),
            });
            if (resp.ok) {
                setInfForm({ name: "", gender: "Female", accent: "Castilian Spanish (Spain)", tone: "Enthusiastic", visual_description: "", reference_image_url: "", category: "Travel" });
                fetchData();
            }
        } catch (err) { console.error(err); }
    };

    const addClip = async (e: React.FormEvent) => {
        e.preventDefault();
        try {
            const resp = await fetch(`${API_URL}/app_clips`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(clipForm),
            });
            if (resp.ok) {
                setClipForm({ name: "", category: "Travel", video_url: "", duration: 4.0 });
                fetchData();
            }
        } catch (err) { console.error(err); }
    };

    return (
        <div className="space-y-8 pb-20">
            <header>
                <h2 className="text-3xl font-bold italic tracking-tighter">Assets <span className="gradient-text">Management</span></h2>
                <p className="text-slate-400 mt-1 uppercase text-xs font-bold tracking-widest">Add and configure your production library</p>
            </header>

            <div className="flex space-x-4 border-b border-slate-900 pb-px">
                <button
                    onClick={() => setActiveTab("influencers")}
                    className={`pb-4 px-2 font-bold transition-all border-b-2 ${activeTab === "influencers" ? "border-blue-500 text-blue-400" : "border-transparent text-slate-500 hover:text-slate-300"}`}
                >
                    Influencers ({influencers.length})
                </button>
                <button
                    onClick={() => setActiveTab("clips")}
                    className={`pb-4 px-2 font-bold transition-all border-b-2 ${activeTab === "clips" ? "border-blue-500 text-blue-400" : "border-transparent text-slate-500 hover:text-slate-300"}`}
                >
                    App Clips ({clips.length})
                </button>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
                {/* Form Column */}
                <div className="lg:col-span-1 space-y-6">
                    {activeTab === "influencers" ? (
                        <form onSubmit={addInfluencer} className="glass-panel p-6 rounded-2xl border-slate-800 space-y-4">
                            <h3 className="font-bold text-lg mb-2">Add Influencer</h3>
                            <div className="space-y-4">
                                <div>
                                    <label className="text-xs font-bold text-slate-500 uppercase block mb-1">Name</label>
                                    <input value={infForm.name} onChange={e => setInfForm({ ...infForm, name: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm focus:ring-1 focus:ring-blue-500 outline-none" placeholder="Ex: Maria" required />
                                </div>
                                <div className="grid grid-cols-2 gap-4">
                                    <div>
                                        <label className="text-xs font-bold text-slate-500 uppercase block mb-1">Gender</label>
                                        <select value={infForm.gender} onChange={e => setInfForm({ ...infForm, gender: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm outline-none">
                                            <option>Female</option>
                                            <option>Male</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="text-xs font-bold text-slate-500 uppercase block mb-1">Category</label>
                                        <select value={infForm.category} onChange={e => setInfForm({ ...infForm, category: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm outline-none">
                                            <option>Travel</option>
                                            <option>Shop</option>
                                            <option>Product</option>
                                            <option>App</option>
                                        </select>
                                    </div>
                                </div>
                                <div>
                                    <label className="text-xs font-bold text-slate-500 uppercase block mb-1">Visual Description</label>
                                    <textarea value={infForm.visual_description} onChange={e => setInfForm({ ...infForm, visual_description: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm focus:ring-1 focus:ring-blue-500 outline-none h-24" placeholder="Description for AI prompt..." required />
                                </div>
                                <div>
                                    <label className="text-xs font-bold text-slate-500 uppercase block mb-1">Reference Image URL</label>
                                    <input value={infForm.reference_image_url} onChange={e => setInfForm({ ...infForm, reference_image_url: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm focus:ring-1 focus:ring-blue-500 outline-none" placeholder="https://..." />
                                </div>
                                <button type="submit" className="w-full py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-bold transition-all active:scale-95 shadow-lg shadow-blue-900/20">Create Influencer</button>
                            </div>
                        </form>
                    ) : (
                        <form onSubmit={addClip} className="glass-panel p-6 rounded-2xl border-slate-800 space-y-4">
                            <h3 className="font-bold text-lg mb-2">Add App Clip</h3>
                            <div className="space-y-4">
                                <div>
                                    <label className="text-xs font-bold text-slate-500 uppercase block mb-1">Clip Name</label>
                                    <input value={clipForm.name} onChange={e => setClipForm({ ...clipForm, name: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm focus:ring-1 focus:ring-blue-500 outline-none" placeholder="Ex: Filter Search" required />
                                </div>
                                <div>
                                    <label className="text-xs font-bold text-slate-500 uppercase block mb-1">Category (Assistant Type)</label>
                                    <select value={clipForm.category} onChange={e => setClipForm({ ...clipForm, category: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm outline-none">
                                        <option>Travel</option>
                                        <option>Shop</option>
                                        <option>Product</option>
                                        <option>App</option>
                                    </select>
                                </div>
                                <div>
                                    <label className="text-xs font-bold text-slate-500 uppercase block mb-1">Direct Video URL</label>
                                    <input value={clipForm.video_url} onChange={e => setClipForm({ ...clipForm, video_url: e.target.value })} className="w-full bg-slate-950 border border-slate-800 rounded-lg p-3 text-sm focus:ring-1 focus:ring-blue-500 outline-none" placeholder="https://...mp4" required />
                                </div>
                                <button type="submit" className="w-full py-3 bg-blue-600 hover:bg-blue-500 rounded-xl font-bold transition-all active:scale-95 shadow-lg shadow-blue-900/20">Create App Clip</button>
                            </div>
                        </form>
                    )}
                </div>

                {/* List Column */}
                <div className="lg:col-span-2 space-y-4">
                    <h3 className="font-bold text-lg px-2">Production Library</h3>
                    {loading ? (
                        <div className="p-10 text-center opacity-30 italic">Synchronizing with cloud...</div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {activeTab === "influencers" ? (
                                influencers.map(inf => (
                                    <div key={inf.id} className="glass-panel p-4 rounded-xl border-slate-900 flex items-center justify-between">
                                        <div>
                                            <p className="font-bold">{inf.name}</p>
                                            <p className="text-xs text-blue-500 font-mono">{inf.category}</p>
                                        </div>
                                        <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs opacity-50">API</div>
                                    </div>
                                ))
                            ) : (
                                clips.map(clip => (
                                    <div key={clip.id} className="glass-panel p-4 rounded-xl border-slate-900 flex items-center justify-between">
                                        <div>
                                            <p className="font-bold">{clip.name}</p>
                                            <p className="text-xs text-purple-500 font-mono">{clip.category}</p>
                                        </div>
                                        <div className="w-10 h-10 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-xs opacity-50">MP4</div>
                                    </div>
                                ))
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
