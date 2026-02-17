"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Influencer {
    id: string;
    name: string;
    visual_description: string;
    reference_image_url: string;
    category: string;
}

interface AppClip {
    id: string;
    name: string;
    category: string;
    video_url: string;
}

interface Script {
    id: string;
    text: string;
    category: string;
}

export default function GeneratePage() {
    const router = useRouter();
    const [step, setStep] = useState(1);
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [clips, setClips] = useState<AppClip[]>([]);
    const [loading, setLoading] = useState(true);

    const [selectedInfluencer, setSelectedInfluencer] = useState<string | null>(null);
    const [selectedClip, setSelectedClip] = useState<string | null>(null);
    const [scripts, setScripts] = useState<Script[]>([]);
    const [selectedScriptId, setSelectedScriptId] = useState<string | null>(null);
    const [hook, setHook] = useState("");
    const [duration, setDuration] = useState("15s");
    const [modelApi, setModelApi] = useState("infinitalk-audio");
    const [genLoading, setGenLoading] = useState(false);

    useEffect(() => {
        async function fetchData() {
            try {
                const infResp = await fetch(`${API_URL}/influencers`);
                const clipResp = await fetch(`${API_URL}/app_clips`);
                const scriptResp = await fetch(`${API_URL}/scripts`);

                if (infResp.ok) setInfluencers(await infResp.json());
                if (clipResp.ok) setClips(await clipResp.json());
                if (scriptResp.ok) setScripts(await scriptResp.json());
            } catch (err) {
                console.error("Failed to fetch data", err);
            } finally {
                setLoading(false);
            }
        }
        fetchData();
    }, []);

    const handleGenerateHook = async () => {
        if (!selectedInfluencer) return;
        setGenLoading(true);
        try {
            const influencer = influencers.find(i => i.id === selectedInfluencer);
            const resp = await fetch(`${API_URL}/scripts/generate?influencer_id=${selectedInfluencer}&category=${influencer?.category || 'General'}`, {
                method: "POST"
            });
            if (resp.ok) {
                const data = await resp.json();
                setHook(data.text);
                setSelectedScriptId(null);
            }
        } catch (err) {
            console.error("Failed to generate hook", err);
        } finally {
            setGenLoading(false);
        }
    };

    const handleSubmit = async () => {
        if (!selectedInfluencer) return;

        try {
            const resp = await fetch(`${API_URL}/jobs`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    influencer_id: selectedInfluencer,
                    app_clip_id: selectedClip,
                    script_id: selectedScriptId,
                    hook: hook,
                    model_api: modelApi,
                    assistant_type: influencers.find(i => i.id === selectedInfluencer)?.category || "Travel",
                    length: duration,
                    user_id: "00000000-0000-0000-0000-000000000000" // Mock user
                }),
            });

            if (resp.ok) {
                router.push("/history");
            }
        } catch (err) {
            console.error("Failed to submit job", err);
        }
    };

    if (loading) return <div className="text-center py-20 opacity-50">Initializing engine...</div>;

    return (
        <div className="max-w-4xl mx-auto space-y-10 pb-20">
            <header className="flex items-center justify-between">
                <div>
                    <h2 className="text-3xl font-bold">New <span className="gradient-text">Production</span></h2>
                    <p className="text-slate-400 mt-1">Configure your AI generator parameters.</p>
                </div>
                <div className="flex space-x-2">
                    {[1, 2, 3].map((s) => (
                        <div
                            key={s}
                            className={`w-10 h-10 rounded-full flex items-center justify-center font-bold border ${step === s ? 'bg-blue-600 border-blue-400 text-white' : 'bg-slate-900 border-slate-800 text-slate-500'}`}
                        >
                            {s}
                        </div>
                    ))}
                </div>
            </header>

            {/* Step 1: Influencer Selection */}
            {step === 1 && (
                <section className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <h3 className="text-xl font-bold flex items-center">
                        <span className="mr-3 text-2xl">👤</span> Select Influencer
                    </h3>
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                        {influencers.map((inf) => (
                            <button
                                key={inf.id}
                                onClick={() => setSelectedInfluencer(inf.id)}
                                className={`glass-panel p-4 rounded-2xl text-left transition-all glow-hover ${selectedInfluencer === inf.id ? 'border-blue-500 bg-blue-500/10 ring-2 ring-blue-500/20' : 'border-slate-800 opacity-70 hover:opacity-100'}`}
                            >
                                <div className="w-full aspect-square bg-slate-800 rounded-xl mb-4 overflow-hidden">
                                    {inf.reference_image_url ? (
                                        <img src={inf.reference_image_url} alt={inf.name} className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="w-full h-full flex items-center justify-center text-4xl opacity-20">👤</div>
                                    )}
                                </div>
                                <p className="font-bold text-lg">{inf.name}</p>
                                <p className="text-xs font-mono text-blue-400 uppercase tracking-widest mt-1">{inf.category}</p>
                            </button>
                        ))}
                    </div>
                    <div className="pt-6 flex justify-end">
                        <button
                            disabled={!selectedInfluencer}
                            onClick={() => setStep(2)}
                            className="px-8 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-30 rounded-xl font-bold transition-all shadow-lg shadow-blue-900/40"
                        >
                            Next Step: Assets →
                        </button>
                    </div>
                </section>
            )}

            {/* Step 2: Content & Assets */}
            {step === 2 && (
                <section className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                        <div className="space-y-4">
                            <h3 className="text-xl font-bold">🛠️ Model Selection</h3>
                            <select
                                value={modelApi}
                                onChange={(e) => setModelApi(e.target.value)}
                                className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 outline-none focus:ring-2 focus:ring-blue-500"
                            >
                                <option value="infinitalk-audio">InfiniteTalk + ElevenLabs (High Fidelity)</option>
                                <option value="seedance-1.5-pro">Seedance 1.5 Pro (Ultra Realistic)</option>
                                <option value="kling-2.6">Kling 2.6 (Cinematic)</option>
                                <option value="veo-3.1">Google Veo 3.1 (Experimental)</option>
                            </select>
                        </div>
                        <div className="space-y-4">
                            <h3 className="text-xl font-bold">📜 Script Library</h3>
                            <select
                                value={selectedScriptId || ""}
                                onChange={(e) => {
                                    const id = e.target.value;
                                    setSelectedScriptId(id || null);
                                    if (id) {
                                        const s = scripts.find(scr => scr.id === id);
                                        if (s) setHook(s.text);
                                    }
                                }}
                                className="w-full bg-slate-900 border border-slate-800 rounded-xl p-3 outline-none focus:ring-2 focus:ring-blue-500"
                            >
                                <option value="">-- Random / Custom Hook --</option>
                                {scripts.map(s => (
                                    <option key={s.id} value={s.id}>{s.text.substring(0, 40)}...</option>
                                ))}
                            </select>
                        </div>
                    </div>

                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h3 className="text-xl font-bold">🎬 Video Hook</h3>
                            <button
                                onClick={handleGenerateHook}
                                disabled={genLoading}
                                className="text-xs bg-blue-600/20 hover:bg-blue-600/40 text-blue-400 px-3 py-1 rounded-full border border-blue-500/30 transition-all"
                            >
                                {genLoading ? "✨ Generating..." : "✨ AI Generate Hook"}
                            </button>
                        </div>
                        <textarea
                            value={hook}
                            onChange={(e) => {
                                setHook(e.target.value);
                                setSelectedScriptId(null);
                            }}
                            placeholder="Type your script or use AI to generate one..."
                            className="w-full h-32 bg-slate-900 border border-slate-800 rounded-2xl p-4 focus:ring-2 focus:ring-blue-500 outline-none transition-all placeholder:text-slate-700"
                        />
                        <div className="flex space-x-4">
                            {["15s", "30s"].map((l) => (
                                <button
                                    key={l}
                                    onClick={() => setDuration(l)}
                                    className={`px-6 py-2 rounded-lg font-bold border transition-all ${duration === l ? 'bg-slate-100 text-slate-950 border-white' : 'border-slate-800 text-slate-400 hover:border-slate-500'}`}
                                >
                                    {l}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="space-y-4">
                        <h3 className="text-xl font-bold">📱 Mobile Feature (App Clip)</h3>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                            <button
                                onClick={() => setSelectedClip(null)}
                                className={`p-3 rounded-xl border text-sm transition-all ${selectedClip === null ? 'border-blue-500 bg-blue-500/10' : 'border-slate-800 hover:border-slate-600 text-slate-500'}`}
                            >
                                Auto-Select
                            </button>
                            {clips.map((clip) => (
                                <button
                                    key={clip.id}
                                    onClick={() => setSelectedClip(clip.id)}
                                    className={`p-3 rounded-xl border text-sm transition-all truncate text-left ${selectedClip === clip.id ? 'border-blue-500 bg-blue-500/10' : 'border-slate-800 hover:border-slate-600 text-slate-500'}`}
                                >
                                    {clip.name}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div className="pt-10 flex justify-between">
                        <button onClick={() => setStep(1)} className="px-6 py-3 text-slate-400 hover:text-white transition-colors">← Back</button>
                        <button
                            disabled={!hook}
                            onClick={() => setStep(3)}
                            className="px-8 py-3 bg-blue-600 hover:bg-blue-500 disabled:opacity-30 rounded-xl font-bold transition-all shadow-lg shadow-blue-900/40"
                        >
                            Verify Production →
                        </button>
                    </div>
                </section>
            )}

            {/* Step 3: Confirmation */}
            {step === 3 && (
                <section className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                    <div className="glass-panel p-1 rounded-3xl border-slate-800 overflow-hidden">
                        <div className="bg-slate-900/50 p-8 rounded-[23px] space-y-8">
                            <h3 className="text-2xl font-bold">Confirm <span className="text-blue-400">Production Run</span></h3>

                            <div className="grid grid-cols-2 gap-8">
                                <div className="space-y-1">
                                    <p className="text-xs uppercase font-bold text-slate-500 tracking-widest">Influencer</p>
                                    <p className="text-xl">{influencers.find(i => i.id === selectedInfluencer)?.name}</p>
                                </div>
                                <div className="space-y-1">
                                    <p className="text-xs uppercase font-bold text-slate-500 tracking-widest">Format</p>
                                    <p className="text-xl">Vertical ({duration})</p>
                                </div>
                                <div className="col-span-2 space-y-1">
                                    <p className="text-xs uppercase font-bold text-slate-500 tracking-widest">Script Snippet</p>
                                    <p className="text-slate-300 italic">"{hook || "Auto-Selected Unique Script"}"</p>
                                </div>
                                <div className="space-y-1">
                                    <p className="text-xs uppercase font-bold text-slate-500 tracking-widest">AI Engine</p>
                                    <p className="text-xl text-blue-400 font-mono text-sm">{modelApi}</p>
                                </div>
                            </div>

                            <div className="bg-blue-500/5 border border-blue-500/20 p-4 rounded-xl flex items-center space-x-4">
                                <span className="text-2xl text-blue-400">🛡️</span>
                                <p className="text-sm text-blue-200/70 leading-relaxed">
                                    <strong>Anti-Fatigue Filter Active</strong>: The system will automatically select a unique combination of hook and app clip to ensure your content remains fresh for social algorithms.
                                </p>
                            </div>

                            <div className="pt-4 flex items-center justify-between border-t border-slate-800">
                                <button onClick={() => setStep(2)} className="text-slate-500 hover:text-white">Modify settings</button>
                                <button
                                    onClick={handleSubmit}
                                    className="px-12 py-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 rounded-2xl font-black text-lg tracking-tight transition-all active:scale-95 shadow-xl shadow-blue-900/20"
                                >
                                    🚀 Launch Engine
                                </button>
                            </div>
                        </div>
                    </div>
                </section>
            )}
        </div>
    );
}
