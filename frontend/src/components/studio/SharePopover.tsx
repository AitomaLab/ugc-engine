'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { useTranslation } from '@/lib/i18n';

interface SharePopoverProps {
    url: string;
    assetType?: 'image' | 'video';
    onClose: () => void;
}

export function SharePopover({ url, assetType = 'video', onClose }: SharePopoverProps) {
    const { t } = useTranslation();
    const [copied, setCopied] = useState(false);
    const ref = useRef<HTMLDivElement>(null);

    // Click-outside handler
    useEffect(() => {
        const handler = (e: MouseEvent) => {
            if (ref.current && !ref.current.contains(e.target as Node)) onClose();
        };
        document.addEventListener('mousedown', handler);
        return () => document.removeEventListener('mousedown', handler);
    }, [onClose]);

    const handleCopy = useCallback(() => {
        navigator.clipboard.writeText(url);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    }, [url]);

    // Pre-populated share message
    const shareMsg = assetType === 'image'
        ? `Check out this image I just created with AI on Aitoma Studio\n${url}\n\nCreate yours at studio.aitoma.ai`
        : `Check out this video I just created with AI on Aitoma Studio\n${url}\n\nCreate yours at studio.aitoma.ai`;

    const shareToWhatsApp = () =>
        window.open(`https://wa.me/?text=${encodeURIComponent(shareMsg)}`, '_blank');
    const shareToX = () =>
        window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(shareMsg)}`, '_blank');
    const shareToLinkedIn = () =>
        window.open(`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`, '_blank');

    return (
        <div
            ref={ref}
            onClick={(e) => e.stopPropagation()}
            style={{
                position: 'absolute',
                bottom: '100%',
                right: 0,
                marginBottom: '8px',
                width: '300px',
                background: '#FFF',
                borderRadius: '14px',
                boxShadow: '0 12px 40px rgba(0,0,0,0.18)',
                border: '1px solid rgba(0,0,0,0.06)',
                padding: '16px',
                zIndex: 10001,
                animation: 'sharePopIn 0.18s cubic-bezier(0.4, 0, 0.2, 1)',
            }}
        >
            {/* Header */}
            <div style={{
                fontSize: '12px',
                fontWeight: 700,
                color: '#8A93B0',
                textTransform: 'uppercase',
                letterSpacing: '0.5px',
                marginBottom: '10px',
            }}>
                {t('share.title')}
            </div>

            {/* Copy link row */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                marginBottom: '12px',
            }}>
                <input
                    readOnly
                    value={url}
                    style={{
                        flex: 1,
                        padding: '8px 10px',
                        borderRadius: '8px',
                        border: '1px solid rgba(0,0,0,0.08)',
                        background: 'rgba(51,122,255,0.02)',
                        fontSize: '12px',
                        color: '#5A6178',
                        fontFamily: 'inherit',
                        outline: 'none',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                    }}
                />
                <button
                    onClick={handleCopy}
                    style={{
                        padding: '8px 12px',
                        borderRadius: '8px',
                        border: 'none',
                        background: copied
                            ? 'rgba(34,197,94,0.12)'
                            : 'linear-gradient(135deg, #337AFF, #6C5CE7)',
                        color: copied ? '#22C55E' : 'white',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: 'pointer',
                        whiteSpace: 'nowrap',
                        transition: 'all 0.2s',
                        flexShrink: 0,
                    }}
                >
                    {copied ? '✓' : t('share.copy')}
                </button>
            </div>

            {/* Copied confirmation */}
            {copied && (
                <div style={{
                    fontSize: '12px',
                    color: '#22C55E',
                    fontWeight: 600,
                    marginBottom: '10px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '4px',
                }}>
                    ✓ {t('share.copied')}
                </div>
            )}

            {/* Divider */}
            <div style={{
                height: '1px',
                background: 'rgba(0,0,0,0.06)',
                margin: '4px 0 12px',
            }} />

            {/* Social share */}
            <div style={{
                fontSize: '12px',
                color: '#8A93B0',
                marginBottom: '10px',
                fontWeight: 500,
            }}>
                {t('share.shareDirectly')}
            </div>
            <div style={{
                display: 'flex',
                gap: '8px',
            }}>
                <SocialButton
                    label="WhatsApp"
                    color="#25D366"
                    onClick={shareToWhatsApp}
                    icon={
                        <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'currentColor' }}>
                            <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z" />
                        </svg>
                    }
                />
                <SocialButton
                    label=""
                    color="#0D1B3E"
                    onClick={shareToX}
                    ariaLabel="Share on X"
                    icon={
                        <svg viewBox="0 0 24 24" style={{ width: '13px', height: '13px', fill: 'currentColor' }}>
                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                        </svg>
                    }
                />
                <SocialButton
                    label="LinkedIn"
                    color="#0A66C2"
                    onClick={shareToLinkedIn}
                    icon={
                        <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'currentColor' }}>
                            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 01-2.063-2.065 2.064 2.064 0 112.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                        </svg>
                    }
                />
            </div>

            <style>{`
                @keyframes sharePopIn {
                    from { opacity: 0; transform: translateY(4px) scale(0.97); }
                    to { opacity: 1; transform: translateY(0) scale(1); }
                }
            `}</style>
        </div>
    );
}

/* ── Social share button ─────────────────────────────────────── */
function SocialButton({
    label,
    color,
    onClick,
    icon,
    ariaLabel,
}: {
    label: string;
    color: string;
    onClick: () => void;
    icon: React.ReactNode;
    ariaLabel?: string;
}) {
    return (
        <button
            onClick={onClick}
            title={ariaLabel || label}
            aria-label={ariaLabel || label}
            style={{
                flex: 1,
                padding: '8px 0',
                borderRadius: '8px',
                border: '1px solid rgba(0,0,0,0.06)',
                background: 'white',
                color,
                fontSize: '11px',
                fontWeight: 600,
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: label ? '5px' : '0',
                transition: 'all 0.15s',
            }}
            onMouseEnter={(e) => {
                e.currentTarget.style.background = `${color}10`;
                e.currentTarget.style.borderColor = `${color}30`;
            }}
            onMouseLeave={(e) => {
                e.currentTarget.style.background = 'white';
                e.currentTarget.style.borderColor = 'rgba(0,0,0,0.06)';
            }}
        >
            {icon}
            {label}
        </button>
    );
}
