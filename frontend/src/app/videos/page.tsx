'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { apiFetch, formatDate } from '@/lib/utils';
import { VideoJob, Influencer } from '@/lib/types';
import Select from '@/components/ui/Select';
import MediaPreviewModal from '@/components/ui/MediaPreviewModal';
import SchedulePostModal from '@/components/modals/SchedulePostModal';
import { useProgressiveList } from '@/hooks/useProgressiveList';
import { useTranslation } from '@/lib/i18n';

export default function VideosPage() {
    const { t } = useTranslation();
    const [jobs, setJobs] = useState<VideoJob[]>([]);
    const [influencers, setInfluencers] = useState<Influencer[]>([]);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [influencerFilter, setInfluencerFilter] = useState('');
    const [statusFilter, setStatusFilter] = useState('');
    const [campaignFilter, setCampaignFilter] = useState('');
    const [sortOrder, setSortOrder] = useState('newest');
    const [previewAssetUrl, setPreviewAssetUrl] = useState<string | null>(null);
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [copiedFeedback, setCopiedFeedback] = useState(false);
    const [scheduleModalOpen, setScheduleModalOpen] = useState(false);

    const [clones, setClones] = useState<any[]>([]);

    const fetchData = useCallback(async () => {
        try {
            const [jobsData, infData, clonesData] = await Promise.all([
                apiFetch<any[]>('/jobs?limit=200&include_clones=true'),
                apiFetch<Influencer[]>('/influencers'),
                apiFetch<any[]>('/api/clones').catch(() => []),
            ]);
            setJobs(jobsData);
            setInfluencers(infData);
            setClones(clonesData);
        } catch (err) {
            console.error('Videos fetch error:', err);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { fetchData(); }, [fetchData]);

    // Poll every 5s while there are processing/pending jobs
    useEffect(() => {
        const hasActiveJobs = jobs.some(j => j.status === 'processing' || j.status === 'pending');
        if (!hasActiveJobs) return;
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, [jobs, fetchData]);

    // Re-fetch when user switches projects
    useEffect(() => {
        const handler = () => { setLoading(true); fetchData(); };
        window.addEventListener('projectChanged', handler);
        return () => window.removeEventListener('projectChanged', handler);
    }, [fetchData]);

    async function handleDelete(jobId: string) {
        if (!confirm('Delete this video? This cannot be undone.')) return;
        try {
            // Find the job to check if it's a clone job
            const job = jobs.find(j => j.id === jobId);
            if (job && (job as any)._source === 'clone') {
                await apiFetch(`/api/clone-jobs/${jobId}`, { method: 'DELETE' });
            } else {
                await apiFetch(`/jobs/${jobId}`, { method: 'DELETE' });
            }
            setJobs(prev => prev.filter(j => j.id !== jobId));
            setSelectedIds(prev => { const next = new Set(prev); next.delete(jobId); return next; });
        } catch (err) { console.error('Delete error:', err); }
    }

    function toggleSelect(id: string) {
        setSelectedIds(prev => {
            const next = new Set(prev);
            next.has(id) ? next.delete(id) : next.add(id);
            return next;
        });
    }
    function clearSelection() { setSelectedIds(new Set()); }
    function bulkDownload() {
        jobs.filter(j => selectedIds.has(j.id) && j.final_video_url).forEach(j => window.open(j.final_video_url!));
    }
    async function bulkShare() {
        const urls = jobs.filter(j => selectedIds.has(j.id) && j.final_video_url).map(j => j.final_video_url!);
        await navigator.clipboard.writeText(urls.join('\n'));
        setCopiedFeedback(true);
        setTimeout(() => setCopiedFeedback(false), 2000);
    }

    const influencerMap = new Map(influencers.map((i) => [i.id, i]));
    const campaignNames = [...new Set(jobs.map(j => j.campaign_name).filter(Boolean))] as string[];

    let filteredJobs = jobs;

    if (search) {
        const q = search.toLowerCase();
        filteredJobs = filteredJobs.filter(job =>
            (influencerMap.get(job.influencer_id || '')?.name || '').toLowerCase().includes(q) ||
            (job.campaign_name || '').toLowerCase().includes(q) ||
            job.id.toLowerCase().includes(q)
        );
    }

    if (influencerFilter) {
        filteredJobs = filteredJobs.filter(job => job.influencer_id === influencerFilter);
    }

    if (statusFilter) {
        filteredJobs = filteredJobs.filter(job => job.status === statusFilter);
    }

    if (campaignFilter) {
        filteredJobs = filteredJobs.filter(job => job.campaign_name === campaignFilter);
    }

    filteredJobs.sort((a, b) => {
        const da = new Date(a.created_at || 0).getTime();
        const db = new Date(b.created_at || 0).getTime();
        return sortOrder === 'newest' ? db - da : da - db;
    });

    const { visibleItems: visibleJobs, sentinelRef, hasMore } = useProgressiveList(filteredJobs, 12);

    if (loading) {
        return <div className='content-area'><div className='text-[#94A3B8] text-sm italic animate-pulse py-12 text-center'>{t('common.loading')}</div></div>;
    }

    return (
        <div className='content-area'>
            <div className='page-header'>
                <h1>{t('videos.title')}</h1>
                <p>{t('videos.subtitle')}</p>
            </div>

            <div className='asset-toolbar border-b pb-6 mb-8 mt-6 flex justify-between items-center' style={{ borderBottomColor: 'var(--border)' }}>
                <div className='asset-toolbar-left flex gap-3 flex-1' style={{ display: 'flex', gap: '12px', flex: 1, alignItems: 'center' }}>
                    <div className='search-box' style={{ flex: 1, maxWidth: '280px', display: 'flex', alignItems: 'center', gap: '8px', background: 'white', border: '1px solid var(--border)', borderRadius: '8px', padding: '8px 12px' }}>
                        <svg viewBox='0 0 24 24' style={{ width: '16px', height: '16px', stroke: 'var(--text-3)', fill: 'none', strokeWidth: 2 }}><circle cx='11' cy='11' r='8' /><line x1='21' y1='21' x2='16.65' y2='16.65' /></svg>
                        <input type='text' style={{ background: 'transparent', border: 'none', outline: 'none', width: '100%', fontSize: '14px', color: 'var(--text-1)' }} placeholder={t('videos.searchPlaceholder')} value={search} onChange={e => setSearch(e.target.value)} />
                    </div>
                    <Select
                        className="filter-select"
                        value={influencerFilter}
                        onChange={setInfluencerFilter}
                        placeholder={t('videos.allCreators')}
                        options={[
                            { value: '', label: t('videos.allCreators') },
                            ...influencers.map(inf => ({ value: inf.id, label: inf.name })),
                            ...(clones.length > 0 ? [
                                { value: '__divider_clones__', label: '── AI Clones ──' },
                                ...clones.map((c: any) => ({ value: `clone_${c.id}`, label: c.name })),
                            ] : []),
                        ]}
                    />

                    <Select
                        className="filter-select"
                        value={statusFilter}
                        onChange={setStatusFilter}
                        placeholder={t('videos.allStatus')}
                        options={[
                            { value: '', label: t('videos.allStatus') },
                            { value: 'success', label: t('common.completed') },
                            { value: 'processing', label: t('common.processing') },
                            { value: 'pending', label: t('common.queued') },
                            { value: 'failed', label: t('common.failed') }
                        ]}
                    />

                    <Select
                        className="filter-select"
                        value={campaignFilter}
                        onChange={setCampaignFilter}
                        placeholder={t('videos.allCampaigns')}
                        options={[
                            { value: '', label: t('videos.allCampaigns') },
                            ...campaignNames.map(name => ({ value: name, label: name }))
                        ]}
                    />

                    <Select
                        className="filter-select"
                        value={sortOrder}
                        onChange={setSortOrder}
                        options={[
                            { value: 'newest', label: t('videos.newestFirst') },
                            { value: 'oldest', label: t('videos.oldestFirst') }
                        ]}
                    />
                </div>
                <Link href='/create' className='btn-primary' style={{ padding: '8px 16px', fontWeight: 600, fontSize: '14px', height: '38px', display: 'flex', alignItems: 'center' }}>
                    {t('videos.createVideo')}
                </Link>
            </div>

            {filteredJobs.length === 0 ? (
                <div className='empty-state'>
                    <div className='empty-icon'>
                        <svg viewBox='0 0 24 24'><rect x='2' y='3' width='20' height='14' rx='2' /><path d='M8 21h8M12 17v4' /></svg>
                    </div>
                    <div className='empty-title'>{t('videos.noVideos')}</div>
                    <div className='empty-sub'>{t('videos.subtitle')}</div>
                    <Link href='/create' className='btn-primary'>{t('header.createVideo')}</Link>
                </div>
            ) : (<>
                {selectedIds.size > 0 && (
                    <div className="bulk-bar">
                        <span className="bulk-bar-count">{selectedIds.size} {t('videos.selected')}</span>
                        <div className="bulk-bar-actions">
                            <button className="btn-secondary" onClick={() => setSelectedIds(new Set(filteredJobs.filter(j => j.final_video_url).map(j => j.id)))}>{t('videos.selectAll')}</button>
                            <button className="btn-secondary" onClick={bulkDownload}>
                                <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="7 10 12 15 17 10" /><line x1="12" y1="15" x2="12" y2="3" /></svg>
                                {t('videos.download')}
                            </button>
                            <button className="btn-secondary" onClick={bulkShare}>
                                <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" /></svg>
                                {copiedFeedback ? t('videos.copied') : t('videos.shareLinks')}
                            </button>
                            <button className="btn-secondary" onClick={() => setScheduleModalOpen(true)} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                                <svg viewBox="0 0 24 24" style={{ width: 14, height: 14, fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg>
                                {t('videos.scheduleBtn')}
                            </button>
                            <button className="btn-secondary" onClick={clearSelection} style={{ color: 'var(--text-3)' }}>{t('common.cancel')}</button>
                        </div>
                    </div>
                )}
                <div className='video-grid'>
                    {visibleJobs.map((job, i) => {
                        const statusLabel = job.status === 'success' ? t('common.done') : job.status === 'processing' ? t('common.processing') + '...' : job.status === 'pending' ? t('common.queued') : t('common.failed');
                        return (
                            <div key={job.id} className='video-card'>
                                <div
                                    className={`video-thumb grad-${(i % 5) + 1}`}
                                    style={{ cursor: job.final_video_url ? 'zoom-in' : 'default' }}
                                    onClick={() => job.final_video_url && setPreviewAssetUrl(job.final_video_url)}
                                >
                                    {job.final_video_url ? (
                                        <video src={job.final_video_url} style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', inset: 0 }} muted loop playsInline preload="metadata" />
                                    ) : (job.status === 'processing' || job.status === 'pending') ? (
                                        <div style={{ position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: '8px' }}>
                                            <div className="processing-spinner" />
                                            <span style={{ fontSize: '12px', fontWeight: 600, color: 'white', opacity: 0.9 }}>
                                                {job.status === 'pending' ? t('common.queued') : t('common.processing')}
                                            </span>
                                            {job.status === 'processing' && job.created_at && (() => {
                                                const elapsed = Math.round((Date.now() - new Date(job.created_at).getTime()) / 60000);
                                                const est = (job as any).product_type === 'digital' ? 5 : 7;
                                                const remaining = Math.max(est - elapsed, 0);
                                                return <span style={{ fontSize: '11px', color: 'white', opacity: 0.6 }}>{remaining > 0 ? (t('videos.timeLeft') || '~{min}m left').replace('{min}', String(remaining)) : t('videos.finishing')}</span>;
                                            })()}
                                        </div>
                                    ) : null}
                                    <button className={`card-select-btn ${selectedIds.has(job.id) ? 'selected' : ''}`} onClick={(e) => { e.stopPropagation(); toggleSelect(job.id); }} title="Select video">
                                        {selectedIds.has(job.id) && <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12" /></svg>}
                                    </button>
                                    <button className="card-delete-btn" onClick={(e) => { e.stopPropagation(); handleDelete(job.id); }} title="Delete video">
                                        <svg viewBox="0 0 24 24"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                                    </button>
                                </div>
                                <div className='video-info' style={{ paddingBottom: '12px' }}>
                                    <div className='video-name' style={{ fontWeight: 700 }}>
                                        {(job as any)._source === 'clone'
                                            ? ((job as any).clone_name || 'AI Clone')
                                            : (influencerMap.get(job.influencer_id ?? '')?.name ?? 'Unknown')}
                                        {' — '}{job.campaign_name || 'Single'}
                                    </div>
                                    <div className='video-date' style={{ marginTop: '4px' }}>{(job as any).product_type === 'physical' ? 'Physical' : 'Digital'} 15s · {formatDate(job.created_at ?? '')}</div>
                                </div>
                                <div className='video-info' style={{ display: 'flex', gap: '8px', paddingTop: 0, paddingBottom: '12px', marginTop: 'auto' }}>
                                    {job.final_video_url ? (
                                        <>
                                            <button style={{ flex: 1, padding: '6px 0', backgroundColor: 'var(--surface-hover)', color: 'var(--blue)', borderRadius: '4px', fontSize: '12px', fontWeight: 600, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', border: '1px solid rgba(51,122,255,0.15)', cursor: 'pointer' }} onClick={() => window.open(job.final_video_url!)}>
                                                <svg viewBox='0 0 24 24' style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><path d='M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4' /><polyline points='7 10 12 15 17 10' /><line x1='12' y1='15' x2='12' y2='3' /></svg>
                                                {t('videos.save')}
                                            </button>
                                            <button style={{ flex: 1, padding: '6px 0', backgroundColor: 'transparent', color: 'var(--text-2)', borderRadius: '4px', fontSize: '12px', fontWeight: 600, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '6px', border: '1px solid var(--border)', cursor: 'pointer' }}>
                                                <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: 2 }}><circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" /><line x1="8.59" y1="13.51" x2="15.42" y2="17.49" /><line x1="15.41" y1="6.51" x2="8.59" y2="10.49" /></svg>
                                                {t('videos.share')}
                                            </button>
                                        </>
                                    ) : (
                                        <div style={{ width: '100%', textAlign: 'center' }}>
                                            <button style={{ width: '90%', margin: '0 auto', padding: '6px 0', backgroundColor: 'transparent', color: 'var(--text-2)', borderRadius: '20px', fontSize: '12px', fontWeight: 600, border: '1px solid var(--border)', opacity: 0.6, cursor: 'not-allowed' }}>
                                                {statusLabel.replace('...', '')}...
                                            </button>
                                        </div>
                                    )}
                                </div>
                            </div>
                        );
                    })}
                </div>
                {hasMore && (
                    <div ref={sentinelRef} style={{ height: '1px', marginTop: '8px' }} />
                )}
            </>)}

            <MediaPreviewModal
                isOpen={!!previewAssetUrl}
                onClose={() => setPreviewAssetUrl(null)}
                src={previewAssetUrl || ''}
                type="mixed"
            />
            <SchedulePostModal
                isOpen={scheduleModalOpen}
                onClose={() => setScheduleModalOpen(false)}
                preSelectedIds={selectedIds}
            />
        </div>
    );
}
