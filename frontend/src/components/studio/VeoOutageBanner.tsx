'use client';

import { useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import MediaPreviewModal from '@/components/ui/MediaPreviewModal';
import {
    VEO_KIE_OUTAGE_PROOF_SRC,
    VEO_UGC_OUTAGE_BANNER_ENABLED,
} from '@/lib/service-status';

function WarningIcon() {
    return (
        <svg
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#B45309"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden
        >
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
            <line x1="12" y1="9" x2="12" y2="13" />
            <line x1="12" y1="17" x2="12.01" y2="17" />
        </svg>
    );
}

export function VeoOutageBanner() {
    const { t } = useTranslation();
    const [showProof, setShowProof] = useState(false);

    if (!VEO_UGC_OUTAGE_BANNER_ENABLED) return null;

    return (
        <>
            <div
                role="status"
                style={{
                    width: '100%',
                    flexShrink: 0,
                    borderBottom: '1px solid rgba(245, 158, 11, 0.35)',
                    background: 'rgba(245, 158, 11, 0.10)',
                }}
            >
                <div
                    style={{
                        width: '100%',
                        padding: '12px 24px',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '12px',
                        flexWrap: 'wrap',
                        boxSizing: 'border-box',
                    }}
                >
                    <div style={{ paddingTop: '2px', flexShrink: 0 }}>
                        <WarningIcon />
                    </div>
                    <div style={{ flex: '1 1 200px', minWidth: 0 }}>
                        <p style={{
                            margin: 0,
                            fontSize: '13px',
                            fontWeight: 700,
                            color: '#92400E',
                            lineHeight: 1.4,
                        }}>
                            {t('creativeOs.veoOutage.title')}
                        </p>
                        <p style={{
                            margin: '4px 0 0',
                            fontSize: '12px',
                            fontWeight: 500,
                            color: '#B45309',
                            lineHeight: 1.5,
                        }}>
                            {t('creativeOs.veoOutage.body')}
                        </p>
                    </div>
                    <button
                        type="button"
                        onClick={() => setShowProof(true)}
                        style={{
                            flexShrink: 0,
                            alignSelf: 'center',
                            padding: '6px 12px',
                            borderRadius: '8px',
                            border: '1px solid rgba(245, 158, 11, 0.5)',
                            background: 'rgba(255, 255, 255, 0.65)',
                            color: '#B45309',
                            fontSize: '12px',
                            fontWeight: 600,
                            cursor: 'pointer',
                            whiteSpace: 'nowrap',
                            transition: 'background 0.15s ease',
                        }}
                        onMouseEnter={(e) => {
                            e.currentTarget.style.background = 'rgba(245, 158, 11, 0.12)';
                        }}
                        onMouseLeave={(e) => {
                            e.currentTarget.style.background = 'rgba(255, 255, 255, 0.65)';
                        }}
                    >
                        {t('creativeOs.veoOutage.viewProof')}
                    </button>
                </div>
            </div>

            <MediaPreviewModal
                isOpen={showProof}
                onClose={() => setShowProof(false)}
                src={VEO_KIE_OUTAGE_PROOF_SRC}
                type="image"
            />
        </>
    );
}
