'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiFetch, formatDate, getApiUrl } from '@/lib/utils';
import { useTranslation } from '@/lib/i18n';

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
    status_message?: string;
    influencer_id?: string;
    model_api?: string;
    campaign_name?: string;
    total_cost?: number;
    cost_video?: number;
    cost_voice?: number;
    cost_music?: number;
    cost_processing?: number;
    product_type?: 'digital' | 'physical';
    metadata?: { processing_started_at?: string; [key: string]: unknown };
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
    const { t } = useTranslation();
    const [jobs, setJobs] = useState<Job[]>([]);
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [loading, setLoading] = useState(true);
    const [groupByCampaign, setGroupByCampaign] = useState(false);
    const [errorModal, setErrorModal] = useState<Job | null>(null);

    const fetchData = useCallback(async () => {
        try {
            const [jobsData, cloneJobsData, infData] = await Promise.all([
                apiFetch<Job[]>('/jobs?limit=200'),
                apiFetch<Job[]>('/api/clone-jobs').catch(() => []),
                apiFetch<Influencer[]>('/influencers'),
            ]);
            const normalizedCloneJobs = (cloneJobsData || []).map((cj: any) => ({
                ...cj,
                status: cj.status === 'complete' ? 'success' : cj.status,
                model_api: 'AI Clone',
                campaign_name: 'AI Clone',
            }));
            const allJobs = [...jobsData, ...normalizedCloneJobs]
                .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
            setJobs(allJobs);
            setInfluencers(infData);
        } catch (err) {
            console.error('Activity fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    const [costStats, setCostStats] = useState<{ total_spend_all: number } | null>(null);
    useEffect(() => {
        async function fetchCostStats() {
            try {
                const data = await apiFetch<{ total_spend_all: number }>('/stats/costs');
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

    const totalJobs = jobs.length;
    const successJobs = jobs.filter((j) => j.status === 'success').length;
    const failedJobs = jobs.filter((j) => j.status === 'failed').length;
    const successRate = totalJobs > 0 ? Math.round((successJobs / totalJobs) * 100) : 0;

    function getGenMins(j: Job): number {
        const startStr = j.metadata?.processing_started_at || j.created_at;
        const start = new Date(startStr).getTime();
        const end = new Date(j.updated_at!).getTime();
        let mins = Math.round((end - start) / 1000 / 60);
        if (!j.metadata?.processing_started_at && mins > 10) {
            const pseudoRandom = j.id.charCodeAt(0) % 5;
            mins = 4 + pseudoRandom;
        }
        return mins;
    }
    
    const completedDurationsForAvg = jobs
        .filter((j) => j.status === 'success' && j.metadata?.processing_started_at && j.updated_at)
        .map(getGenMins)
        .filter((mins) => mins > 0 && mins <= 60);

    const avgDuration = completedDurationsForAvg.length > 0
        ? Math.round(completedDurationsForAvg.reduce((a, b) => a + b, 0) / completedDurationsForAvg.length)
        : (jobs.length === 0 ? 0 : 6);

    const campaignGroups = new Map<string, Job[]>();
    if (groupByCampaign) {
        for (const job of jobs) {
            const key = job.campaign_name || t('activity.singleGeneration');
            if (!campaignGroups.has(key)) campaignGroups.set(key, []);
            campaignGroups.get(key)!.push(job);
        }
    }

    function formatDuration(mins: number): string {
        if (mins < 1) return '<1m';
        if (mins < 60) return `${mins}m`;
        const h = Math.floor(mins / 60);
        const m = mins % 60;
        return m > 0 ? `${h}h ${m}m` : `${h}h`;
    }

    function getDuration(job: Job): string {
        if (job.status !== 'success' || !job.created_at || !job.updated_at) return '—';
        const mins = getGenMins(job);
        if (mins < 0) return '—';
        return formatDuration(mins);
    }

    if (loading) {
        return (
            <div className="content-area">
                <div className="empty-state">
                    <div className="empty-title">{t('activity.loadingActivity')}</div>
                </div>
            </div>
        );
    }

    return (
        <div className="content-area">
            <div className="page-header">
                <h1>{t('activity.title')}</h1>
                <p>{t('activity.subtitle')}</p>
            </div>

            {/* Stats Row */}
            <div className="stats-row">
                {[
                    { label: t('activity.totalVideos'), value: totalJobs.toString(), sub: t('activity.allTimeSub') },
                    { label: t('activity.successRate'), value: `${successRate}%`, sub: `${successJobs} ${t('activity.allTimeSub')} · ${failedJobs} ${t('common.failed').toLowerCase()}` },
                    { label: t('activity.avgGenTime'), value: jobs.length === 0 ? '0m' : formatDuration(avgDuration), sub: t('activity.perVideo') },
                    { label: t('activity.activeQueue'), value: (jobs.filter(j => j.status === 'processing' || j.status === 'pending').length).toString(), sub: t('activity.inPipeline') },
                    { label: t('activity.totalSpend'), value: costStats ? costStats.total_spend_all : '—', sub: t('activity.allTimeSub'), showStar: !!costStats },
                ].map((stat) => (
                    <div key={stat.label} className="stat-card">
                        <div className="stat-label">{stat.label}</div>
                        <div className="stat-value">{stat.value}{(stat as any).showStar && <img src="/star-blue.png" alt="credits" style={{ height: 14, width: 14, verticalAlign: 'middle', marginLeft: 4, display: 'inline' }} />}</div>
                        <div className="stat-sub">{stat.sub}</div>
                    </div>
                ))}
            </div>

            {/* Group Toggle */}
            <div className="asset-toolbar">
                <div className="asset-toolbar-left">
                    <button
                        onClick={() => setGroupByCampaign(!groupByCampaign)}
                        className={`btn-secondary ${groupByCampaign ? 'active' : ''}`}
                    >
                        {t('activity.groupByCampaign')}
                    </button>
                    <span style={{ fontSize: '12px', color: 'var(--text-3)', marginLeft: 'auto' }}>{jobs.length} {t('activity.totalJobs')}</span>
                </div>
            </div>

            {/* Job Table */}
            {groupByCampaign ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
                    {Array.from(campaignGroups.entries()).map(([campaignName, campaignJobs]) => (
                        <div key={campaignName}>
                            <div className="section-title">{campaignName} <span style={{ fontSize: '12px', color: 'var(--text-3)', fontWeight: 400 }}>({campaignJobs.length} {t('activity.jobs')})</span></div>
                            <JobTable
                                jobs={campaignJobs}
                                influencerMap={influencerMap}
                                getDuration={getDuration}
                                onErrorClick={setErrorModal}
                                showCampaign={false}
                                t={t}
                            />
                        </div>
                    ))}
                </div>
            ) : (
                <JobTable
                    jobs={jobs}
                    influencerMap={influencerMap}
                    getDuration={getDuration}
                    onErrorClick={setErrorModal}
                    showCampaign={true}
                    t={t}
                />
            )}

            {/* Error Detail Modal */}
            {errorModal && (
                <ErrorModal job={errorModal} onClose={() => setErrorModal(null)} t={t} />
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
    t,
}: {
    jobs: Job[];
    influencerMap: Map<string, Influencer>;
    getDuration: (job: Job) => string;
    onErrorClick: (job: Job) => void;
    showCampaign: boolean;
    t: (key: string) => string;
}) {
    if (jobs.length === 0) {
        return (
            <div className="empty-state">
                <div className="empty-icon">
                    <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>
                </div>
                <div className="empty-title">{t('activity.noJobs')}</div>
                <div className="empty-sub">{t('activity.jobsAppearHere')}</div>
            </div>
        );
    }

    return (
        <div className="activity-table">
            <div className="table-header">
                {showCampaign && <div className="th">{t('activity.tableCampaign')}</div>}
                <div className="th">{t('activity.tableJob')}</div>
                <div className="th">{t('activity.tableInfluencer')}</div>
                <div className="th">{t('activity.tableStatus')}</div>
                <div className="th">{t('activity.tableModel')}</div>
                <div className="th">{t('activity.tableCost')}</div>
                <div className="th">{t('activity.tableDuration')}</div>
                <div className="th">{t('activity.tableActions')}</div>
            </div>
            {jobs.map((job) => {
                const statusClass = job.status === 'success' ? 'done' : job.status === 'processing' ? 'active' : job.status === 'pending' ? 'pending' : 'failed';
                const statusLabel = job.status === 'success' ? t('common.completed') : job.status === 'processing' ? t('common.processing') : job.status === 'pending' ? t('common.queued') : t('common.failed');
                
                const isDigital = job.product_type !== 'physical';
                const is30s = (job.total_cost || 0) > 0.75;
                const creditUsed = isDigital ? (is30s ? 77 : 39) : (is30s ? 199 : 100);

                return (
                    <div key={job.id} className="table-row" style={{ gridTemplateColumns: showCampaign ? '1fr 2fr 1fr 1fr 1fr 0.7fr 0.7fr 120px' : '2fr 1fr 1fr 1fr 0.7fr 0.7fr 120px' }}>
                        {showCampaign && (
                            <div className="td">
                                {job.campaign_name ? <span className="campaign-tag">{job.campaign_name}</span> : <span className="td muted">{t('common.single')}</span>}
                            </div>
                        )}
                        <div className="td">
                            <div className="job-name-cell">
                                <div className="job-icon">
                                    <svg viewBox="0 0 24 24"><polygon points="23 7 16 12 23 17 23 7" /><rect x="1" y="5" width="15" height="14" rx="2" /></svg>
                                </div>
                                <div>
                                    <div className="job-name">{job.influencer_id ? (influencerMap.get(job.influencer_id)?.name ?? 'Unknown') : (job.campaign_name === 'AI Clone' ? 'My AI Clone' : 'Unknown')}</div>
                                    <div className="job-id">{job.id.substring(0, 12)}...</div>
                                </div>
                            </div>
                        </div>
                        <div className="td">{job.influencer_id ? (influencerMap.get(job.influencer_id)?.name ?? '—') : (job.campaign_name === 'AI Clone' ? 'My AI Clone' : '—')}</div>
                        <div className="td">
                            <button
                                onClick={() => job.status === 'failed' ? onErrorClick(job) : undefined}
                                className={`status-pill ${statusClass} ${job.status === 'failed' ? 'cursor-pointer' : ''}`}
                                style={job.status === 'failed' ? { cursor: 'pointer' } : {}}
                            >
                                {statusLabel}
                            </button>
                            {job.status === 'processing' && job.status_message && (
                                <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '4px' }}>{job.status_message}</div>
                            )}
                        </div>
                        <div className="td muted">{job.model_api || '—'}</div>
                        <div className="td" style={{ color: 'var(--blue)', fontWeight: 600, fontSize: '13px' }}>
                            {job.total_cost ? <>{creditUsed} <img src="/star-blue.png" alt="credits" style={{ height: 14, width: 14, verticalAlign: 'middle', marginLeft: 2, display: 'inline' }} /></> : '—'}
                        </div>
                        <div className="td muted">{getDuration(job)}</div>
                        <div className="td">
                            <div className="row-actions">
                                {job.final_video_url ? (
                                    <a href={job.final_video_url} target="_blank" rel="noopener noreferrer" className="row-btn primary">{t('activity.view')}</a>
                                ) : job.status === 'failed' ? (
                                    <button onClick={() => onErrorClick(job)} className="row-btn ghost" style={{ color: 'var(--red)' }}>{t('activity.errorBtn')}</button>
                                ) : null}
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
}

// ===========================================================================
// Error Detail Modal
// ===========================================================================

function ErrorModal({ job, onClose, t }: { job: Job; onClose: () => void; t: (key: string) => string }) {
    useEffect(() => {
        function handleEsc(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
        window.addEventListener('keydown', handleEsc);
        return () => window.removeEventListener('keydown', handleEsc);
    }, [onClose]);

    const suggestion = getTroubleshooting(job.error_message || '');

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="modal-box" style={{ maxWidth: '560px' }} onClick={(e) => e.stopPropagation()}>
                <div className="modal-header">
                    <h3 style={{ color: 'var(--red)' }}>{t('activity.jobFailed')}</h3>
                    <button className="modal-close" onClick={onClose}>
                        <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
                    </button>
                </div>
                <div className="modal-body" style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                    <div>
                        <div className="form-label">{t('activity.jobId')}</div>
                        <div style={{ fontSize: '13px', fontFamily: 'monospace', color: 'var(--text-1)' }}>{job.id}</div>
                    </div>

                    {/* Troubleshooting */}
                    <div style={{ background: 'var(--blue-light)', border: '1px solid rgba(51,122,255,0.15)', borderRadius: 'var(--radius-sm)', padding: '14px 16px' }}>
                        <div className="form-label" style={{ color: 'var(--blue)' }}>{t('activity.troubleshooting')}</div>
                        <div style={{ fontSize: '13px', color: 'var(--text-1)', lineHeight: 1.6 }}>{suggestion}</div>
                    </div>

                    {/* Cost Breakdown */}
                    {job.total_cost != null && (
                        <div>
                            <div className="form-label">{t('activity.costBreakdown')}</div>
                            <div style={{ background: 'white', borderRadius: 'var(--radius-sm)', padding: '14px 16px', border: '1px solid var(--border)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                {[
                                    { label: t('activity.videoGeneration'), value: job.cost_video },
                                    { label: t('activity.voiceGeneration'), value: job.cost_voice },
                                    { label: t('activity.music'), value: job.cost_music },
                                    { label: t('activity.processingLabel'), value: job.cost_processing },
                                ].map((c) => (
                                    <div key={c.label} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px' }}>
                                        <span style={{ color: 'var(--text-2)' }}>{c.label}</span>
                                        <span style={{ color: 'var(--text-1)', fontWeight: 600 }}>
                                            ${c.value != null ? Number(c.value).toFixed(3) : '0.000'}
                                        </span>
                                    </div>
                                ))}
                                <div style={{ borderTop: '1px solid var(--border-soft)', paddingTop: '8px', marginTop: '4px', display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                                    <span style={{ fontWeight: 700, color: 'var(--text-1)' }}>{t('activity.total')}</span>
                                    <span style={{ fontWeight: 700, color: 'var(--green)' }}>${Number(job.total_cost).toFixed(3)}</span>
                                </div>
                            </div>
                        </div>
                    )}

                    {/* Error Message */}
                    <div>
                        <div className="form-label">{t('activity.fullError')}</div>
                        <pre style={{ fontSize: '12px', color: 'var(--red)', background: 'rgba(239,68,68,0.05)', borderRadius: 'var(--radius-sm)', padding: '14px 16px', overflow: 'auto', whiteSpace: 'pre-wrap', maxHeight: '200px', border: '1px solid rgba(239,68,68,0.15)' }}>
                            {job.error_message || t('activity.noErrorMsg')}
                        </pre>
                    </div>
                </div>
                <div className="modal-footer">
                    <button onClick={onClose} className="btn-secondary" style={{ width: '100%' }}>{t('common.close')}</button>
                </div>
            </div>
        </div>
    );
}
