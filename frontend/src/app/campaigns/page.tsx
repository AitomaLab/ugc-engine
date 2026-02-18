'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiFetch, statusColor, formatDate } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
interface Influencer {
    id: string;
    name: string;
    image_url?: string;
}

interface VideoJob {
    id: string;
    influencer_id?: string;
    status: string;
    progress: number;
    final_video_url?: string;
    error_message?: string;
    created_at?: string;
    updated_at?: string;
}

interface Stats {
    total_jobs: number;
    pending: number;
    processing: number;
    success: number;
    failed: number;
    influencers: number;
    scripts: number;
    app_clips: number;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function CampaignsPage() {
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [jobs, setJobs] = useState<VideoJob[]>([]);
    const [stats, setStats] = useState<Stats | null>(null);
    const [loading, setLoading] = useState(true);

    // Form state
    const [selectedInfluencer, setSelectedInfluencer] = useState('');
    const [count, setCount] = useState(5);
    const [duration, setDuration] = useState(15);
    const [submitting, setSubmitting] = useState(false);
    const [result, setResult] = useState<{ count: number; job_ids: string[] } | null>(null);

    const loadData = useCallback(async () => {
        try {
            const [infData, jobData, statsData] = await Promise.all([
                apiFetch<Influencer[]>('/influencers'),
                apiFetch<VideoJob[]>('/jobs?limit=50'),
                apiFetch<Stats>('/stats'),
            ]);
            setInfluencers(infData);
            setJobs(jobData);
            setStats(statsData);
        } catch (e) { console.error(e); }
        setLoading(false);
    }, []);

    useEffect(() => {
        loadData();
        const interval = setInterval(loadData, 5000); // Poll every 5 seconds
        return () => clearInterval(interval);
    }, [loadData]);

    const handleBulkCreate = async () => {
        setSubmitting(true);
        setResult(null);
        try {
            const data = await apiFetch<{ count: number; job_ids: string[] }>('/jobs/bulk', {
                method: 'POST',
                body: JSON.stringify({
                    influencer_id: selectedInfluencer,
                    count,
                    duration,
                }),
            });
            setResult(data);
            loadData();
        } catch (e: unknown) {
            alert(e instanceof Error ? e.message : 'Campaign creation failed');
        }
        setSubmitting(false);
    };

    if (loading) return <div className="text-slate-400 animate-pulse">Loading campaigns...</div>;

    return (
        <div>
            <h1 className="text-3xl font-bold gradient-text mb-2">Campaigns</h1>
            <p className="text-slate-400 mb-8">Launch bulk video generation campaigns and track progress.</p>

            {/* Stats Overview */}
            {stats && (
                <div className="grid grid-cols-4 gap-4 mb-8">
                    {[
                        { label: 'Total Jobs', value: stats.total_jobs, color: 'text-white' },
                        { label: 'Pending', value: stats.pending, color: 'text-amber-400' },
                        { label: 'Processing', value: stats.processing, color: 'text-blue-400' },
                        { label: 'Completed', value: stats.success, color: 'text-green-400' },
                    ].map((stat) => (
                        <div key={stat.label} className="glass-panel rounded-xl p-5 text-center">
                            <p className={`text-3xl font-bold ${stat.color}`}>{stat.value}</p>
                            <p className="text-slate-500 text-sm mt-1">{stat.label}</p>
                        </div>
                    ))}
                </div>
            )}

            {/* Campaign Creator */}
            <div className="glass-panel rounded-xl p-8 mb-8">
                <h2 className="text-xl font-bold text-white mb-6">🚀 Launch New Campaign</h2>

                <div className="grid grid-cols-3 gap-6">
                    {/* Influencer Selector */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">Influencer</label>
                        <select
                            value={selectedInfluencer}
                            onChange={(e) => setSelectedInfluencer(e.target.value)}
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:border-blue-500 outline-none appearance-none cursor-pointer"
                        >
                            <option value="">Select influencer...</option>
                            {influencers.map((inf) => (
                                <option key={inf.id} value={inf.id}>{inf.name}</option>
                            ))}
                        </select>
                    </div>

                    {/* Count */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">Number of Videos</label>
                        <input
                            type="number"
                            value={count}
                            onChange={(e) => setCount(Math.max(1, parseInt(e.target.value) || 1))}
                            min={1}
                            max={100}
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:border-blue-500 outline-none"
                        />
                    </div>

                    {/* Duration */}
                    <div>
                        <label className="block text-sm font-medium text-slate-400 mb-2">Duration (seconds)</label>
                        <select
                            value={duration}
                            onChange={(e) => setDuration(parseInt(e.target.value))}
                            className="w-full bg-slate-800 border border-slate-700 rounded-lg px-4 py-3 text-white focus:border-blue-500 outline-none appearance-none cursor-pointer"
                        >
                            <option value={15}>15s (Short)</option>
                            <option value={30}>30s (Medium)</option>
                            <option value={60}>60s (Long)</option>
                        </select>
                    </div>
                </div>

                <div className="mt-6 flex items-center gap-4">
                    <button
                        onClick={handleBulkCreate}
                        disabled={!selectedInfluencer || submitting}
                        className="px-8 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 disabled:from-slate-700 disabled:to-slate-700 disabled:text-slate-500 rounded-lg font-bold text-lg transition-all shadow-lg shadow-blue-500/20 hover:shadow-blue-500/40"
                    >
                        {submitting ? '⏳ Dispatching...' : `🚀 Launch ${count} Videos`}
                    </button>

                    {result && (
                        <span className="text-green-400 text-sm animate-pulse">
                            ✅ Dispatched {result.count} jobs successfully!
                        </span>
                    )}
                </div>
            </div>

            {/* Job List */}
            <h2 className="text-xl font-bold text-white mb-4">Recent Jobs</h2>
            <div className="space-y-2">
                {jobs.map((job) => (
                    <div key={job.id} className="glass-panel rounded-lg p-4 flex items-center gap-4">
                        {/* Status Badge */}
                        <span
                            className="w-3 h-3 rounded-full shrink-0"
                            style={{ backgroundColor: statusColor(job.status) }}
                        />

                        {/* Job Info */}
                        <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-3">
                                <span className="text-white font-mono text-sm">{job.id.slice(0, 8)}...</span>
                                <span className="text-slate-500 text-xs">{formatDate(job.created_at)}</span>
                            </div>
                            {job.error_message && (
                                <p className="text-red-400 text-xs mt-1 truncate">{job.error_message}</p>
                            )}
                        </div>

                        {/* Progress Bar */}
                        <div className="w-32 shrink-0">
                            <div className="w-full h-2 bg-slate-700 rounded-full overflow-hidden">
                                <div
                                    className="h-full rounded-full transition-all duration-500"
                                    style={{
                                        width: `${job.progress}%`,
                                        backgroundColor: statusColor(job.status),
                                    }}
                                />
                            </div>
                            <p className="text-xs text-slate-500 text-right mt-1">{job.progress}%</p>
                        </div>

                        {/* Status Label */}
                        <span
                            className="px-3 py-1 rounded-full text-xs font-bold uppercase shrink-0"
                            style={{ color: statusColor(job.status), backgroundColor: `${statusColor(job.status)}20` }}
                        >
                            {job.status}
                        </span>

                        {/* Video Link */}
                        {job.final_video_url && (
                            <a
                                href={job.final_video_url}
                                target="_blank"
                                rel="noreferrer"
                                className="text-blue-400 hover:text-blue-300 text-sm shrink-0"
                            >
                                🎥 View
                            </a>
                        )}
                    </div>
                ))}
            </div>

            {jobs.length === 0 && (
                <p className="text-slate-500 text-center py-12">No jobs yet. Launch your first campaign above!</p>
            )}
        </div>
    );
}
