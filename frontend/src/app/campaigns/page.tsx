'use client';

import { useState, useEffect, useCallback } from 'react';
import { creativeFetch } from '@/lib/creative-os-api';
import { formatDate } from '@/lib/utils';

interface PlanItem {
    id: string;
    slot_index: number;
    scheduled_at: string;
    asset_type: string;
    platforms: string[];
    caption?: string;
    status: string;
    job_id?: string;
    asset_url?: string;
    scheduled_post_id?: string;
    error?: string;
}

interface Campaign {
    id: string;
    name: string;
    goal?: string;
    status: string;
    start_date?: string;
    end_date?: string;
    created_at?: string;
    updated_at?: string;
}

interface CampaignDetail extends Campaign {
    items: PlanItem[];
}

const ITEM_TERMINAL = new Set(['scheduled', 'posted', 'failed', 'cancelled']);

const STATUS_COLOR: Record<string, string> = {
    planning: '#94A3B8',
    approved: '#337AFF',
    running: '#F59E0B',
    completed: '#10B981',
    failed: '#EF4444',
    cancelled: '#64748B',
    pending: '#94A3B8',
    generating: '#F59E0B',
    ready_to_post: '#337AFF',
    scheduled: '#10B981',
    posted: '#10B981',
};

function statusColor(status: string): string {
    return STATUS_COLOR[status] || '#94A3B8';
}

export default function CampaignsPage() {
    const [campaigns, setCampaigns] = useState<Campaign[]>([]);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [detail, setDetail] = useState<CampaignDetail | null>(null);
    const [loading, setLoading] = useState(true);
    const [cancelling, setCancelling] = useState(false);

    const loadList = useCallback(async () => {
        try {
            const data = await creativeFetch<Campaign[]>('/creative-os/campaigns/');
            setCampaigns(data);
            if (data.length > 0 && !selectedId) {
                setSelectedId(data[0].id);
            }
        } catch (e) {
            console.error(e);
        }
        setLoading(false);
    }, [selectedId]);

    const loadDetail = useCallback(async (id: string) => {
        try {
            const data = await creativeFetch<CampaignDetail>(`/creative-os/campaigns/${id}`);
            setDetail(data);
        } catch (e) {
            console.error(e);
        }
    }, []);

    useEffect(() => {
        loadList();
        const interval = setInterval(loadList, 10_000);
        return () => clearInterval(interval);
    }, [loadList]);

    useEffect(() => {
        if (!selectedId) {
            setDetail(null);
            return;
        }
        loadDetail(selectedId);
        const interval = setInterval(() => loadDetail(selectedId), 10_000);
        return () => clearInterval(interval);
    }, [selectedId, loadDetail]);

    const handleCancel = async () => {
        if (!selectedId) return;
        if (!confirm('Cancel this campaign? Pending items will stop; in-flight jobs keep running.')) return;
        setCancelling(true);
        try {
            await creativeFetch(`/creative-os/campaigns/${selectedId}/cancel`, { method: 'POST' });
            await loadList();
            await loadDetail(selectedId);
        } catch (e: unknown) {
            alert(e instanceof Error ? e.message : 'Cancel failed');
        }
        setCancelling(false);
    };

    if (loading) return <div className="text-[#4A5568] animate-pulse">Loading campaigns...</div>;

    if (campaigns.length === 0) {
        return (
            <div>
                <h1 className="text-3xl font-bold gradient-text mb-2">Campaigns</h1>
                <p className="text-[#4A5568] mb-8">Multi-day content plans orchestrated by the agent.</p>
                <div className="glass-panel rounded-xl p-12 text-center">
                    <p className="text-[#94A3B8] mb-2">No campaigns yet.</p>
                    <p className="text-[#4A5568] text-sm">
                        Ask the agent something like: &quot;30-day content plan for @product, 30 mixed assets, schedule on TikTok and Instagram.&quot;
                    </p>
                </div>
            </div>
        );
    }

    const items = detail?.items || [];
    const counts = items.reduce<Record<string, number>>((acc, it) => {
        acc[it.status] = (acc[it.status] || 0) + 1;
        return acc;
    }, {});
    const terminalCount = items.filter((it) => ITEM_TERMINAL.has(it.status)).length;

    return (
        <div>
            <h1 className="text-3xl font-bold gradient-text mb-2">Campaigns</h1>
            <p className="text-[#4A5568] mb-8">Multi-day content plans orchestrated by the agent.</p>

            <div className="grid grid-cols-[280px_1fr] gap-6">
                <div className="space-y-2">
                    {campaigns.map((c) => (
                        <button
                            key={c.id}
                            onClick={() => setSelectedId(c.id)}
                            className={`w-full text-left glass-panel rounded-lg p-4 transition-all ${
                                selectedId === c.id ? 'ring-2 ring-[#337AFF]' : 'hover:bg-white/60'
                            }`}
                        >
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-white font-semibold truncate">{c.name}</span>
                                <span
                                    className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase shrink-0 ml-2"
                                    style={{
                                        color: statusColor(c.status),
                                        backgroundColor: `${statusColor(c.status)}20`,
                                    }}
                                >
                                    {c.status}
                                </span>
                            </div>
                            <p className="text-xs text-[#94A3B8]">{formatDate(c.updated_at || c.created_at)}</p>
                        </button>
                    ))}
                </div>

                <div>
                    {detail ? (
                        <div className="glass-panel rounded-xl p-6">
                            <div className="flex items-start justify-between mb-6">
                                <div>
                                    <h2 className="text-xl font-bold text-white mb-1">{detail.name}</h2>
                                    {detail.goal && <p className="text-[#4A5568] text-sm">{detail.goal}</p>}
                                </div>
                                {detail.status !== 'cancelled' && detail.status !== 'completed' && (
                                    <button
                                        onClick={handleCancel}
                                        disabled={cancelling}
                                        className="px-4 py-2 text-sm bg-white/60 hover:bg-white/80 border border-[#E8ECF4] rounded-lg text-[#4A5568] disabled:opacity-50"
                                    >
                                        {cancelling ? 'Cancelling...' : 'Cancel'}
                                    </button>
                                )}
                            </div>

                            <div className="grid grid-cols-5 gap-3 mb-6">
                                {[
                                    { label: 'Total', value: items.length, color: 'text-white' },
                                    { label: 'Generating', value: counts.generating || 0, color: 'text-amber-400' },
                                    { label: 'Ready', value: counts.ready_to_post || 0, color: 'text-[#337AFF]' },
                                    { label: 'Scheduled', value: (counts.scheduled || 0) + (counts.posted || 0), color: 'text-green-400' },
                                    { label: 'Failed', value: counts.failed || 0, color: 'text-red-400' },
                                ].map((stat) => (
                                    <div key={stat.label} className="glass-panel rounded-lg p-3 text-center">
                                        <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                                        <p className="text-[#94A3B8] text-xs mt-1">{stat.label}</p>
                                    </div>
                                ))}
                            </div>

                            {items.length > 0 && (
                                <div className="mb-4">
                                    <div className="w-full h-2 bg-[#E8ECF4] rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-gradient-to-r from-blue-500 to-green-500 transition-all duration-500"
                                            style={{ width: `${(terminalCount / items.length) * 100}%` }}
                                        />
                                    </div>
                                    <p className="text-xs text-[#94A3B8] text-right mt-1">
                                        {terminalCount} / {items.length} items complete
                                    </p>
                                </div>
                            )}

                            <div className="space-y-2">
                                {items.map((item) => (
                                    <div key={item.id} className="glass-panel rounded-lg p-4 flex items-center gap-4">
                                        <span className="text-[#94A3B8] font-mono text-xs w-6 shrink-0">
                                            {item.slot_index + 1}
                                        </span>
                                        <span
                                            className="w-2 h-2 rounded-full shrink-0"
                                            style={{ backgroundColor: statusColor(item.status) }}
                                        />
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-3 flex-wrap">
                                                <span className="text-white text-sm font-medium">
                                                    {item.asset_type.replace(/_/g, ' ')}
                                                </span>
                                                <span className="text-[#94A3B8] text-xs">
                                                    {formatDate(item.scheduled_at)}
                                                </span>
                                                {item.platforms.length > 0 && (
                                                    <span className="text-[#4A5568] text-xs">
                                                        {item.platforms.join(', ')}
                                                    </span>
                                                )}
                                            </div>
                                            {item.caption && (
                                                <p className="text-[#4A5568] text-xs mt-1 truncate">{item.caption}</p>
                                            )}
                                            {item.error && (
                                                <p className="text-red-400 text-xs mt-1 truncate">{item.error}</p>
                                            )}
                                        </div>
                                        <span
                                            className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase shrink-0"
                                            style={{
                                                color: statusColor(item.status),
                                                backgroundColor: `${statusColor(item.status)}20`,
                                            }}
                                        >
                                            {item.status.replace(/_/g, ' ')}
                                        </span>
                                        {item.asset_url && (
                                            <a
                                                href={item.asset_url}
                                                target="_blank"
                                                rel="noreferrer"
                                                className="text-[#337AFF] hover:text-[#337AFF]/80 text-xs shrink-0"
                                            >
                                                View
                                            </a>
                                        )}
                                    </div>
                                ))}
                            </div>
                        </div>
                    ) : (
                        <div className="glass-panel rounded-xl p-12 text-center text-[#94A3B8]">
                            Select a campaign to see its plan.
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
