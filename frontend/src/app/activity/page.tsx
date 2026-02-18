'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiFetch, formatDate, getApiUrl } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Job {
    id: string;
    status: string;
    progress: number;
    created_at: string;
    updated_at?: string;
    final_video_url?: string;
    error_message?: string;
    influencer_id?: string;
    model_api?: string;
    campaign_name?: string;
    total_cost?: number;
    cost_video?: number;
    cost_voice?: number;
    cost_music?: number;
    cost_processing?: number;
}

interface Influencer {
    id: string;
    name: string;
}

// ---------------------------------------------------------------------------
// Error Troubleshooting
// ---------------------------------------------------------------------------

function getTroubleshooting(error: string): string {
    const lower = error.toLowerCase();
    if (lower.includes('missingschema') || lower.includes('invalid url'))
        return "The reference image URL is invalid. Check the influencer's image URL in the Library.";
    if (lower.includes('timeout') || lower.includes('timed out'))
        return "The AI API took too long to respond. This is usually temporary. Try again in a few minutes.";
    if (lower.includes('nonetype') || lower.includes("'none'"))
        return "A required field was missing. Check that the influencer, script, and app clip are all properly configured.";
    if (lower.includes('bucket') || lower.includes('storage'))
        return "A storage bucket is misconfigured. Contact support or check the Supabase storage configuration.";
    if (lower.includes('rate limit') || lower.includes('429'))
        return "You've hit an API rate limit. Wait a few minutes and try again.";
    if (lower.includes('auth') || lower.includes('403') || lower.includes('401'))
        return "Authentication error. Check your API keys in the .env configuration.";
    return "An unexpected error occurred. Check the full error message below for details.";
}

// ---------------------------------------------------------------------------
// Activity Page
// ---------------------------------------------------------------------------

export default function ActivityPage() {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [loading, setLoading] = useState(true);
    const [groupByCampaign, setGroupByCampaign] = useState(false);
    const [errorModal, setErrorModal] = useState<Job | null>(null);

    const fetchData = useCallback(async () => {
        try {
            const [jobsData, infData] = await Promise.all([
                apiFetch<Job[]>('/jobs?limit=200'),
                apiFetch<Influencer[]>('/influencers'),
            ]);
            setJobs(jobsData);
            setInfluencers(infData);
        } catch (err) {
            console.error('Activity fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    // Cost stats
    const [costStats, setCostStats] = useState<{ total_spend_month: number; total_spend_all: number } | null>(null);
    useEffect(() => {
        async function fetchCostStats() {
            try {
                const data = await apiFetch<{ total_spend_month: number; total_spend_all: number }>('/stats/costs');
                setCostStats(data);
            } catch { /* silent */ }
        }
        fetchCostStats();
    }, []);

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, [fetchData]);

    const influencerMap = new Map(influencers.map((i) => [i.id, i]));

    // Stats
    const totalJobs = jobs.length;
    const successJobs = jobs.filter((j) => j.status === 'success').length;
    const failedJobs = jobs.filter((j) => j.status === 'failed').length;
    const successRate = totalJobs > 0 ? Math.round((successJobs / totalJobs) * 100) : 0;

    // Compute average duration (for completed jobs that have both created_at and updated_at)
    const completedWithDuration = jobs.filter((j) => j.status === 'success' && j.created_at && j.updated_at);
    const avgDuration = completedWithDuration.length > 0
        ? Math.round(completedWithDuration.reduce((sum, j) => {
            const start = new Date(j.created_at).getTime();
            const end = new Date(j.updated_at!).getTime();
            return sum + (end - start) / 1000 / 60;
        }, 0) / completedWithDuration.length)
        : 0;

    // Group by campaign
    const campaignGroups = new Map<string, Job[]>();
    if (groupByCampaign) {
        for (const job of jobs) {
            const key = job.campaign_name || 'Single Generation';
            if (!campaignGroups.has(key)) campaignGroups.set(key, []);
            campaignGroups.get(key)!.push(job);
        }
    }

    function getDuration(job: Job): string {
        if (job.status !== 'success' || !job.created_at || !job.updated_at) return '—';
        const start = new Date(job.created_at).getTime();
        const end = new Date(job.updated_at).getTime();
        const mins = Math.round((end - start) / 1000 / 60);
        return mins > 0 ? `${mins}m` : '<1m';
    }

    if (loading) {
        return (
            <div className="flex items-center justify-center h-96">
                <div className="text-slate-500 text-sm italic animate-pulse">Loading activity...</div>
            </div>
        );
    }

    return (
        <div className="space-y-8 animate-slide-up">
            <header>
                <h2 className="text-3xl font-bold tracking-tight">
                    <span className="gradient-text">Activity</span>
                </h2>
                <p className="text-slate-400 mt-2 text-sm">
                    Monitor generation jobs, track performance, and debug issues.
                </p>
            </header>

            {/* ============ RESOURCE USAGE DASHBOARD ============ */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                {[
                    { label: 'Total Videos', value: totalJobs.toString(), sub: 'all time' },
                    { label: 'Success Rate', value: `${successRate}%`, sub: `${successJobs} success · ${failedJobs} failed` },
                    { label: 'Avg. Gen Time', value: avgDuration > 0 ? `${avgDuration}m` : '—', sub: 'per video' },
                    { label: 'Active Queue', value: (jobs.filter(j => j.status === 'processing' || j.status === 'pending').length).toString(), sub: 'in pipeline' },
                    { label: 'Total Spend', value: costStats ? `$${costStats.total_spend_month.toFixed(2)}` : '—', sub: costStats ? `$${costStats.total_spend_all.toFixed(2)} all time` : 'this month' },
                ].map((stat) => (
                    <div key={stat.label} className="glass-panel p-5">
                        <p className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">{stat.label}</p>
                        <p className="text-2xl font-bold text-slate-100 mt-1">{stat.value}</p>
                        <p className="text-[10px] text-slate-500 mt-1">{stat.sub}</p>
                    </div>
                ))}
            </div>

            {/* ============ CONTROLS ============ */}
            <div className="flex items-center gap-4">
                <button
                    onClick={() => setGroupByCampaign(!groupByCampaign)}
                    className={`tab-button text-xs ${groupByCampaign ? 'active' : ''}`}
                >
                    {groupByCampaign ? '✓ ' : ''}Group by Campaign
                </button>
                <span className="text-xs text-slate-500 ml-auto">{jobs.length} total jobs</span>
            </div>

            {/* ============ JOB TABLE ============ */}
            {groupByCampaign ? (
                // Grouped view
                <div className="space-y-6">
                    {Array.from(campaignGroups.entries()).map(([campaignName, campaignJobs]) => (
                        <div key={campaignName}>
                            <div className="flex items-center gap-2 mb-3">
                                <h4 className="text-sm font-semibold text-slate-300">{campaignName}</h4>
                                <span className="text-[10px] text-slate-500">({campaignJobs.length} jobs)</span>
                            </div>
                            <JobTable
                                jobs={campaignJobs}
                                influencerMap={influencerMap}
                                getDuration={getDuration}
                                onErrorClick={setErrorModal}
                                showCampaign={false}
                            />
                        </div>
                    ))}
                </div>
            ) : (
                // Flat view
                <JobTable
                    jobs={jobs}
                    influencerMap={influencerMap}
                    getDuration={getDuration}
                    onErrorClick={setErrorModal}
                    showCampaign={true}
                />
            )}

            {/* ============ ERROR DETAIL MODAL ============ */}
            {errorModal && (
                <ErrorModal job={errorModal} onClose={() => setErrorModal(null)} />
            )}
        </div>
    );
}

// ===========================================================================
// Job Table Component
// ===========================================================================

function JobTable({
    jobs,
    influencerMap,
    getDuration,
    onErrorClick,
    showCampaign,
}: {
    jobs: Job[];
    influencerMap: Map<string, Influencer>;
    getDuration: (job: Job) => string;
    onErrorClick: (job: Job) => void;
    showCampaign: boolean;
}) {
    return (
        <div className="glass-panel overflow-hidden">
            <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-slate-900/50 border-b border-slate-800/60">
                            {showCampaign && <th className="p-4 text-[10px] uppercase font-bold text-slate-500 tracking-tighter">Campaign</th>}
                            <th className="p-4 text-[10px] uppercase font-bold text-slate-500 tracking-tighter">Job ID</th>
                            <th className="p-4 text-[10px] uppercase font-bold text-slate-500 tracking-tighter">Influencer</th>
                            <th className="p-4 text-[10px] uppercase font-bold text-slate-500 tracking-tighter">Status</th>
                            <th className="p-4 text-[10px] uppercase font-bold text-slate-500 tracking-tighter">Progress</th>
                            <th className="p-4 text-[10px] uppercase font-bold text-slate-500 tracking-tighter">Model</th>
                            <th className="p-4 text-[10px] uppercase font-bold text-slate-500 tracking-tighter">Cost</th>
                            <th className="p-4 text-[10px] uppercase font-bold text-slate-500 tracking-tighter">Duration</th>
                            <th className="p-4 text-[10px] uppercase font-bold text-slate-500 tracking-tighter">Created</th>
                            <th className="p-4 text-[10px] uppercase font-bold text-slate-500 tracking-tighter">Actions</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-900/50">
                        {jobs.length === 0 ? (
                            <tr>
                                <td colSpan={showCampaign ? 10 : 9} className="p-16 text-center text-slate-600 italic text-sm">
                                    No jobs found.
                                </td>
                            </tr>
                        ) : (
                            jobs.map((job) => (
                                <tr key={job.id} className="hover:bg-slate-800/10 transition-colors">
                                    {showCampaign && (
                                        <td className="p-4 text-xs text-slate-400">{job.campaign_name || 'Single'}</td>
                                    )}
                                    <td className="p-4">
                                        <span className="text-xs font-mono text-slate-400">{job.id.substring(0, 8)}</span>
                                    </td>
                                    <td className="p-4 text-xs text-slate-300">
                                        {influencerMap.get(job.influencer_id || '')?.name ?? '—'}
                                    </td>
                                    <td className="p-4">
                                        <button
                                            onClick={() => job.status === 'failed' ? onErrorClick(job) : undefined}
                                            className={`badge badge-${job.status === 'success' ? 'success' : job.status === 'failed' ? 'failed' : job.status === 'processing' ? 'processing' : 'pending'} ${job.status === 'failed' ? 'cursor-pointer hover:opacity-80' : ''}`}
                                        >
                                            {job.status}
                                        </button>
                                    </td>
                                    <td className="p-4">
                                        <div className="w-20 progress-bar">
                                            <div
                                                className={`progress-bar-fill ${job.status === 'success' ? 'bg-green-500' : job.status === 'failed' ? 'bg-red-500' : 'bg-blue-500'}`}
                                                style={{ width: `${job.status === 'success' ? 100 : job.status === 'failed' ? 100 : job.progress}%` }}
                                            />
                                        </div>
                                    </td>
                                    <td className="p-4 text-xs text-slate-400">{job.model_api || '—'}</td>
                                    <td className="p-4 text-xs font-medium text-green-400">
                                        {job.total_cost != null ? `$${Number(job.total_cost).toFixed(3)}` : '—'}
                                    </td>
                                    <td className="p-4 text-xs text-slate-400">{getDuration(job)}</td>
                                    <td className="p-4 text-xs text-slate-500">{new Date(job.created_at).toLocaleDateString()}</td>
                                    <td className="p-4">
                                        {job.final_video_url ? (
                                            <a
                                                href={job.final_video_url}
                                                target="_blank"
                                                rel="noopener noreferrer"
                                                className="text-xs text-blue-400 hover:text-blue-300 font-medium"
                                            >
                                                Preview
                                            </a>
                                        ) : job.status === 'failed' ? (
                                            <button
                                                onClick={() => onErrorClick(job)}
                                                className="text-xs text-red-400 hover:text-red-300 font-medium"
                                            >
                                                View Error
                                            </button>
                                        ) : (
                                            <span className="text-xs text-slate-600 italic">—</span>
                                        )}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

// ===========================================================================
// Error Detail Modal
// ===========================================================================

function ErrorModal({ job, onClose }: { job: Job; onClose: () => void }) {
    useEffect(() => {
        function handleEsc(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
        window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [onClose]);

    const suggestion = getTroubleshooting(job.error_message || '');

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
                <div className="p-6 space-y-5">
                    <div className="flex items-center justify-between">
                        <h3 className="font-semibold text-lg text-red-400">Job Failed</h3>
                        <button onClick={onClose} className="text-slate-500 hover:text-white transition-colors text-lg">✕</button>
                    </div>

                    <div>
                        <p className="text-[10px] uppercase text-slate-500 font-semibold mb-1">Job ID</p>
                        <p className="text-sm text-slate-300 font-mono">{job.id}</p>
                    </div>

                    {/* Troubleshooting */}
                    <div className="bg-blue-500/5 border border-blue-500/15 rounded-xl p-4">
                        <p className="text-[10px] uppercase text-blue-400 font-semibold mb-2">💡 Troubleshooting Suggestion</p>
                        <p className="text-sm text-slate-300 leading-relaxed">{suggestion}</p>
                    </div>

                    {/* Cost Breakdown */}
                    {job.total_cost != null && (
                        <div>
                            <p className="text-[10px] uppercase text-slate-500 font-semibold mb-2">💰 Cost Breakdown</p>
                            <div className="bg-slate-900 rounded-xl p-4 border border-slate-800/60 space-y-2">
                                {[
                                    { label: '🎬 Video Generation', value: job.cost_video },
                                    { label: '🎙️ Voice Generation', value: job.cost_voice },
                                    { label: '🎵 Music', value: job.cost_music },
                                    { label: '⚙️ Processing', value: job.cost_processing },
                                ].map((c) => (
                                    <div key={c.label} className="flex justify-between text-xs">
                                        <span className="text-slate-400">{c.label}</span>
                                        <span className="text-slate-300 font-medium">
                                            ${c.value != null ? Number(c.value).toFixed(3) : '0.000'}
                                        </span>
                                    </div>
                                ))}
                                <div className="border-t border-slate-700/50 pt-2 mt-2 flex justify-between text-sm">
                                    <span className="text-slate-300 font-semibold">Total</span>
                                    <span className="text-green-400 font-bold">${Number(job.total_cost).toFixed(3)}</span>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Error Message */}
                    <div>
                        <p className="text-[10px] uppercase text-slate-500 font-semibold mb-2">Full Error</p>
                        <pre className="text-xs text-red-400/80 bg-slate-900 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap max-h-60 border border-slate-800/60">
                            {job.error_message || 'No error message available.'}
                        </pre>
                    </div>

                    <button onClick={onClose} className="btn-secondary w-full">Close</button>
                </div>
            </div>
        </div>
    );
}
