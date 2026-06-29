'use client';

import { useEffect, useRef, useState } from 'react';
import { useTranslation } from '@/lib/i18n';
import ScrubbableTimestamp from './ScrubbableTimestamp';
import type { AnalyticsBreakdown, VideoPrepStatus } from './analytics-types';

/**
 * Heuristic match against the friendly strings the backend writes from
 * `vision_service._friendly_error`. We classify failures purely by message
 * (no schema change needed) so the UI can pick the right tone + decide
 * whether to silently auto-retry once.
 *
 * Falls back to "permanent" for unknown copy so we never auto-retry into
 * an infinite loop on a config error (e.g. missing API key).
 */
function classifyBreakdownError(message?: string | null): 'transient' | 'permanent' {
    if (!message) return 'permanent';
    const m = message.toLowerCase();
    if (
        m.includes('temporarily') ||
        m.includes('temporally') ||
        m.includes('busy') ||
        m.includes('rate limit') ||
        m.includes('took too long') ||
        m.includes('try again') ||
        m.includes('interrupted')
    ) {
        return 'transient';
    }
    return 'permanent';
}

/** Map backend video-prep errors to user-facing i18n strings. */
function friendlyPrepError(
    message: string | null | undefined,
    t: (key: string) => string,
): string {
    if (!message) return t('analytics.detail.prep.failed');
    const m = message.toLowerCase();
    if (
        m.includes('parse error')
        || m.includes('brightdata returned')
    ) {
        return t('analytics.detail.prep.brightdataFailed');
    }
    if (
        m.includes('empty trigger payload')
        || m.includes('no url could be derived')
        || m.includes('missing post url')
        || m.includes('could not detect platform')
    ) {
        return t('analytics.detail.prep.missingPostUrl');
    }
    return message;
}

/** Map backend `vision_service._friendly_error` strings to i18n keys. */
function localizeBreakdownErrorBody(
    message: string | null | undefined,
    t: (key: string) => string,
): string {
    if (!message) return t('analytics.detail.error.permanentBody');
    const m = message.toLowerCase();
    if (m.includes('temporarily busy') || m.includes('service is temporarily busy')) {
        return t('analytics.detail.error.busy');
    }
    if (m.includes('rate limit')) return t('analytics.detail.error.rateLimit');
    if (m.includes('took too long')) return t('analytics.detail.error.timeout');
    if (m.includes('too large')) return t('analytics.detail.error.tooLarge');
    if (m.includes('not configured')) return t('analytics.detail.error.notConfigured');
    if (m.includes('temporarily unavailable')) return t('analytics.detail.error.genericUnavailable');
    if (m.includes('timed out') || m.includes('ai analysis timed out')) {
        return t('analytics.detail.error.timeout');
    }
    if (m.includes('interrupted')) {
        return t('analytics.detail.error.interrupted');
    }
    return message;
}

interface Props {
    breakdown: AnalyticsBreakdown | null;
    status: AnalyticsBreakdown['status'] | 'none';
    videoRef: React.RefObject<HTMLVideoElement | null>;
    onGenerate: () => void;
    /**
     * `canGenerate` is true only when the AI breakdown can actually be
     * triggered — i.e. the parent has a downloadable video URL ready
     * (storage_video_url for external posts, video_jobs.final_video_url
     * for internal posts).
     */
    canGenerate: boolean;
    generating: boolean;
    /**
     * Lazy video-prep status from the parent. When `queued | scraping |
     * downloading`, the empty-state shows a progress bar instead of the
     * normal "Generate AI breakdown" button. When `failed`, the error
     * message bubbles up so the user knows why.
     */
    prepStatus?: VideoPrepStatus;
    prepProgressPct?: number;
    prepError?: string;
    videoOnly?: boolean;
    targetLang?: string;
    onRetryPrep?: () => void;
    onRetryLocale?: () => void;
}

function ProgressLine({ label }: { label: string }) {
    return (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: 'var(--blue)', fontWeight: 600 }}>
            <span
                style={{
                    display: 'inline-block',
                    width: 100,
                    height: 4,
                    borderRadius: 2,
                    background:
                        'linear-gradient(90deg, rgba(51,122,255,0.12) 0%, rgba(51,122,255,0.55) 50%, rgba(51,122,255,0.12) 100%)',
                    backgroundSize: '200% 100%',
                    animation: 'shimmer 1.6s ease-in-out infinite',
                }}
            />
            {label}
        </div>
    );
}

function Section({
    title,
    open,
    onToggle,
    children,
}: {
    title: string;
    open: boolean;
    onToggle: () => void;
    children: React.ReactNode;
}) {
    return (
        <div
            style={{
                background: 'white',
                border: '1px solid var(--border)',
                borderRadius: '12px',
                overflow: 'hidden',
            }}
        >
            <button
                onClick={onToggle}
                style={{
                    display: 'flex',
                    width: '100%',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 14px',
                    background: 'transparent',
                    border: 'none',
                    cursor: 'pointer',
                    fontSize: '13px',
                    fontWeight: 700,
                    color: 'var(--text-1)',
                }}
            >
                <span>{title}</span>
                <svg
                    width="14"
                    height="14"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2.5}
                    style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.15s ease' }}
                >
                    <polyline points="6 9 12 15 18 9" />
                </svg>
            </button>
            {open && (
                <div style={{ padding: '0 14px 14px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {children}
                </div>
            )}
        </div>
    );
}

export default function HookBreakdownPanel({
    breakdown, status, videoRef, onGenerate, canGenerate, generating,
    prepStatus, prepProgressPct, prepError, videoOnly,
    targetLang, onRetryPrep, onRetryLocale,
}: Props) {
    const { t } = useTranslation();
    const [scenesOpen, setScenesOpen] = useState(false);
    const [audioOpen, setAudioOpen] = useState(false);
    const [visualOpen, setVisualOpen] = useState(false);
    const [momentsOpen, setMomentsOpen] = useState(false);
    const [localeWaitSec, setLocaleWaitSec] = useState(0);

    const localePending = breakdown?.locale_pending === true;
    const localeMismatch = !!(
        breakdown
        && targetLang
        && breakdown.content_locale
        && breakdown.content_locale !== targetLang
    );

    useEffect(() => {
        if (!localePending && !localeMismatch) {
            setLocaleWaitSec(0);
            return;
        }
        const timer = window.setInterval(() => {
            setLocaleWaitSec((s) => s + 1);
        }, 1000);
        return () => window.clearInterval(timer);
    }, [localePending, localeMismatch, breakdown?.id]);

    /**
     * Silent auto-retry for transient failures (Gemini 503 spikes, rate
     * limits, etc.). We retry at most ONCE per (breakdown.id, error) pair
     * so a permanent-but-misclassified message can't loop. The user can
     * still hit "Try again" manually after that.
     */
    const autoRetriedRef = useRef<string | null>(null);
    useEffect(() => {
        if (status !== 'failed' || !breakdown) return;
        if (!canGenerate || generating) return;
        if (classifyBreakdownError(breakdown.error_message) !== 'transient') return;
        const fingerprint = `${breakdown.id}:${breakdown.error_message || ''}`;
        if (autoRetriedRef.current === fingerprint) return;
        autoRetriedRef.current = fingerprint;
        const timer = setTimeout(() => onGenerate(), 4000);
        return () => clearTimeout(timer);
    }, [status, breakdown, canGenerate, generating, onGenerate]);

    if (status === 'none' || !breakdown) {
        if (videoOnly || prepStatus === 'skipped') {
            return (
                <div
                    style={{
                        background: 'var(--blue-light)',
                        border: '1px dashed var(--border)',
                        borderRadius: 'var(--radius)',
                        padding: '20px',
                        textAlign: 'center',
                        color: 'var(--text-2)',
                        fontSize: '13px',
                        maxWidth: 360,
                        margin: '0 auto',
                    }}
                >
                    {prepError || t('analytics.detail.prep.videoOnly')}
                </div>
            );
        }

        // Prep is in flight — show a progress bar in place of the button so
        // the user understands *why* "Generate AI breakdown" is unavailable.
        const prepInProgress = prepStatus === 'queued' || prepStatus === 'scraping' || prepStatus === 'downloading';
        const pct = Math.max(5, Math.min(100, prepProgressPct ?? 5));

        return (
            <div
                style={{
                    background: 'var(--blue-light)',
                    border: '1px dashed var(--border)',
                    borderRadius: 'var(--radius)',
                    padding: '20px',
                    textAlign: 'center',
                    color: 'var(--text-2)',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    alignItems: 'center',
                }}
            >
                <div style={{ fontSize: '13px', maxWidth: 360 }}>
                    {prepInProgress
                        ? t('analytics.detail.prep.preparing')
                        : prepStatus === 'failed'
                            ? friendlyPrepError(prepError, t)
                            : t('analytics.detail.aiBreakdown')}
                </div>

                {prepInProgress ? (
                    <div style={{ width: '100%', maxWidth: 320, display: 'flex', flexDirection: 'column', gap: '6px' }}>
                        <div
                            style={{
                                width: '100%',
                                height: 6,
                                borderRadius: 999,
                                background: 'rgba(51,122,255,0.15)',
                                overflow: 'hidden',
                            }}
                        >
                            <div
                                style={{
                                    width: `${pct}%`,
                                    height: '100%',
                                    background: 'linear-gradient(90deg, #5B9CFF 0%, #337AFF 100%)',
                                    borderRadius: 999,
                                    transition: 'width 0.4s ease',
                                }}
                            />
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-3)' }}>
                            {prepStatus === 'scraping'    && t('analytics.detail.prep.scraping')}
                            {prepStatus === 'downloading' && t('analytics.detail.prep.downloading')}
                            {prepStatus === 'queued'      && t('analytics.detail.prep.queued')}
                        </div>
                        {onRetryPrep && (
                            <button
                                type="button"
                                onClick={onRetryPrep}
                                style={{
                                    marginTop: 4,
                                    padding: '6px 14px',
                                    borderRadius: '8px',
                                    border: '1px solid var(--border)',
                                    background: 'white',
                                    color: 'var(--blue)',
                                    fontSize: '12px',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                }}
                            >
                                {t('analytics.detail.prep.retry')}
                            </button>
                        )}
                    </div>
                ) : (
                    <button
                        onClick={onGenerate}
                        disabled={!canGenerate || generating}
                        title={!canGenerate ? t('analytics.detail.prep.waitingForVideo') : undefined}
                        style={{
                            padding: '10px 22px',
                            borderRadius: '10px',
                            border: 'none',
                            background: canGenerate ? 'var(--blue)' : 'var(--text-3)',
                            color: 'white',
                            fontSize: '13px',
                            fontWeight: 600,
                            cursor: canGenerate && !generating ? 'pointer' : 'not-allowed',
                            opacity: canGenerate ? 1 : 0.7,
                        }}
                    >
                        {generating
                            ? '…'
                            : canGenerate
                                ? t('analytics.detail.generate')
                                : t('analytics.detail.prep.waitingForVideo')}
                    </button>
                )}
            </div>
        );
    }

    if (status === 'pending' || status === 'running') {
        return (
            <div
                style={{
                    background: 'white',
                    border: '1px solid var(--border)',
                    borderRadius: 'var(--radius)',
                    padding: '18px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                }}
            >
                <ProgressLine label={status === 'pending' ? t('analytics.detail.progress.uploading') : t('analytics.detail.progress.analyzing')} />
                <div style={{ fontSize: '12px', color: 'var(--text-3)' }}>
                    {t('analytics.detail.progress.pipeline')}
                </div>
            </div>
        );
    }

    if (status === 'failed') {
        const transient = classifyBreakdownError(breakdown.error_message) === 'transient';
        const accent = transient ? '#a35a00' : 'var(--text-2)';
        const bg = transient ? 'rgba(255,159,10,0.08)' : 'rgba(13,27,62,0.04)';
        const border = transient ? 'rgba(255,159,10,0.30)' : 'var(--border)';
        const title = transient
            ? t('analytics.detail.error.transientTitle')
            : t('analytics.detail.error.permanentTitle');
        // Prefer the friendly server message; only fall back to generic copy
        // if the row is somehow missing one.
        const body = localizeBreakdownErrorBody(breakdown.error_message, t);
        // When we have an auto-retry queued, surface a subtle "retrying…"
        // hint so the user understands the activity instead of seeing a
        // stale failure card.
        const retryingNow = transient && generating;

        return (
            <div
                style={{
                    background: bg,
                    border: `1px solid ${border}`,
                    borderRadius: '12px',
                    padding: '16px 18px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '10px',
                }}
            >
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <span
                        aria-hidden
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            width: 28, height: 28,
                            borderRadius: '50%',
                            background: transient ? 'rgba(255,159,10,0.18)' : 'rgba(13,27,62,0.08)',
                            color: accent,
                        }}
                    >
                        {transient ? (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
                                <path d="M12 8v4l3 2" />
                                <circle cx="12" cy="12" r="10" />
                            </svg>
                        ) : (
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10" />
                                <line x1="12" y1="8" x2="12" y2="12" />
                                <line x1="12" y1="16" x2="12.01" y2="16" />
                            </svg>
                        )}
                    </span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, minWidth: 0 }}>
                        <span style={{ fontSize: '13px', fontWeight: 700, color: accent }}>
                            {title}
                        </span>
                        <span style={{ fontSize: '12px', color: 'var(--text-2)' }}>
                            {body}
                        </span>
                    </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
                    <button
                        onClick={onGenerate}
                        disabled={!canGenerate || generating}
                        style={{
                            padding: '8px 16px',
                            borderRadius: '10px',
                            border: '1px solid var(--border)',
                            background: 'white',
                            color: 'var(--blue)',
                            fontSize: '13px',
                            fontWeight: 600,
                            cursor: canGenerate && !generating ? 'pointer' : 'not-allowed',
                            opacity: canGenerate ? 1 : 0.6,
                        }}
                    >
                        {generating ? '…' : t('analytics.detail.regenerate')}
                    </button>
                    {retryingNow && (
                        <span style={{ fontSize: '12px', color: 'var(--text-3)' }}>
                            {t('analytics.detail.error.retrying')}
                        </span>
                    )}
                </div>
            </div>
        );
    }

    // status === 'completed'
    const showLocaleBanner = localePending || localeMismatch || !!breakdown.locale_error;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {showLocaleBanner && (
                <div
                    style={{
                        fontSize: '12px',
                        color: breakdown.locale_error ? '#a35a00' : 'var(--blue)',
                        padding: '8px 12px',
                        borderRadius: '8px',
                        background: breakdown.locale_error
                            ? 'rgba(255,159,10,0.08)'
                            : 'rgba(51,122,255,0.08)',
                        border: breakdown.locale_error
                            ? '1px solid rgba(255,159,10,0.25)'
                            : '1px solid rgba(51,122,255,0.20)',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '8px',
                    }}
                >
                    <span>
                        {breakdown.locale_error
                            ? (breakdown.locale_error.includes('OPENAI')
                                ? t('analytics.detail.locale.notConfigured')
                                : t('analytics.detail.locale.failed'))
                            : localeWaitSec >= 30
                                ? t('analytics.detail.locale.slow')
                                : t('analytics.detail.progress.translating')}
                    </span>
                    {onRetryLocale && (breakdown.locale_error || localeWaitSec >= 30) && (
                        <button
                            type="button"
                            onClick={onRetryLocale}
                            style={{
                                alignSelf: 'flex-start',
                                padding: '6px 14px',
                                borderRadius: '8px',
                                border: '1px solid var(--border)',
                                background: 'white',
                                color: 'var(--blue)',
                                fontSize: '12px',
                                fontWeight: 600,
                                cursor: 'pointer',
                            }}
                        >
                            {t('analytics.detail.locale.retry')}
                        </button>
                    )}
                </div>
            )}
            {/* Summary */}
            {breakdown.summary && (
                <div
                    style={{
                        background: 'white',
                        border: '1px solid var(--border)',
                        borderRadius: '12px',
                        padding: '14px',
                        fontSize: '13px',
                        color: 'var(--text-1)',
                        lineHeight: 1.55,
                    }}
                >
                    {breakdown.summary}
                </div>
            )}

            {/* Hook callout */}
            {breakdown.hook && (
                <div
                    style={{
                        background: 'linear-gradient(135deg, rgba(51,122,255,0.10) 0%, rgba(51,122,255,0.04) 100%)',
                        border: '1px solid rgba(51,122,255,0.25)',
                        borderRadius: '12px',
                        padding: '14px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '8px',
                    }}
                >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.6, color: 'var(--blue)' }}>
                            {t('analytics.detail.hook')}
                        </span>
                        {breakdown.hook.timestamp && (
                            <ScrubbableTimestamp ts={breakdown.hook.timestamp} videoRef={videoRef} label="hook" />
                        )}
                    </div>
                    {breakdown.hook.on_screen_text && (
                        <div style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-1)' }}>
                            “{breakdown.hook.on_screen_text}”
                        </div>
                    )}
                    {breakdown.hook.visual && (
                        <div style={{ fontSize: '13px', color: 'var(--text-2)' }}>{breakdown.hook.visual}</div>
                    )}
                    {breakdown.hook.why_it_works && (
                        <div style={{ fontSize: '12px', color: 'var(--text-3)', fontStyle: 'italic' }}>
                            {breakdown.hook.why_it_works}
                        </div>
                    )}
                </div>
            )}

            {/* Scenes */}
            {breakdown.scenes && breakdown.scenes.length > 0 && (
                <Section
                    title={`${t('analytics.detail.scenes')} (${breakdown.scenes.length})`}
                    open={scenesOpen}
                    onToggle={() => setScenesOpen((v) => !v)}
                >
                    {breakdown.scenes.map((scene, i) => (
                        <div
                            key={i}
                            style={{
                                display: 'flex',
                                gap: '10px',
                                alignItems: 'flex-start',
                                paddingBottom: '8px',
                                borderBottom: i === (breakdown.scenes?.length ?? 0) - 1 ? 'none' : '1px solid var(--border)',
                            }}
                        >
                            <ScrubbableTimestamp ts={scene.start} videoRef={videoRef} />
                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '3px' }}>
                                <div style={{ fontSize: '13px', color: 'var(--text-1)' }}>{scene.description}</div>
                                {scene.on_screen_text && (
                                    <div style={{ fontSize: '12px', color: 'var(--text-3)', fontStyle: 'italic' }}>
                                        “{scene.on_screen_text}”
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}
                </Section>
            )}

            {/* Audio */}
            {breakdown.audio && (
                <Section
                    title={t('analytics.detail.audio')}
                    open={audioOpen}
                    onToggle={() => setAudioOpen((v) => !v)}
                >
                    {breakdown.audio.has_audio && breakdown.audio.transcript && breakdown.audio.transcript.length > 0 ? (
                        breakdown.audio.transcript.map((line, i) => (
                            <div key={i} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                                <ScrubbableTimestamp ts={line.ts} videoRef={videoRef} />
                                <div style={{ fontSize: '13px', color: 'var(--text-1)', flex: 1 }}>{line.text}</div>
                            </div>
                        ))
                    ) : (
                        <div style={{ fontSize: '13px', color: 'var(--text-3)' }}>
                            {breakdown.audio.notes || t('analytics.detail.noAudio')}
                        </div>
                    )}
                </Section>
            )}

            {/* Visual details */}
            {breakdown.visual_details && breakdown.visual_details.length > 0 && (
                <Section
                    title={t('analytics.detail.visualDetails')}
                    open={visualOpen}
                    onToggle={() => setVisualOpen((v) => !v)}
                >
                    <ul style={{ margin: 0, paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        {breakdown.visual_details.map((d, i) => (
                            <li key={i} style={{ fontSize: '13px', color: 'var(--text-1)' }}>{d}</li>
                        ))}
                    </ul>
                </Section>
            )}

            {/* Key moments */}
            {breakdown.key_moments && breakdown.key_moments.length > 0 && (
                <Section
                    title={t('analytics.detail.keyMoments')}
                    open={momentsOpen}
                    onToggle={() => setMomentsOpen((v) => !v)}
                >
                    {breakdown.key_moments.map((m, i) => (
                        <div key={i} style={{ display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                            <ScrubbableTimestamp ts={m.ts} videoRef={videoRef} />
                            <div style={{ fontSize: '13px', color: 'var(--text-1)', flex: 1 }}>{m.description}</div>
                        </div>
                    ))}
                </Section>
            )}

            {/* Takeaways */}
            {breakdown.takeaways && breakdown.takeaways.length > 0 && (
                <div
                    style={{
                        background: 'white',
                        border: '1px solid var(--border)',
                        borderRadius: '12px',
                        padding: '14px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '10px',
                    }}
                >
                    <div style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: 0.6, color: 'var(--blue)' }}>
                        {t('analytics.detail.takeaways')}
                    </div>
                    {breakdown.takeaways.map((line, i) => (
                        <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: '13px', color: 'var(--text-1)' }}>
                            <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--blue)', minWidth: 18 }}>
                                {i + 1}.
                            </span>
                            <span style={{ flex: 1, lineHeight: 1.5 }}>{line}</span>
                        </div>
                    ))}
                </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                <button
                    onClick={onGenerate}
                    disabled={!canGenerate || generating}
                    style={{
                        padding: '6px 14px',
                        borderRadius: '10px',
                        border: '1px solid var(--border)',
                        background: 'white',
                        color: 'var(--blue)',
                        fontSize: '12px',
                        fontWeight: 600,
                        cursor: canGenerate && !generating ? 'pointer' : 'not-allowed',
                    }}
                >
                    {t('analytics.detail.regenerate')}
                </button>
            </div>
        </div>
    );
}
