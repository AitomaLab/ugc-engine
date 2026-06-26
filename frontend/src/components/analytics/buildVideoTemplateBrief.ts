import type { AgentRef } from '@/lib/creative-os-api';
import type { AnalyticsBreakdown, AnalyticsPost } from '@/lib/types';

const MAX_BRIEF_CHARS = 4000;
const MAX_TARGET_DURATION_SEC = 30;
const SCENE_DENSE_THRESHOLD = 10;

const SPEAK_CUES = /\b(speak|speaking|says|said|dialogue|voiceover|voice over|script|testimon|habla|hablando|dice|narra|presenta)\b/i;
const CINEMATIC_NEG = /\b(storyboard|cinematic ad|cinematic spot|film-style|movie-style|hollywood|anuncio cinemático|anuncio cinematico)\b/i;
const HUMAN_ACTION = /\b(walk|walking|move|moving|brother|person|presenter|creator|founder|team|office|street|call|video call)\b/i;

export interface TemplateBriefResult {
    brief: string;
    refs: AgentRef[];
    useDynamicSpeaking: boolean;
    targetDurationSec: number;
}

interface SceneBeat {
    startSec: number;
    endSec: number;
    description: string;
}

function parseTimestamp(ts?: string): number | null {
    if (!ts) return null;
    const cleaned = ts.trim().replace(/[^\d:.]/g, '');
    const parts = cleaned.split(':').map((p) => parseInt(p, 10));
    if (parts.some((n) => Number.isNaN(n))) return null;
    if (parts.length === 1) return parts[0];
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    return null;
}

function formatTimestamp(sec: number): string {
    const s = Math.max(0, Math.round(sec));
    const m = Math.floor(s / 60);
    const r = s % 60;
    return `${m}:${String(r).padStart(2, '0')}`;
}

function collectBeats(breakdown: AnalyticsBreakdown): SceneBeat[] {
    const scenes = breakdown.scenes || [];
    const keyMoments = breakdown.key_moments || [];
    const useKeyMoments = scenes.length > SCENE_DENSE_THRESHOLD && keyMoments.length > 0;

    if (useKeyMoments) {
        return keyMoments
            .map((km, i) => {
                const startSec = parseTimestamp(km.ts) ?? i * 5;
                const nextStart = i + 1 < keyMoments.length
                    ? parseTimestamp(keyMoments[i + 1]?.ts)
                    : null;
                const endSec = nextStart != null ? Math.max(startSec + 1, nextStart) : startSec + 5;
                const description = (km.description || '').trim();
                if (!description) return null;
                return { startSec, endSec, description };
            })
            .filter((b): b is SceneBeat => b !== null);
    }

    if (scenes.length > 0) {
        return scenes
            .map((sc, i) => {
                const startSec = parseTimestamp(sc.start) ?? i * 3;
                const endSec = parseTimestamp(sc.end) ?? startSec + 3;
                const parts = [sc.description, sc.on_screen_text].filter(Boolean);
                const description = parts.join(' — ').trim();
                if (!description) return null;
                return { startSec, endSec: Math.max(endSec, startSec + 1), description };
            })
            .filter((b): b is SceneBeat => b !== null);
    }

    return [];
}

function inferSourceDuration(
    durationSec: number | undefined,
    beats: SceneBeat[],
): number {
    if (durationSec && durationSec > 0) return durationSec;
    if (beats.length > 0) {
        return Math.max(...beats.map((b) => b.endSec));
    }
    return MAX_TARGET_DURATION_SEC;
}

function scaleBeats(beats: SceneBeat[], sourceDuration: number, targetDuration: number): SceneBeat[] {
    if (beats.length === 0) return beats;
    const scale = targetDuration / sourceDuration;
    return beats.map((b) => ({
        startSec: b.startSec * scale,
        endSec: Math.min(targetDuration, b.endSec * scale),
        description: b.description,
    }));
}

function detectDynamicSpeaking(
    breakdown: AnalyticsBreakdown,
    beats: SceneBeat[],
    combinedText: string,
): boolean {
    if (beats.length < 2) return false;
    if (CINEMATIC_NEG.test(combinedText)) return false;

    const hasTranscript = (breakdown.audio?.transcript?.length ?? 0) > 0;
    const hasSpeakCue = SPEAK_CUES.test(combinedText);
    const hasHumanAction = beats.some((b) => HUMAN_ACTION.test(b.description)) || HUMAN_ACTION.test(combinedText);

    return (hasTranscript || hasSpeakCue) && (hasHumanAction || beats.length >= 3);
}

function flattenTranscript(breakdown: AnalyticsBreakdown): string {
    const lines = breakdown.audio?.transcript || [];
    if (!lines.length) return '';
    return lines
        .map((line) => {
            const text = (line.text || '').trim();
            if (!text) return '';
            const ts = line.ts ? `[${line.ts}] ` : '';
            return `${ts}${text}`;
        })
        .filter(Boolean)
        .join('\n');
}

export function buildVideoTemplateBrief(
    post: AnalyticsPost,
    breakdown: AnalyticsBreakdown,
    durationSec: number | undefined,
    selectedCreator: AgentRef | null,
): TemplateBriefResult {
    const beats = collectBeats(breakdown);
    const sourceDuration = inferSourceDuration(durationSec, beats);
    const targetDurationSec = Math.min(MAX_TARGET_DURATION_SEC, sourceDuration);
    const scaledBeats = scaleBeats(beats, sourceDuration, targetDurationSec);

    const hookText = [
        breakdown.hook?.on_screen_text,
        breakdown.hook?.visual,
        breakdown.hook?.why_it_works,
    ].filter(Boolean).join(' ');

    const combinedText = [
        hookText,
        post.caption,
        breakdown.summary,
        ...(breakdown.takeaways || []),
        flattenTranscript(breakdown),
        ...scaledBeats.map((b) => b.description),
    ].join(' ');

    const useDynamicSpeaking = detectDynamicSpeaking(breakdown, scaledBeats, combinedText);
    const refs = selectedCreator ? [selectedCreator] : [];

    const sections: string[] = [];

    if (selectedCreator) {
        sections.push(`Recreate this competitor template starring @${selectedCreator.tag}.`);
    } else {
        sections.push('Recreate this competitor video as UGC with a presenter (@influencer — pick your creator below).');
    }

    if (sourceDuration > MAX_TARGET_DURATION_SEC) {
        sections.push(
            `Source video was ${Math.round(sourceDuration)}s — recreate in ≤${MAX_TARGET_DURATION_SEC}s, compressing beats proportionally.`,
        );
    } else {
        sections.push(`Target length: ${Math.round(targetDurationSec)} seconds.`);
    }

    if (useDynamicSpeaking) {
        if (selectedCreator) {
            sections.push(`@${selectedCreator.tag} speaks on camera while moving through these scenes:`);
        } else {
            sections.push('Presenter speaks on camera while walking through multiple scenes, then continue through these beats:');
        }
    } else if (scaledBeats.length > 0) {
        sections.push('Scene-by-scene recreation guide:');
    }

    if (scaledBeats.length > 0) {
        const sceneLines = scaledBeats.map((b, i) => {
            const start = formatTimestamp(b.startSec);
            const end = formatTimestamp(b.endSec);
            return `Scene ${i + 1} (${start}–${end}): ${b.description}`;
        });
        sections.push(sceneLines.join('\n'));
    } else {
        if (hookText) sections.push(`Hook:\n${hookText.trim()}`);
        if (breakdown.summary) sections.push(`Summary:\n${breakdown.summary}`);
    }

    if (post.caption) {
        sections.push(`Original caption:\n${post.caption}`);
    }

    const transcript = flattenTranscript(breakdown);
    if (transcript) {
        sections.push(`Suggested dialogue (adapt to fit ${targetDurationSec}s):\n${transcript}`);
    }

    if (breakdown.takeaways?.length) {
        sections.push(`Takeaways:\n${breakdown.takeaways.map((t) => `• ${t}`).join('\n')}`);
    }

  const attribution = [
        post.platform ? `Platform: ${post.platform}` : '',
        post.username ? `Source: @${post.username}` : '',
        post.post_url ? `Reference: ${post.post_url}` : '',
    ].filter(Boolean).join(' · ');
    if (attribution) sections.push(attribution);

    if (!selectedCreator) {
        sections.push('[[CREATOR_SELECTOR]]');
    }

    let brief = sections.join('\n\n').trim();
    if (brief.length > MAX_BRIEF_CHARS) {
        brief = `${brief.slice(0, MAX_BRIEF_CHARS - 3)}...`;
    }

    return { brief, refs, useDynamicSpeaking, targetDurationSec };
}
