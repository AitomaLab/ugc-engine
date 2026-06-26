'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import { dedupeInfluencersByName } from '@/lib/utils';
import { supabase } from '@/lib/supabaseClient';
import type { AgentRef } from '@/lib/creative-os-api';
import { MentionAssetGrid } from '@/components/studio/MentionAssetGrid';
import { buildMentionRef } from '@/components/studio/mention-utils';
import type { MentionItem } from '@/components/studio/mention-utils';
import Modal from './Modal';
import { buildTemplateCreatorGroups } from './buildTemplateCreatorItems';

interface Props {
    onClose: () => void;
    onConfirm: (creator: AgentRef | null) => void;
    launching?: boolean;
    error?: string | null;
}

export default function TemplateCreatorPicker({ onClose, onConfirm, launching = false, error = null }: Props) {
    const { t } = useTranslation();
    const [loading, setLoading] = useState(true);
    const [influencers, setInfluencers] = useState<any[]>([]);
    const [clones, setClones] = useState<any[]>([]);
    const [selectedTag, setSelectedTag] = useState<string | null>(null);
    const [selectedRef, setSelectedRef] = useState<AgentRef | null>(null);

    useEffect(() => {
        let cancelled = false;
        (async () => {
            setLoading(true);
            try {
                const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
                const token = (await supabase.auth.getSession()).data.session?.access_token;
                const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
                const [infRes, cloneRes] = await Promise.all([
                    fetch(`${apiBase}/influencers`, { headers }).then((r) => (r.ok ? r.json() : [])),
                    fetch(`${apiBase}/api/clones`, { headers }).then((r) => (r.ok ? r.json() : [])),
                ]);
                const cloneRows = cloneRes || [];
                const clonesWithLooks = await Promise.all(
                    cloneRows.map(async (c: any) => {
                        try {
                            const looks = await fetch(`${apiBase}/api/clones/${c.id}/looks`, { headers })
                                .then((r) => (r.ok ? r.json() : []));
                            return { ...c, looks: looks || [] };
                        } catch {
                            return { ...c, looks: [] };
                        }
                    }),
                );
                if (!cancelled) {
                    setInfluencers(dedupeInfluencersByName(infRes || []));
                    setClones(clonesWithLooks);
                }
            } catch {
                if (!cancelled) {
                    setInfluencers([]);
                    setClones([]);
                }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, []);

    const mentionGroups = useMemo(
        () => buildTemplateCreatorGroups(influencers, clones),
        [influencers, clones],
    );

    const handlePick = useCallback((item: MentionItem) => {
        const ref = buildMentionRef(item);
        setSelectedTag(item.tag);
        setSelectedRef(ref);
    }, []);

    return (
        <div style={{ position: 'fixed', inset: 0, zIndex: 10001 }}>
            <Modal
                title={t('analytics.detail.template.pickerTitle')}
                onClose={launching ? () => {} : onClose}
                maxWidth={640}
                footer={
                    <>
                        <button
                            type="button"
                            onClick={onClose}
                            disabled={launching}
                            style={{
                                padding: '9px 16px',
                                borderRadius: '8px',
                                border: '1px solid var(--border)',
                                background: 'white',
                                color: 'var(--text-2)',
                                fontSize: '13px',
                                fontWeight: 600,
                                cursor: launching ? 'not-allowed' : 'pointer',
                                opacity: launching ? 0.6 : 1,
                            }}
                        >
                            {t('common.cancel')}
                        </button>
                        <button
                            type="button"
                            onClick={() => onConfirm(null)}
                            disabled={launching}
                            style={{
                                padding: '9px 16px',
                                borderRadius: '8px',
                                border: '1px solid var(--border)',
                                background: 'white',
                                color: 'var(--text-2)',
                                fontSize: '13px',
                                fontWeight: 600,
                                cursor: launching ? 'not-allowed' : 'pointer',
                                opacity: launching ? 0.6 : 1,
                            }}
                        >
                            {t('analytics.detail.template.pickerSkip')}
                        </button>
                        <button
                            type="button"
                            onClick={() => onConfirm(selectedRef)}
                            disabled={launching || !selectedRef}
                            style={{
                                padding: '9px 16px',
                                borderRadius: '8px',
                                border: 'none',
                                background: selectedRef && !launching
                                    ? 'linear-gradient(135deg, #34D399 0%, #2DD4BF 100%)'
                                    : 'rgba(138,147,176,0.35)',
                                color: 'white',
                                fontSize: '13px',
                                fontWeight: 700,
                                cursor: launching || !selectedRef ? 'not-allowed' : 'pointer',
                            }}
                        >
                            {launching
                                ? t('analytics.detail.template.launching')
                                : t('analytics.detail.template.pickerConfirm')}
                        </button>
                    </>
                }
            >
                <p style={{ margin: '0 0 14px', fontSize: '13px', color: 'var(--text-2)', lineHeight: 1.5 }}>
                    {t('analytics.detail.template.pickerSubtitle')}
                </p>
                {error && (
                    <p style={{ margin: '0 0 12px', fontSize: '13px', color: '#DC2626', lineHeight: 1.45 }}>
                        {error}
                    </p>
                )}
                <MentionAssetGrid
                    groups={mentionGroups}
                    allowedTypes={['influencer', 'clone']}
                    variant="inline"
                    active={!launching}
                    loading={loading}
                    emptyLabel={t('creativeOs.agent.selectorNoCreators')}
                    selectedTag={selectedTag}
                    onPick={handlePick}
                />
            </Modal>
        </div>
    );
}
