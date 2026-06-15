'use client';

import React, { useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import type { MentionGroups, MentionGroupType, MentionItem } from './mention-utils';

export interface MentionAssetGridProps {
    groups: MentionGroups;
    ordered?: MentionItem[];
    allowedTypes?: MentionGroupType[];
    variant: 'popover' | 'inline';
    active?: boolean;
    activeIndex?: number;
    selectedTag?: string | null;
    loading?: boolean;
    emptyLabel?: string;
    onPick: (item: MentionItem) => void;
    onHover?: (idx: number) => void;
    shotPickerItem?: MentionItem | null;
    onPickShot?: (imageUrl: string) => void;
    onBackFromShotPicker?: () => void;
}

const GROUP_ORDER: MentionGroupType[] = ['influencer', 'clone', 'product', 'image', 'video'];

export function MentionAssetGrid({
    groups,
    ordered = [],
    allowedTypes,
    variant,
    active = true,
    activeIndex = -1,
    selectedTag = null,
    loading = false,
    emptyLabel,
    onPick,
    onHover,
    shotPickerItem,
    onPickShot,
    onBackFromShotPicker,
}: MentionAssetGridProps) {
    const { t } = useTranslation();
    const GROUP_LABELS_T: Record<MentionGroupType, string> = {
        product: t('creativeOs.mention.products'),
        influencer: t('creativeOs.mention.models'),
        clone: t('creativeOs.mention.clones'),
        image: t('creativeOs.mention.images'),
        video: t('creativeOs.mention.videos'),
    };

    const filteredOrder = allowedTypes ?? GROUP_ORDER;
    const availableGroups = filteredOrder.filter((g) => (groups[g]?.length || 0) > 0);
    const [activeTab, setActiveTab] = useState<MentionGroupType>(availableGroups[0] || filteredOrder[0]);
    const effectiveTab = availableGroups.includes(activeTab) ? activeTab : (availableGroups[0] || filteredOrder[0]);
    const tabItems = groups[effectiveTab] || [];

    const useMouseDown = variant === 'popover';
    const preventBlur = (e: React.MouseEvent) => {
        if (useMouseDown) e.preventDefault();
    };

    const containerStyle: React.CSSProperties = variant === 'popover'
        ? {
            position: 'absolute',
            left: '14px',
            right: '14px',
            bottom: 'calc(100% - 6px)',
            background: 'white',
            border: '1px solid rgba(13,27,62,0.12)',
            borderRadius: '12px',
            boxShadow: '0 12px 32px rgba(13,27,62,0.16)',
            maxHeight: '320px',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            zIndex: 10,
        }
        : {
            marginTop: '10px',
            background: 'rgba(244,246,250,0.6)',
            border: '1px solid rgba(13,27,62,0.08)',
            borderRadius: '10px',
            overflow: 'hidden',
            display: 'flex',
            flexDirection: 'column',
            maxHeight: '280px',
        };

    if (loading) {
        return (
            <div style={containerStyle}>
                <div style={{ padding: '16px 12px', fontSize: '12px', color: '#8A93B0', textAlign: 'center' }}>
                    {t('creativeOs.agent.loadingAssets')}
                </div>
            </div>
        );
    }

    if (shotPickerItem && shotPickerItem.views && onPickShot) {
        return (
            <div style={containerStyle}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 12px 8px' }}>
                    <button
                        type="button"
                        onMouseDown={preventBlur}
                        onClick={() => onBackFromShotPicker?.()}
                        disabled={!active}
                        style={{
                            border: '1px solid rgba(13,27,62,0.15)',
                            background: 'white',
                            borderRadius: '6px',
                            padding: '2px 8px',
                            cursor: active ? 'pointer' : 'default',
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
                <div style={{ overflowY: 'auto', padding: '0 8px 8px' }}>
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
                        {shotPickerItem.views.map((url, i) => (
                            <button
                                key={`${url}-${i}`}
                                type="button"
                                onMouseDown={preventBlur}
                                onClick={() => active && onPickShot(url)}
                                disabled={!active}
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
                                    cursor: active ? 'pointer' : 'default',
                                    minWidth: 0,
                                }}
                                onMouseEnter={(e) => {
                                    if (!active) return;
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
            </div>
        );
    }

    if (availableGroups.length === 0) {
        return (
            <div style={containerStyle}>
                <div style={{ padding: '16px 12px', fontSize: '12px', color: '#8A93B0', textAlign: 'center' }}>
                    {emptyLabel || t('creativeOs.mention.noMatches')}
                </div>
            </div>
        );
    }

    return (
        <div style={containerStyle}>
            {availableGroups.length > 1 && (
                <div
                    style={{
                        display: 'flex',
                        gap: '0',
                        borderBottom: '1px solid rgba(13,27,62,0.08)',
                        padding: '0 8px',
                        flexShrink: 0,
                    }}
                >
                    {availableGroups.map((g) => {
                        const isTabActive = g === effectiveTab;
                        return (
                            <button
                                key={g}
                                type="button"
                                onMouseDown={preventBlur}
                                onClick={() => setActiveTab(g)}
                                style={{
                                    flex: 1,
                                    padding: '9px 0 7px',
                                    border: 'none',
                                    borderBottom: isTabActive ? '2px solid #337AFF' : '2px solid transparent',
                                    background: 'transparent',
                                    cursor: 'pointer',
                                    fontSize: '11px',
                                    fontWeight: isTabActive ? 700 : 500,
                                    color: isTabActive ? '#337AFF' : '#8A93B0',
                                    textTransform: 'uppercase',
                                    letterSpacing: '0.4px',
                                    transition: 'color 0.15s, border-color 0.15s',
                                }}
                            >
                                {GROUP_LABELS_T[g]}
                                <span
                                    style={{
                                        marginLeft: '4px',
                                        fontSize: '10px',
                                        fontWeight: 600,
                                        color: isTabActive ? '#337AFF' : '#B0B8CC',
                                    }}
                                >
                                    {groups[g]?.length || 0}
                                </span>
                            </button>
                        );
                    })}
                </div>
            )}
            <div style={{ overflowY: 'auto', padding: '8px' }}>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
                    {tabItems.map((item, itemIdx) => {
                        const idx = ordered.indexOf(item);
                        const keyboardActive = idx === activeIndex;
                        const isSelected = selectedTag === item.tag;
                        const muted = !!selectedTag && !isSelected;
                        return (
                            <button
                                key={`${item.type}-${item.ref?.id || item.tag}-${itemIdx}`}
                                type="button"
                                onMouseDown={preventBlur}
                                onClick={() => active && onPick(item)}
                                onMouseEnter={() => onHover?.(idx)}
                                disabled={!active}
                                title={item.name}
                                style={{
                                    display: 'flex',
                                    flexDirection: 'column',
                                    alignItems: 'center',
                                    gap: '4px',
                                    padding: '6px 4px',
                                    border: isSelected || keyboardActive
                                        ? '1px solid rgba(51,122,255,0.5)'
                                        : '1px solid transparent',
                                    background: isSelected || keyboardActive
                                        ? 'rgba(51,122,255,0.08)'
                                        : 'transparent',
                                    borderRadius: '8px',
                                    cursor: active ? 'pointer' : 'default',
                                    minWidth: 0,
                                    opacity: muted ? 0.45 : 1,
                                }}
                            >
                                <div
                                    style={{
                                        width: '100%',
                                        aspectRatio: '1 / 1',
                                        borderRadius: '6px',
                                        background: '#F4F6FA',
                                        overflow: 'hidden',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                    }}
                                >
                                    {item.image_url ? (
                                        // eslint-disable-next-line @next/next/no-img-element
                                        <img
                                            src={item.image_url}
                                            alt={item.name}
                                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                        />
                                    ) : item.type === 'video' && item.ref.video_url ? (
                                        <video
                                            src={item.ref.video_url}
                                            muted
                                            playsInline
                                            preload="metadata"
                                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                                        />
                                    ) : (
                                        <span style={{ fontSize: '14px', color: '#8A93B0' }}>
                                            {item.type === 'video' ? '▶' : '·'}
                                        </span>
                                    )}
                                </div>
                                <span
                                    style={{
                                        fontSize: '10px',
                                        color: '#0D1B3E',
                                        fontWeight: 500,
                                        textOverflow: 'ellipsis',
                                        overflow: 'hidden',
                                        whiteSpace: 'nowrap',
                                        width: '100%',
                                        textAlign: 'center',
                                    }}
                                >
                                    {item.name}
                                </span>
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
