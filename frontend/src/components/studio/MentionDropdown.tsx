import React from 'react';
import { AgentRef } from '@/lib/creative-os-api';
import { useTranslation } from '@/lib/i18n';

export interface MentionItem {
    type: AgentRef['type'];
    tag: string;
    name: string;
    image_url?: string;
    views?: string[];
    ref: AgentRef;
}

export interface MentionDropdownProps {
    groups: Record<'product' | 'influencer' | 'image' | 'video', MentionItem[]>;
    ordered: MentionItem[];
    activeIndex: number;
    onPick: (item: MentionItem) => void;
    onHover: (idx: number) => void;
    shotPickerItem?: MentionItem | null;
    onPickShot?: (imageUrl: string) => void;
    onBackFromShotPicker?: () => void;
}

export function MentionDropdown({ groups, ordered, activeIndex, onPick, onHover, shotPickerItem, onPickShot, onBackFromShotPicker }: MentionDropdownProps) {
    const { t } = useTranslation();
    const GROUP_LABELS: Record<MentionItem['type'], string> = {
        product: t('creativeOs.mention.products'),
        influencer: t('creativeOs.mention.models'),
        image: t('creativeOs.mention.images'),
        video: t('creativeOs.mention.videos'),
    };
    const groupOrder: MentionItem['type'][] = ['product', 'influencer', 'image', 'video'];
    const containerStyle: React.CSSProperties = {
        position: 'absolute',
        left: '14px',
        right: '14px',
        bottom: 'calc(100% - 6px)',
        background: 'white',
        border: '1px solid rgba(13,27,62,0.12)',
        borderRadius: '12px',
        boxShadow: '0 12px 32px rgba(13,27,62,0.16)',
        maxHeight: 'min(320px, 50vh)',
        overflowY: 'auto',
        padding: '8px',
        zIndex: 10,
    };
    if (shotPickerItem && shotPickerItem.views && onPickShot) {
        return (
            <div style={containerStyle}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 6px 8px' }}>
                    <button
                        type="button"
                        onMouseDown={(e) => { e.preventDefault(); onBackFromShotPicker?.(); }}
                        style={{
                            border: '1px solid rgba(13,27,62,0.15)',
                            background: 'white',
                            borderRadius: '6px',
                            padding: '2px 8px',
                            cursor: 'pointer',
                            fontSize: '11px',
                            color: '#0D1B3E',
                        }}
                    >
                        {t('creativeOs.mention.back')}
                    </button>
                    <span style={{ fontSize: '11px', fontWeight: 600, color: '#0D1B3E' }}>
                        {t('creativeOs.mention.pickShotFor').replace('{name}', shotPickerItem.name)}
                    </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
                    {shotPickerItem.views.map((url, i) => (
                        <button
                            key={`${url}-${i}`}
                            type="button"
                            onMouseDown={(e) => { e.preventDefault(); onPickShot(url); }}
                            title={i === 0 ? t('creativeOs.mention.profileImage') : t('creativeOs.mention.shot').replace('{n}', String(i + 1))}
                            style={{
                                display: 'flex',
                                flexDirection: 'column',
                                alignItems: 'center',
                                gap: '4px',
                                padding: '6px 4px',
                                border: '1px solid transparent',
                                background: 'transparent',
                                borderRadius: '8px',
                                cursor: 'pointer',
                                minWidth: 0,
                            }}
                            onMouseEnter={(e) => {
                                (e.currentTarget as HTMLButtonElement).style.background = 'rgba(51,122,255,0.08)';
                                (e.currentTarget as HTMLButtonElement).style.borderColor = 'rgba(51,122,255,0.5)';
                            }}
                            onMouseLeave={(e) => {
                                (e.currentTarget as HTMLButtonElement).style.background = 'transparent';
                                (e.currentTarget as HTMLButtonElement).style.borderColor = 'transparent';
                            }}
                        >
                            <div style={{ width: '100%', aspectRatio: '1 / 1', borderRadius: '6px', background: '#F4F6FA', overflow: 'hidden' }}>
                                {/* eslint-disable-next-line @next/next/no-img-element */}
                                <img src={url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            </div>
                            <span style={{ fontSize: '10px', color: '#0D1B3E', fontWeight: 500, textAlign: 'center' }}>
                                {i === 0 ? t('creativeOs.mention.profile') : t('creativeOs.mention.shot').replace('{n}', String(i + 1))}
                            </span>
                        </button>
                    ))}
                </div>
            </div>
        );
    }
    return (
        <div style={containerStyle}>
            {ordered.length === 0 ? (
                <div style={{ padding: '12px 8px', fontSize: '12px', color: '#8A93B0', textAlign: 'center' }}>
                    {t('creativeOs.mention.noMatches')}
                </div>
            ) : (
                groupOrder.map((gType) => {
                    const groupItems = groups[gType] || [];
                    if (groupItems.length === 0) return null;
                    return (
                        <div key={gType} style={{ marginBottom: '8px' }}>
                            <div style={{
                                padding: '4px 8px',
                                fontSize: '11px',
                                fontWeight: 700,
                                textTransform: 'uppercase',
                                letterSpacing: '0.5px',
                                color: '#8A93B0',
                                marginBottom: '2px',
                            }}>
                                {GROUP_LABELS[gType]}
                            </div>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
                                {groupItems.map((item) => {
                                    const globalIdx = ordered.findIndex((o) => o.tag === item.tag);
                                    const active = globalIdx === activeIndex;
                                    return (
                                        <button
                                            key={item.tag}
                                            type="button"
                                            onMouseDown={(e) => {
                                                e.preventDefault();
                                                onPick(item);
                                            }}
                                            onMouseEnter={() => onHover(globalIdx)}
                                            style={{
                                                display: 'flex',
                                                alignItems: 'center',
                                                gap: '10px',
                                                padding: '6px 8px',
                                                borderRadius: '8px',
                                                background: active ? 'rgba(51,122,255,0.06)' : 'transparent',
                                                cursor: 'pointer',
                                                border: '1px solid transparent',
                                            }}
                                        >
                                            <div style={{
                                                width: '24px', height: '24px', borderRadius: '4px',
                                                background: '#F4F6FA', flexShrink: 0, overflow: 'hidden',
                                                display: 'flex', alignItems: 'center', justifyContent: 'center'
                                            }}>
                                                {item.image_url ? (
                                                    // eslint-disable-next-line @next/next/no-img-element
                                                    <img src={item.image_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                                ) : (
                                                    <span style={{ fontSize: '12px' }}>
                                                        {item.type === 'product' ? '📦' : item.type === 'influencer' ? '👤' : item.type === 'image' ? '🖼' : '🎬'}
                                                    </span>
                                                )}
                                            </div>
                                            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
                                                <span style={{ fontSize: '13px', fontWeight: 600, color: '#0D1B3E', lineHeight: 1.2 }}>
                                                    {item.name}
                                                </span>
                                                <span style={{ fontSize: '11px', color: '#8A93B0' }}>
                                                    @{item.tag}
                                                </span>
                                            </div>
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                    );
                })
            )}
        </div>
    );
}
