'use client';

import { useState, useEffect, useRef, useCallback, useMemo, forwardRef, useImperativeHandle } from 'react';
import {
    creativeFetch,
    getAgentThread,
    prewarmAgentSession,
    resetAgentThread,
    stopAgent,
    streamAgent,
    uploadAgentFile,
    transcribeAudio,
    type AgentTurn,
    type AgentArtifact,
    type AgentRef,
    type AgentStreamEvent,
    type CaptionStylePreview,
} from '@/lib/creative-os-api';
import { CaptionStylePreviewCard } from '@/components/captions/CaptionStylePreviewCard';
import { supabase } from '@/lib/supabaseClient';
import { useTranslation } from '@/lib/i18n';
import { FEATURE_AGENTPANEL_EDITOR_ROUTING } from '@/editor/flags';
import { classifyEditorAgentRoute } from '@/editor-agent/route-intent';

export interface AgentPanelHandle {
    useSeedance: boolean;
    toggleSeedance: () => void;
    running: boolean;
    turnsCount: number;
    reset: () => void;
}

export interface AgentPanelState {
    useSeedance: boolean;
    running: boolean;
    turnsCount: number;
}

interface AgentPanelProps {
    projectId: string;
    onArtifact?: () => void;
    /** When true, renders as a full-height embedded panel instead of a floating modal. */
    embedded?: boolean;
    /** When set in embedded mode, shows a collapse button in the header that calls this. */
    onCollapse?: () => void;
    /** When true, hides the internal header (parent renders its own). */
    hideHeader?: boolean;
    /** Notifies parent of internal state changes (running, turns, seedance toggle) */
    onStateChange?: (state: AgentPanelState) => void;
    /** When set, intercepts submit — parent handles the prompt (e.g. home dashboard creates a project). */
    onSubmitOverride?: (prompt: string) => void;
    /** Pre-populate textarea and auto-submit once on mount. */
    initialBrief?: string;
    /** Pre-populate refs for auto-submit (e.g. @mentions from dashboard). */
    initialRefs?: AgentRef[];
    /** Pre-set the Seedance toggle (e.g. from dashboard composer). */
    initialUseSeedance?: boolean;
    /** Fires when the agent starts a generation job, so the parent can switch the gallery tab. */
    onJobStart?: (kind: 'image' | 'video') => void;
    /**
     * When set, edit-intent prompts (e.g. "trim clip 2 to 5 seconds") are routed to
     * the editor-AI module (/api/editor/ai) instead of the managed agent stream.
     * Generation-intent prompts still go through /api/agent/stream as today.
     * Unset = current behavior (all prompts go to managed agent).
     */
    jobId?: string | null;
}

interface MentionItem {
    type: AgentRef['type'];
    tag: string;          // unique @-token
    name: string;         // display label
    image_url?: string;   // thumbnail
    views?: string[];     // additional shots/views (product_views / character_views) — profile first, then extras
    ref: AgentRef;        // payload sent to backend
    product_type?: 'physical' | 'digital';
    // For digital products: maps a first_frame_url (shown in the picker grid)
    // to its underlying app clip so finalizeMention can attach app_clip_id.
    clipsByFrame?: Record<string, { clip_id: string; video_url?: string }>;
}

interface AttachedFile {
    id: string;            // local id (uuid)
    type: 'image' | 'video';
    name: string;
    status: 'uploading' | 'ready' | 'error';
    url?: string;          // public URL (set when status==='ready')
    previewUrl?: string;   // local object URL for thumbnail
    error?: string;
    tag?: string;          // @upload_xxx tag (set when ready)
}

function slugify(s: string): string {
    return (s || '').toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
}

function formatElapsed(sec: number): string {
    if (sec < 0) sec = 0;
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s < 10 ? '0' : ''}${s}`;
}

// Maps a backend tool_call event to a user-facing activity label. Specific
// long-running jobs (animate, generate_video, render_edited_video, etc.) keep
// their detailed copy; everything else falls into a phase category so the
// indicator varies instead of flashing "Thinking…" for every call.
function toolActivityLabel(
    name: string,
    mode: string | null | undefined,
    summary: string | null | undefined,
    t: (k: string) => string,
): string {
    const lmode = (mode || '').toLowerCase();
    const lsum = (summary || '').toLowerCase();

    if (name === 'animate_image') return t('creativeOs.agent.activityAnimatingKling');
    if (name === 'generate_video') {
        const isSeedance = lmode.startsWith('seedance_2') || lsum.includes('seedance_2');
        const isCinematic = lmode === 'cinematic_video' || lsum.includes('"mode":"cinematic');
        return isSeedance
            ? t('creativeOs.agent.activityGeneratingSeedanceFull')
            : isCinematic
                ? t('creativeOs.agent.activityGeneratingCinematicFull')
                : t('creativeOs.agent.activityGeneratingUgcFull');
    }
    if (name === 'create_ugc_video' || name === 'create_clone_video') {
        return t('creativeOs.agent.activityProducingFull').replace('{name}', name);
    }
    if (name === 'create_bulk_campaign') return t('creativeOs.agent.activityBulkCampaign');
    if (name === 'render_edited_video') return t('creativeOs.agent.activityRenderingEditFull');

    if (name === 'generate_image' || name === 'generate_influencer'
        || name === 'generate_identity' || name === 'generate_product_shots') {
        return t('creativeOs.agent.activityGeneratingImage');
    }

    if (name.startsWith('list_') || name.startsWith('get_') || name === 'estimate_credits') {
        return t('creativeOs.agent.activityChecking');
    }
    if (name.startsWith('analyze_')) return t('creativeOs.agent.activityAnalyzing');
    if (name === 'generate_scripts' || name === 'generate_ai_script' || name === 'generate_caption') {
        return t('creativeOs.agent.activityWriting');
    }
    if (name === 'caption_video') return t('creativeOs.agent.activityCaptioning');
    if (name === 'list_caption_styles') return t('creativeOs.agent.activityShowingCaptionStyles');
    if (name === 'add_voiceover') return t('creativeOs.agent.activityAddingVoiceover');
    if (name === 'combine_videos') {
        // combine_videos doubles as the "add music to a single video" path.
        // Pick a more specific label when the summary indicates a music_prompt
        // and/or only one video_url — so the user sees "Adding background music…"
        // instead of "Combining videos…" during that flow.
        const hasMusic = lsum.includes('music_prompt');
        const urlCount = (lsum.match(/https?:\/\//g) || []).length;
        const isSingleVideoMusic = hasMusic && urlCount <= 1;
        if (isSingleVideoMusic) return t('creativeOs.agent.activityAddingMusic');
        if (hasMusic) return t('creativeOs.agent.activityCombiningWithMusic');
        return t('creativeOs.agent.activityCombining');
    }
    if (name === 'schedule_posts' || name === 'cancel_scheduled_post') {
        return t('creativeOs.agent.activityScheduling');
    }
    if (name.startsWith('create_') || name === 'manage_app_clips') {
        return t('creativeOs.agent.activitySettingUp');
    }

    return t('creativeOs.agent.activityWorking');
}

export const AgentPanel = forwardRef(function AgentPanel({ projectId, onArtifact, embedded = false, onCollapse, hideHeader = false, onStateChange, onSubmitOverride, initialBrief, initialRefs, initialUseSeedance, onJobStart, jobId }: AgentPanelProps, ref: React.Ref<AgentPanelHandle>) {
    const { lang, t } = useTranslation();
    const [open, setOpen] = useState(false);
    const [brief, setBrief] = useState('');
    const [turns, setTurns] = useState<AgentTurn[]>([]);
    const [sessionId, setSessionId] = useState<string | null>(null);
    const [running, setRunning] = useState(false);
    const [activity, setActivity] = useState<string>('');
    const [error, setError] = useState<string | null>(null);
    // ── Perceived-latency UX state ────────────────────────────────────────
    // `activityStartedAt` anchors the mm:ss counter next to the activity label;
    // `lastHeartbeatAt` re-triggers the pulsing dot on each SSE keepalive so
    // the UI visibly breathes during minutes-long tool runs; the artifact
    // counter + flash tick give feedback when a multi-artifact job emits
    // intermediate results.
    const [activityStartedAt, setActivityStartedAt] = useState<number | null>(null);
    const [elapsedSec, setElapsedSec] = useState(0);
    const [lastHeartbeatAt, setLastHeartbeatAt] = useState(0);
    const [artifactsReadyCount, setArtifactsReadyCount] = useState(0);
    const [artifactFlashTick, setArtifactFlashTick] = useState(0);
    // The activity pill is suppressed until the agent fires its first
    // `tool_call` event. During the pre-tool synthesis window the placeholder
    // bubble's breathing dots are the single source of "I'm thinking" feedback
    // — so we don't compete with a static "Processing…" pill that reads dead.
    const [sawToolCall, setSawToolCall] = useState(false);
    // Cycles every 4s while the pill is showing a generic label, so the user
    // sees motion in the copy itself instead of a static "Processing…".
    const [pillTick, setPillTick] = useState(0);
    // Start `true` when initialBrief is provided so the auto-submit Phase 2
    // effect waits for hydration to complete (otherwise setTurns on hydrate
    // wipes the user turn appended by the auto-fired handleRun).
    const [hydrating, setHydrating] = useState(Boolean(initialBrief));
    const abortRef = useRef<AbortController | null>(null);
    const reconnectRef = useRef<{ timer: ReturnType<typeof setTimeout> | null; stableSince: number; lastHash: string }>({ timer: null, stableSince: 0, lastHash: '' });
    const scrollerRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // ── File attachments ────────────────────────────────────────────────
    const [attachments, setAttachments] = useState<AttachedFile[]>([]);
    const [useSeedance, setUseSeedance] = useState(initialUseSeedance ?? false);

    // Sync state locally to parent for reactive header elements
    useEffect(() => {
        if (onStateChange) {
            onStateChange({ useSeedance, running, turnsCount: turns.length });
        }
    }, [useSeedance, running, turns.length, onStateChange]);

    // Tick the elapsed counter once per second while a run is active. Keeps
    // the activity label alive ("Generating video · 1:32") instead of showing
    // a frozen string for minutes at a time.
    useEffect(() => {
        if (!running || !activityStartedAt) {
            setElapsedSec(0);
            return;
        }
        // Seed immediately so the counter doesn't wait a full second to show 0:00.
        setElapsedSec(Math.floor((Date.now() - activityStartedAt) / 1000));
        const id = setInterval(() => {
            setElapsedSec(Math.floor((Date.now() - activityStartedAt) / 1000));
        }, 1000);
        return () => clearInterval(id);
    }, [running, activityStartedAt]);

    // Cycle the pill rotation every 4s while a run is active. Strictly
    // cosmetic — only the *generic* "Processing…" label is replaced by the
    // rotation; specific tool labels (e.g. "Generating image…") are left as-is.
    useEffect(() => {
        if (!running) {
            setPillTick(0);
            return;
        }
        const id = setInterval(() => setPillTick((n) => n + 1), 4000);
        return () => clearInterval(id);
    }, [running]);

    // The label actually rendered in the pill. Only swap when the activity is
    // the generic "Processing…" / "Thinking…" string — everything else is a
    // specific tool label we want to keep verbatim.
    const genericProcessing = t('creativeOs.agent.activityProcessing');
    const genericThinking = t('creativeOs.agent.activityThinking');
    const isGenericActivity = activity === genericProcessing || activity === genericThinking;
    const rotationLabels = [
        t('creativeOs.agent.activityWorkingOnIt'),
        t('creativeOs.agent.activityGeneratingShort'),
        t('creativeOs.agent.activityAlmostThere'),
    ];
    const displayActivity = isGenericActivity
        ? rotationLabels[pillTick % rotationLabels.length]
        : activity;

    const handleFilesPicked = useCallback(async (files: FileList | null) => {
        if (!files || files.length === 0) return;
        const accepted: AttachedFile[] = [];
        for (const file of Array.from(files)) {
            const ct = file.type || '';
            const kind: 'image' | 'video' | null = ct.startsWith('image/')
                ? 'image'
                : ct.startsWith('video/')
                    ? 'video'
                    : null;
            if (!kind) {
                setError(t('creativeOs.agent.unsupportedFile').replace('{type}', ct || 'unknown'));
                continue;
            }
            const id = (typeof crypto !== 'undefined' && 'randomUUID' in crypto)
                ? crypto.randomUUID()
                : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
            accepted.push({
                id,
                type: kind,
                name: file.name,
                status: 'uploading',
                previewUrl: URL.createObjectURL(file),
            });
        }
        if (accepted.length === 0) return;
        setAttachments((prev) => [...prev, ...accepted]);

        // Upload each in parallel
        await Promise.all(
            accepted.map(async (att, idx) => {
                const file = files[idx];
                try {
                    const result = await uploadAgentFile(file);
                    const tag = `upload_${att.id.slice(0, 8).replace(/-/g, '')}`;
                    setAttachments((prev) =>
                        prev.map((a) =>
                            a.id === att.id
                                ? { ...a, status: 'ready', url: result.url, tag }
                                : a,
                        ),
                    );
                } catch (err) {
                    setAttachments((prev) =>
                        prev.map((a) =>
                            a.id === att.id
                                ? { ...a, status: 'error', error: err instanceof Error ? err.message : String(err) }
                                : a,
                        ),
                    );
                }
            }),
        );
    }, []);

    const removeAttachment = useCallback((id: string) => {
        setAttachments((prev) => {
            const target = prev.find((a) => a.id === id);
            if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
            return prev.filter((a) => a.id !== id);
        });
    }, []);

    // Revoke object URLs on unmount
    useEffect(() => {
        return () => {
            for (const a of attachments) {
                if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
            }
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // ── @ mention state ─────────────────────────────────────────────────
    const [products, setProducts] = useState<any[]>([]);
    const [influencers, setInfluencers] = useState<any[]>([]);
    const [projectImages, setProjectImages] = useState<any[]>([]);
    const [projectVideos, setProjectVideos] = useState<any[]>([]);
    const [mentionsLoaded, setMentionsLoaded] = useState(false);
    const [mentionOpen, setMentionOpen] = useState(false);
    const [mentionFilter, setMentionFilter] = useState('');
    const [mentionIndex, setMentionIndex] = useState(0);
    const [mentionCursorStart, setMentionCursorStart] = useState(0);
    // When set, the dropdown shows a shot picker for the given asset instead
    // of the normal mention list. Populated when the user clicks a product or
    // model that has multiple views/shots available.
    const [shotPickerItem, setShotPickerItem] = useState<MentionItem | null>(null);
    // Composer "+" menu state
    const [menuOpen, setMenuOpen] = useState(false);
    const [historyOpen, setHistoryOpen] = useState(false);
    // Voice dictation state
    const [recording, setRecording] = useState(false);
    const [transcribing, setTranscribing] = useState(false);
    const [audioLevel, setAudioLevel] = useState(0);
    const mediaRecorderRef = useRef<MediaRecorder | null>(null);
    const audioChunksRef = useRef<Blob[]>([]);
    const audioStreamRef = useRef<MediaStream | null>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const silenceTimerRef = useRef<number | null>(null);
    // Refs the user has actually inserted into the current draft, keyed by tag.
    const [activeRefs, setActiveRefs] = useState<Map<string, AgentRef>>(new Map());

    const loadMentionData = useCallback(async () => {
        if (mentionsLoaded) return;
        try {
            const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
            const token = (await supabase.auth.getSession()).data.session?.access_token;
            const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
            const [prodRes, infRes, imgs, vids] = await Promise.all([
                fetch(`${apiBase}/api/products`, { headers }).then(r => r.ok ? r.json() : []),
                fetch(`${apiBase}/influencers`, { headers }).then(r => r.ok ? r.json() : []),
                creativeFetch<any[]>(`/creative-os/projects/${projectId}/assets/images`).catch(() => []),
                creativeFetch<any[]>(`/creative-os/projects/${projectId}/assets/videos`).catch(() => []),
            ]);
            setProducts(prodRes || []);
            setInfluencers(infRes || []);
            setProjectImages((imgs || []).filter((i: any) => i.image_url));
            setProjectVideos((vids || []).filter((v: any) => v.final_video_url || v.preview_url));
            setMentionsLoaded(true);
        } catch (err) {
            console.warn('mention data load failed:', err);
        }
    }, [mentionsLoaded, projectId]);

    // Reset cached mention data when project changes
    useEffect(() => {
        setMentionsLoaded(false);
        setProducts([]);
        setInfluencers([]);
        setProjectImages([]);
        setProjectVideos([]);
    }, [projectId]);

    const mentionItems = useMemo<MentionItem[]>(() => {
        const items: MentionItem[] = [];
        for (const p of products) {
            const name = p.name || p.product_name || 'product';
            const isDigital = p.type === 'digital';
            const appClips = Array.isArray(p.app_clips) ? p.app_clips.filter((c: any) => c.first_frame_url) : [];

            let views: string[] = [];
            let clipsByFrame: Record<string, { clip_id: string; video_url?: string }> | undefined;
            let thumb = p.image_url;

            if (isDigital && appClips.length) {
                views = appClips.map((c: any) => c.first_frame_url);
                clipsByFrame = Object.fromEntries(
                    appClips.map((c: any) => [c.first_frame_url, { clip_id: c.id, video_url: c.video_url }])
                );
                if (!thumb) thumb = views[0];
            } else {
                const extraViews = Array.isArray(p.product_views) ? p.product_views.filter(Boolean) : [];
                views = p.image_url ? [p.image_url, ...extraViews.filter((v: string) => v !== p.image_url)] : extraViews;
            }

            items.push({
                type: 'product',
                tag: slugify(name),
                name,
                image_url: thumb,
                views: views.length > 1 ? views : undefined,
                product_type: isDigital ? 'digital' : 'physical',
                clipsByFrame,
                ref: {
                    type: 'product',
                    tag: slugify(name),
                    name,
                    id: p.id,
                    image_url: thumb,
                    product_type: isDigital ? 'digital' : 'physical',
                },
            });
        }
        for (const inf of influencers) {
            const name = inf.name || 'model';
            const extraViews = Array.isArray(inf.character_views) ? inf.character_views.filter(Boolean) : [];
            const views = inf.image_url ? [inf.image_url, ...extraViews.filter((v: string) => v !== inf.image_url)] : extraViews;
            items.push({
                type: 'influencer',
                tag: slugify(name),
                name,
                image_url: inf.image_url,
                views: views.length > 1 ? views : undefined,
                ref: { type: 'influencer', tag: slugify(name), name, id: inf.id, image_url: inf.image_url },
            });
        }
        for (const img of projectImages) {
            const baseName = img.product_name || img.campaign_name || 'image';
            const shortId = (img.id || '').slice(0, 8);
            const tag = `${slugify(baseName)}_${shortId}`;
            items.push({
                type: 'image',
                tag,
                name: `${baseName} · ${shortId}`,
                image_url: img.image_url,
                ref: { type: 'image', tag, name: baseName, shot_id: img.id, image_url: img.image_url },
            });
        }
        for (const vid of projectVideos) {
            const baseName = vid.campaign_name || vid.product_name || 'clip';
            const shortId = (vid.id || '').slice(0, 8);
            const tag = `${slugify(baseName)}_${shortId}`;
            const url = vid.final_video_url || vid.video_url;
            items.push({
                type: 'video',
                tag,
                name: `${baseName} · ${shortId}`,
                image_url: vid.preview_url,
                ref: { type: 'video', tag, name: baseName, job_id: vid.id, video_url: url },
            });
        }
        return items;
    }, [products, influencers, projectImages, projectVideos]);

    const filteredMentions = useMemo(() => {
        const f = mentionFilter.toLowerCase();
        if (!f) return mentionItems;
        return mentionItems.filter(m =>
            m.name.toLowerCase().includes(f) || m.tag.includes(f),
        );
    }, [mentionItems, mentionFilter]);

    // Group filtered mentions for the dropdown
    const groupedMentions = useMemo(() => ({
        product: filteredMentions.filter(m => m.type === 'product'),
        influencer: filteredMentions.filter(m => m.type === 'influencer'),
        image: filteredMentions.filter(m => m.type === 'image'),
        video: filteredMentions.filter(m => m.type === 'video'),
    }), [filteredMentions]);

    const orderedMentions = useMemo(
        () => [
            ...groupedMentions.product,
            ...groupedMentions.influencer,
            ...groupedMentions.image,
            ...groupedMentions.video,
        ],
        [groupedMentions],
    );

    // Hydrate when panel opens or project changes
    useEffect(() => {
        // In embedded mode, hydrate immediately on mount (no `open` gate).
        // In floating mode, only hydrate when the panel is opened.
        if (!embedded && !open) return;
        if (!projectId) return;
        let cancelled = false;
        setHydrating(true);
        getAgentThread(projectId)
            .then((thread) => {
                if (cancelled) return;
                setTurns(thread.turns || []);
                setSessionId(thread.session_id);
                // Eagerly create the Anthropic session in the background so
                // the user's first send doesn't pay the ~1-2s session-create
                // round-trip. Skip when a session already exists (returning
                // user) or no project context.
                if (!thread.session_id && projectId) {
                    void prewarmAgentSession(projectId);
                }
            })
            .catch((err) => {
                if (cancelled) return;
                console.warn('agent thread hydrate failed:', err);
            })
            .finally(() => {
                if (!cancelled) setHydrating(false);
            });
        return () => {
            cancelled = true;
        };
    }, [open, projectId, embedded]);

    // Auto-start: if initialBrief is provided, pre-fill textarea and auto-submit once
    const hasAutoSubmitted = useRef(false);
    const pendingBriefRef = useRef<string | null>(null);
    // Tags seeded from initialRefs (dashboard uploads / pre-populated mentions) —
    // always forwarded regardless of whether @tag appears in the brief text.
    const initialRefTagsRef = useRef<Set<string>>(new Set());

    // Phase 1: store the brief and pre-fill textarea (runs early)
    useEffect(() => {
        if (!initialBrief || hasAutoSubmitted.current) return;
        hasAutoSubmitted.current = true;
        setBrief(initialBrief);
        pendingBriefRef.current = initialBrief;
        // Force-open in floating mode so the hydration effect runs and Phase 2
        // eventually fires. In embedded mode this is a no-op.
        setOpen(true);
        // Pre-populate activeRefs from initialRefs so handleRun includes them
        if (initialRefs && initialRefs.length > 0) {
            const refMap = new Map<string, AgentRef>();
            const seedTags = new Set<string>();
            for (const r of initialRefs) {
                refMap.set(r.tag, r);
                seedTags.add(r.tag);
            }
            setActiveRefs(refMap);
            initialRefTagsRef.current = seedTags;
        }
        console.log('[AgentPanel] Auto-submit: stored pending brief', initialBrief.slice(0, 50), 'refs:', initialRefs?.length ?? 0);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [initialBrief]);

    // Auto-scroll on new content
    useEffect(() => {
        const el = scrollerRef.current;
        if (el) el.scrollTop = el.scrollHeight;
    }, [turns, activity, hydrating]);

    // Cancel reconnect polling on unmount so we don't leak timers.
    useEffect(() => {
        const ref = reconnectRef.current;
        return () => {
            if (ref.timer) {
                clearTimeout(ref.timer);
                ref.timer = null;
            }
        };
    }, []);

    const handleRun = useCallback(async (overrideText?: string) => {
        const text = (overrideText || brief).trim();
        const readyAttachments = attachments.filter((a) => a.status === 'ready' && a.url);
        const stillUploading = attachments.some((a) => a.status === 'uploading');
        if (stillUploading) {
            setError(t('creativeOs.agent.uploadWait'));
            return;
        }
        if ((!text && readyAttachments.length === 0) || running) return;

        // Build refs payload from active mentions that are still present in
        // the final text (user may have deleted a tag manually).
        const refsForRequest: AgentRef[] = [];
        for (const [tag, ref] of activeRefs.entries()) {
            if (text.includes(`@${tag}`) || initialRefTagsRef.current.has(tag)) {
                refsForRequest.push(ref);
            }
        }
        // Include uploaded attachments as refs (always sent — user explicitly attached them).
        for (const att of readyAttachments) {
            const ref: AgentRef = {
                type: att.type,
                tag: att.tag || `upload_${att.id.slice(0, 8)}`,
                name: att.name,
                ...(att.type === 'image'
                    ? { image_url: att.url }
                    : { video_url: att.url }),
            };
            refsForRequest.push(ref);
        }

        const finalText = text || (readyAttachments.length > 0
            ? `(uploaded ${readyAttachments.length} file${readyAttachments.length === 1 ? '' : 's'})`
            : '');

        const userTurn: AgentTurn = {
            role: 'user',
            text: finalText,
            ts: Date.now(),
            refs: refsForRequest.length > 0 ? refsForRequest : undefined,
        };
        const placeholder: AgentTurn = {
            role: 'agent',
            text: '',
            artifacts: [],
            tool_calls: [],
            ts: Date.now() + 1,
        };
        setTurns((prev) => [...prev, userTurn, placeholder]);
        setBrief('');
        setActiveRefs(new Map());
        // Clear attachments (revoke object URLs first)
        setAttachments((prev) => {
            for (const a of prev) {
                if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
            }
            return [];
        });
        setMentionOpen(false);
        setError(null);
        setRunning(true);
        setActivity(t('creativeOs.agent.activityThinking'));
        setActivityStartedAt(Date.now());
        setArtifactsReadyCount(0);
        setArtifactFlashTick(0);
        setLastHeartbeatAt(Date.now());
        setSawToolCall(false);

        // Submit intercept: parent handles the prompt (e.g. home page creates a project)
        if (onSubmitOverride) {
            onSubmitOverride(finalText);
            setRunning(false);
            setActivity('');
            setActivityStartedAt(null);
            return;
        }

        // Cancel any prior reconnect polling — this run takes over.
        if (reconnectRef.current.timer) {
            clearTimeout(reconnectRef.current.timer);
            reconnectRef.current.timer = null;
        }

        const controller = new AbortController();
        abortRef.current = controller;

        // When the SSE drops mid-run (Railway proxy timeout, mobile nets, etc.)
        // we silently fall back to polling the persisted thread. The agent
        // never shows a red error pill — recovery is invisible to the user.
        const stopThreadPolling = () => {
            if (reconnectRef.current.timer) {
                clearTimeout(reconnectRef.current.timer);
                reconnectRef.current.timer = null;
            }
        };
        const startThreadPolling = () => {
            stopThreadPolling();
            reconnectRef.current.stableSince = 0;
            reconnectRef.current.lastHash = '';
            const tick = async () => {
                try {
                    const thread = await getAgentThread(projectId);
                    const nextTurns = thread.turns || [];
                    const hash = JSON.stringify(nextTurns.map((t: AgentTurn) => [
                        t.role, t.text, (t.artifacts || []).length, (t.tool_calls || []).length,
                    ]));
                    if (hash !== reconnectRef.current.lastHash) {
                        reconnectRef.current.lastHash = hash;
                        reconnectRef.current.stableSince = Date.now();
                        setTurns(nextTurns);
                        if (thread.session_id) setSessionId(thread.session_id);
                        onArtifact?.();
                    }
                    // Stop polling once state has been stable for 45s —
                    // the run has almost certainly finished by then.
                    const stableFor = Date.now() - reconnectRef.current.stableSince;
                    if (reconnectRef.current.stableSince && stableFor > 45000) {
                        stopThreadPolling();
                        setRunning(false);
                        setActivity('');
                        setActivityStartedAt(null);
                        abortRef.current = null;
                        return;
                    }
                } catch (err) {
                    console.warn('thread poll failed:', err);
                }
                reconnectRef.current.timer = setTimeout(tick, 3000);
            };
            reconnectRef.current.stableSince = Date.now();
            reconnectRef.current.timer = setTimeout(tick, 1500);
        };

        const updateLastAgentTurn = (mut: (t: AgentTurn) => AgentTurn) => {
            setTurns((prev) => {
                const copy = prev.slice();
                const idx = copy.length - 1;
                if (idx >= 0 && copy[idx].role === 'agent') {
                    copy[idx] = mut({ ...copy[idx] });
                }
                return copy;
            });
        };

        const onEvent = (e: AgentStreamEvent) => {
            switch (e.type) {
                case 'session':
                    setSessionId(e.session_id);
                    break;
                case 'agent_message':
                    // Text has started arriving — clear the thinking indicator now
                    // so the user sees the message instead of a redundant spinner.
                    setActivity('');
                    setTurns((prev) => {
                        const copy = prev.slice();
                        const idx = copy.length - 1;
                        const last = idx >= 0 ? copy[idx] : null;
                        // First agent_message of this run fills the placeholder bubble.
                        // Subsequent agent_messages start their own bubble so each
                        // distinct model utterance renders as a separate pill.
                        if (last && last.role === 'agent' && !last.text && !(last.artifacts || []).length && !(last.tool_calls || []).length) {
                            copy[idx] = { ...last, text: e.text };
                        } else {
                            copy.push({
                                role: 'agent',
                                text: e.text,
                                artifacts: [],
                                tool_calls: [],
                                ts: Date.now(),
                            });
                        }
                        return copy;
                    });
                    break;
                case 'tool_call': {
                    setActivity(toolActivityLabel(e.name, e.mode, e.input_summary, t));
                    setSawToolCall(true);
                    // Reset elapsed anchor + per-tool artifact counter so the
                    // mm:ss heartbeat restarts from 0 for this new tool.
                    setActivityStartedAt(Date.now());
                    setArtifactsReadyCount(0);
                    setArtifactFlashTick(0);
                    updateLastAgentTurn((t) => ({
                        ...t,
                        tool_calls: [
                            ...(t.tool_calls || []),
                            { name: e.name, input_summary: e.input_summary, mode: e.mode ?? null },
                        ],
                    }));
                    // Video-producing tools create a "pending" DB row before the
                    // pipeline finishes. Nudge the gallery to refetch so the
                    // in-progress card appears immediately instead of waiting
                    // for tool_result (which can be 2–4 min away).
                    const videoTools = new Set([
                        'generate_video', 'animate_image',
                        'create_ugc_video', 'create_clone_video',
                        'render_edited_video',
                    ]);
                    const imageTools = new Set([
                        'generate_image', 'generate_image_text_only',
                        'generate_image_alt_versions',
                        'generate_influencer',
                        'generate_identity', 'generate_product_shots',
                    ]);
                    if (videoTools.has(e.name)) {
                        onJobStart?.('video');
                    } else if (imageTools.has(e.name)) {
                        onJobStart?.('image');
                    }
                    break;
                }
                case 'tool_result':
                    // Keep the indicator visible — the model is now synthesizing
                    // its reply from this tool's output and may take a few seconds
                    // before `agent_message` begins streaming. Clearing activity
                    // here creates a dead-zone where the UI looks frozen.
                    setActivity(t('creativeOs.agent.activityProcessing'));
                    // Reset elapsed anchor — counter now reflects post-tool latency
                    // rather than the (completed) tool's runtime.
                    setActivityStartedAt(Date.now());
                    onArtifact?.(); // refresh gallery — tool may have created assets
                    break;
                case 'keepalive':
                    // Bump the heartbeat tick so the activity-row dot remounts
                    // and its pulse animation re-fires — visible proof every 15s
                    // that the connection is still alive during minutes-long tools.
                    setLastHeartbeatAt(Date.now());
                    break;
                case 'artifact': {
                    const art = e.artifact as AgentArtifact;
                    updateLastAgentTurn((t) => ({
                        ...t,
                        artifacts: [...(t.artifacts || []), art],
                    }));
                    setArtifactsReadyCount((c) => c + 1);
                    setArtifactFlashTick(Date.now());
                    onArtifact?.();
                    break;
                }
                case 'done':
                    setRunning(false);
                    setActivity('');
                    setActivityStartedAt(null);
                    abortRef.current = null;
                    onArtifact?.(); // final refresh — pick up anything generated
                    break;
                case 'interrupted':
                    updateLastAgentTurn((t) => ({ ...t, interrupted: true }));
                    setRunning(false);
                    setActivity('');
                    setActivityStartedAt(null);
                    abortRef.current = null;
                    break;
                case 'disconnected':
                    // Silently fall back to polling the persisted thread so
                    // the user sees new turns/artifacts as the backend finishes.
                    // No red error pill — this is invisible recovery.
                    setActivity(t('creativeOs.agent.reconnectingShort'));
                    startThreadPolling();
                    break;
                case 'error':
                    setError(e.message);
                    setRunning(false);
                    setActivity('');
                    setActivityStartedAt(null);
                    abortRef.current = null;
                    break;
            }
        };

        // Phase 2: edit-intent routing. When jobId is attached and the prompt is
        // classified as an edit (trim/caption/music/etc.), we bypass the managed
        // agent stream and hit the editor-AI module directly. The response fills
        // the placeholder turn just like a normal agent_message would.
        const editorRoute =
            FEATURE_AGENTPANEL_EDITOR_ROUTING && jobId
                ? classifyEditorAgentRoute(text, jobId)
                : 'managed';

        if (editorRoute === 'editor') {
            try {
                setActivity('');
                const stateRes = await fetch(`/api/editor/state/${jobId}`, {
                    method: 'GET',
                    credentials: 'include',
                });
                const timelineContext = stateRes.ok ? await stateRes.json() : null;
                const aiRes = await fetch('/api/editor/ai', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        messages: [{ role: 'user', content: text }],
                        timelineContext,
                    }),
                });
                if (!aiRes.ok) {
                    const errBody = await aiRes.json().catch(() => ({ error: aiRes.statusText }));
                    throw new Error(errBody.error || `Editor AI request failed (${aiRes.status})`);
                }
                const { text: replyText } = (await aiRes.json()) as { text: string };
                updateLastAgentTurn((t) => ({ ...t, text: replyText }));
            } catch (err) {
                const msg = err instanceof Error ? err.message : String(err);
                setError(msg);
            } finally {
                setRunning(false);
                setActivity('');
                setActivityStartedAt(null);
                abortRef.current = null;
            }
            return;
        }

        try {
            await streamAgent(text, projectId, onEvent, controller.signal, refsForRequest, useSeedance, lang);
        } catch (err) {
            if ((err as Error).name === 'AbortError') {
                updateLastAgentTurn((t) => ({ ...t, interrupted: true }));
            } else {
                const msg = err instanceof Error ? err.message : String(err);
                // 409 concurrency guard — stream never started. Rewind the
                // optimistic user + placeholder turns and surface the error.
                if (msg.includes('already running')) {
                    setTurns((prev) => prev.slice(0, -2));
                    setError(msg);
                } else if (msg.includes('Agent stream error:') || msg.includes('401') || msg.includes('403') || msg.includes('400')) {
                    // Hard server errors deserve a visible message.
                    setError(msg);
                } else {
                    // Transient connection failure — silently fall back to
                    // polling the persisted thread. No red error pill.
                    console.warn('stream failed, polling thread:', msg);
                    setActivity(t('creativeOs.agent.reconnectingShort'));
                    startThreadPolling();
                    return;
                }
            }
        } finally {
            setRunning(false);
            setActivity('');
            setActivityStartedAt(null);
            abortRef.current = null;
        }
    }, [brief, running, projectId, onArtifact, activeRefs, attachments, onSubmitOverride, useSeedance, jobId]);

    // Phase 2: fire handleRun AFTER hydration completes (hydrating: true → false)
    // This ensures the panel is fully initialized before auto-submitting.
    useEffect(() => {
        if (hydrating) return; // still hydrating, wait
        if (pendingBriefRef.current) {
            const text = pendingBriefRef.current;
            pendingBriefRef.current = null;
            console.log('[AgentPanel] Auto-submit: firing handleRun with', text.slice(0, 50));
            handleRun(text);
        }
    }, [hydrating, handleRun]);

    // ── @ mention input handlers ────────────────────────────────────────
    const handleBriefChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
        const val = e.target.value;
        const cursor = e.target.selectionStart;
        setBrief(val);

        const before = val.slice(0, cursor);
        const atMatch = before.match(/@([\w_]*)$/);
        if (atMatch) {
            const filter = atMatch[1];
            setMentionFilter(filter);
            setMentionCursorStart(cursor - filter.length - 1);
            setMentionIndex(0);
            if (!mentionsLoaded) loadMentionData();
            setMentionOpen(true);
        } else {
            setMentionOpen(false);
        }
    };

    const finalizeMention = useCallback((item: MentionItem, chosenImageUrl?: string) => {
        const cursor = textareaRef.current?.selectionStart ?? brief.length;
        const before = brief.slice(0, mentionCursorStart);
        const after = brief.slice(cursor);
        const tagText = `@${item.tag}`;
        const newBrief = before + tagText + ' ' + after;
        setBrief(newBrief);
        let finalRef: AgentRef = chosenImageUrl
            ? { ...item.ref, image_url: chosenImageUrl }
            : item.ref;
        if (chosenImageUrl && item.clipsByFrame && item.clipsByFrame[chosenImageUrl]) {
            finalRef = { ...finalRef, app_clip_id: item.clipsByFrame[chosenImageUrl].clip_id };
        } else if (!chosenImageUrl && item.clipsByFrame) {
            // Digital product with a single app clip — auto-attach it.
            const entries = Object.entries(item.clipsByFrame);
            if (entries.length === 1) {
                const [frameUrl, { clip_id }] = entries[0];
                finalRef = { ...finalRef, image_url: frameUrl, app_clip_id: clip_id };
            }
        }
        setActiveRefs((prev) => {
            const next = new Map(prev);
            next.set(item.tag, finalRef);
            return next;
        });
        setMentionOpen(false);
        setShotPickerItem(null);
        // restore focus + place caret after the inserted tag
        setTimeout(() => {
            const pos = before.length + tagText.length + 1;
            textareaRef.current?.focus();
            textareaRef.current?.setSelectionRange(pos, pos);
        }, 0);
    }, [brief, mentionCursorStart]);

    const insertMention = useCallback((item: MentionItem) => {
        // Products and models with multiple shots open a sub-picker so the
        // user can choose which image to reference. Everything else inserts
        // immediately with its primary image.
        if ((item.type === 'product' || item.type === 'influencer') && item.views && item.views.length > 1) {
            setShotPickerItem(item);
            return;
        }
        finalizeMention(item);
    }, [finalizeMention]);

    const openReferenceDropdown = useCallback(() => {
        const el = textareaRef.current;
        const cursor = el?.selectionStart ?? brief.length;
        const before = brief.slice(0, cursor);
        const after = brief.slice(cursor);
        const newBrief = before + '@' + after;
        setBrief(newBrief);
        setMentionFilter('');
        setMentionCursorStart(cursor);
        setMentionIndex(0);
        if (!mentionsLoaded) loadMentionData();
        setMentionOpen(true);
        setTimeout(() => {
            const pos = cursor + 1;
            textareaRef.current?.focus();
            textareaRef.current?.setSelectionRange(pos, pos);
        }, 0);
    }, [brief, mentionsLoaded, loadMentionData]);

    const handleBriefKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (mentionOpen && orderedMentions.length > 0) {
            if (e.key === 'ArrowDown') {
                e.preventDefault();
                setMentionIndex((i) => Math.min(i + 1, orderedMentions.length - 1));
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                setMentionIndex((i) => Math.max(i - 1, 0));
                return;
            }
            if (e.key === 'Enter' || e.key === 'Tab') {
                e.preventDefault();
                insertMention(orderedMentions[mentionIndex]);
                return;
            }
            if (e.key === 'Escape') {
                e.preventDefault();
                setMentionOpen(false);
                return;
            }
        }
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleRun();
        }
    };

    const startRecording = useCallback(async () => {
        if (recording || transcribing) return;
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioStreamRef.current = stream;
            const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : MediaRecorder.isTypeSupported('audio/webm')
                    ? 'audio/webm'
                    : MediaRecorder.isTypeSupported('audio/mp4')
                        ? 'audio/mp4'
                        : '';
            const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
            audioChunksRef.current = [];
            recorder.ondataavailable = (e) => {
                if (e.data && e.data.size > 0) audioChunksRef.current.push(e.data);
            };
            recorder.onstop = async () => {
                const chunks = audioChunksRef.current;
                audioChunksRef.current = [];
                audioStreamRef.current?.getTracks().forEach((t) => t.stop());
                audioStreamRef.current = null;
                if (chunks.length === 0) return;
                const blob = new Blob(chunks, { type: recorder.mimeType || 'audio/webm' });
                setTranscribing(true);
                try {
                    const { text } = await transcribeAudio(blob);
                    if (text) {
                        setBrief((prev) => {
                            const sep = prev && !prev.endsWith(' ') ? ' ' : '';
                            return prev + sep + text;
                        });
                        setTimeout(() => textareaRef.current?.focus(), 0);
                    }
                } catch (err) {
                    setError(err instanceof Error ? err.message : String(err));
                } finally {
                    setTranscribing(false);
                }
            };
            mediaRecorderRef.current = recorder;
            recorder.start();
            setRecording(true);

            // Auto-stop after 3s of continuous silence, and drive the
            // live waveform visualizer on the mic button. RMS baseline
            // is calibrated from the first ~600ms so ambient noise /
            // AGC boost doesn't prevent silence detection.
            const AC: typeof AudioContext | undefined =
                window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
            if (AC) {
                const ac = new AC();
                audioContextRef.current = ac;
                if (ac.state === 'suspended') await ac.resume().catch(() => {});
                const source = ac.createMediaStreamSource(stream);
                const analyser = ac.createAnalyser();
                analyser.fftSize = 1024;
                source.connect(analyser);
                const buf = new Uint8Array(analyser.fftSize);
                const startedAt = Date.now();
                let lastSoundAt = Date.now();
                let baseline = 0;       // max RMS seen during calibration
                let hasCalibrated = false;
                const SILENCE_MS = 3000;
                const CALIBRATION_MS = 600;
                silenceTimerRef.current = window.setInterval(() => {
                    analyser.getByteTimeDomainData(buf);
                    let sumSq = 0;
                    for (let i = 0; i < buf.length; i++) {
                        const v = (buf[i] - 128) / 128;
                        sumSq += v * v;
                    }
                    const rms = Math.sqrt(sumSq / buf.length);

                    // Smooth level for UI (scale so normal speech ≈ 1).
                    setAudioLevel((prev) => {
                        const target = Math.min(1, rms * 8);
                        return prev * 0.5 + target * 0.5;
                    });

                    const elapsed = Date.now() - startedAt;
                    if (elapsed < CALIBRATION_MS) {
                        if (rms > baseline) baseline = rms;
                        lastSoundAt = Date.now();
                        return;
                    }
                    if (!hasCalibrated) {
                        hasCalibrated = true;
                        // Threshold is baseline * 2.5 with a floor of 0.03
                        // and a ceiling of 0.15 (very noisy rooms).
                        baseline = Math.min(0.15, Math.max(0.03, baseline * 2.5));
                        lastSoundAt = Date.now();
                    }
                    if (rms > baseline) {
                        lastSoundAt = Date.now();
                    } else if (Date.now() - lastSoundAt > SILENCE_MS) {
                        stopRecordingRef.current?.();
                    }
                }, 50);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : t('creativeOs.agent.micDenied'));
        }
    }, [recording, transcribing]);

    const stopRecording = useCallback(() => {
        if (silenceTimerRef.current !== null) {
            clearInterval(silenceTimerRef.current);
            silenceTimerRef.current = null;
        }
        if (audioContextRef.current) {
            audioContextRef.current.close().catch(() => {});
            audioContextRef.current = null;
        }
        const r = mediaRecorderRef.current;
        if (r && r.state !== 'inactive') r.stop();
        mediaRecorderRef.current = null;
        setRecording(false);
        setAudioLevel(0);
    }, []);

    // Indirection so the silence watcher can call the latest stopRecording
    // without recreating the interval each time the callback identity changes.
    const stopRecordingRef = useRef<(() => void) | null>(null);
    useEffect(() => { stopRecordingRef.current = stopRecording; }, [stopRecording]);

    const handleStop = useCallback(() => {
        abortRef.current?.abort();
        // fire-and-forget backend interrupt as a fallback
        stopAgent(projectId).catch(() => {});
    }, [projectId]);

    const handleReset = useCallback(async () => {
        if (!confirm(t('creativeOs.agent.clearConfirm'))) return;
        try {
            await resetAgentThread(projectId);
            setTurns([]);
            setSessionId(null);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
        }
    }, [projectId]);

    // Expose imperative handle for parent-driven header controls
    useImperativeHandle(ref, () => ({
        useSeedance,
        toggleSeedance: () => { if (!running) setUseSeedance(v => !v); },
        running,
        turnsCount: turns.length,
        reset: handleReset,
    }), [useSeedance, running, turns.length, handleReset]);

    // Shared inner content: used by both embedded (full-height) and floating (modal) modes.
    const panelContent = (
        <div
            style={{
                display: 'flex',
                flexDirection: 'column',
                height: '100%',
                width: '100%',
                overflow: 'hidden',
            }}
        >
                    {/* Header */}
                    {!hideHeader && (
                    <div
                        style={{
                            padding: '14px 18px',
                            borderBottom: '1px solid rgba(13,27,62,0.06)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'space-between',
                            background: 'linear-gradient(135deg, rgba(51,122,255,0.06) 0%, rgba(91,143,255,0.03) 100%)',
                            flexShrink: 0,
                        }}
                    >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                            <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: '#337AFF', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                                <path d="M12 2 L13.5 8.5 L20 10 L13.5 11.5 L12 18 L10.5 11.5 L4 10 L10.5 8.5 Z" />
                            </svg>
                            <span style={{ fontSize: '14px', fontWeight: 700, color: '#0D1B3E' }}>{t('creativeOs.agent.creativeAgent')}</span>
                            <span style={{ fontSize: '10px', fontWeight: 600, color: '#337AFF', background: 'rgba(51,122,255,0.12)', padding: '2px 6px', borderRadius: '4px' }}>{t('creativeOs.agent.beta')}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <div
                                onClick={() => { if (!running) setUseSeedance((v) => !v); }}
                                title={useSeedance ? t('creativeOs.agent.seedanceOn') : t('creativeOs.agent.seedanceOff')}
                                style={{
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                    marginRight: '6px',
                                    padding: '0 6px',
                                    cursor: running ? 'not-allowed' : 'pointer',
                                    opacity: running ? 0.5 : 1,
                                    userSelect: 'none',
                                }}
                            >
                                <span style={{
                                    fontSize: '11px',
                                    fontWeight: 600,
                                    color: useSeedance ? '#337AFF' : '#5B6585',
                                    letterSpacing: '0.2px',
                                }}>
                                    Seedance 2.0
                                </span>
                                <div
                                    style={{
                                        width: '32px',
                                        height: '18px',
                                        borderRadius: '9px',
                                        position: 'relative',
                                        background: useSeedance
                                            ? 'linear-gradient(135deg, #5B7BFF, #337AFF)'
                                            : 'rgba(138,147,176,0.25)',
                                        transition: 'background 0.2s',
                                        flexShrink: 0,
                                    }}
                                >
                                    <div style={{
                                        width: '14px',
                                        height: '14px',
                                        borderRadius: '50%',
                                        background: 'white',
                                        position: 'absolute',
                                        top: '2px',
                                        left: useSeedance ? '16px' : '2px',
                                        transition: 'left 0.2s',
                                        boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
                                    }} />
                                </div>
                            </div>
                            <button
                                onClick={handleReset}
                                title={t('creativeOs.agent.clearChat')}
                                disabled={running || turns.length === 0}
                                style={{
                                    width: '28px',
                                    height: '28px',
                                    borderRadius: '6px',
                                    border: 'none',
                                    background: 'transparent',
                                    cursor: running || turns.length === 0 ? 'not-allowed' : 'pointer',
                                    color: '#8A93B0',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    opacity: running || turns.length === 0 ? 0.4 : 1,
                                }}
                            >
                                <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                                    <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6" />
                                </svg>
                            </button>
                            {embedded && onCollapse && (
                                <button
                                    onClick={onCollapse}
                                    title={t('creativeOs.agent.collapse')}
                                    style={{
                                        width: '28px',
                                        height: '28px',
                                        borderRadius: '6px',
                                        border: 'none',
                                        background: 'transparent',
                                        cursor: 'pointer',
                                        color: '#8A93B0',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                    }}
                                >
                                    <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                                        <polyline points="15 18 9 12 15 6" />
                                    </svg>
                                </button>
                            )}
                            {!embedded && (
                                <button
                                    onClick={() => setOpen(false)}
                                    title={t('creativeOs.agent.close')}
                                    style={{
                                        width: '28px',
                                        height: '28px',
                                        borderRadius: '6px',
                                        border: 'none',
                                        background: 'transparent',
                                        cursor: 'pointer',
                                        color: '#8A93B0',
                                        fontSize: '20px',
                                        lineHeight: 1,
                                    }}
                                >
                                    ×
                                </button>
                            )}
                        </div>
                    </div>
                    )}

                    {/* Messages */}
                    <div
                        ref={scrollerRef}
                        style={{
                            flex: 1,
                            padding: '16px 18px',
                            overflowY: 'auto',
                            display: 'flex',
                            flexDirection: 'column',
                            gap: '14px',
                            background: '#FAFBFD',
                        }}
                    >
                        {hydrating && (
                            <div style={{ fontSize: '12px', color: '#8A93B0', textAlign: 'center' }}>
                                {t('creativeOs.agent.loadingChat')}
                            </div>
                        )}
                        {!hydrating && turns.length === 0 && (
                            <div
                                style={{
                                    fontSize: '12px',
                                    color: '#8A93B0',
                                    textAlign: 'center',
                                    padding: '32px 12px',
                                    lineHeight: 1.6,
                                }}
                            >
                                {t('creativeOs.agent.emptyHint')}
                            </div>
                        )}

                        {(() => {
                            // Build a lookup map of all @tag → AgentRef across the conversation
                            const refMap = new Map<string, AgentRef>();
                            for (const t of turns) {
                                if (t.refs) {
                                    for (const r of t.refs) {
                                        refMap.set(r.tag, r);
                                    }
                                }
                            }
                            return turns.map((turn, idx) => {
                                // If this agent turn asked for aspect ratio ([[ASPECT_BUTTONS]]
                                // marker) and the next turn is the user's reply, detect which
                                // ratio they picked so the bubble can render it as "selected".
                                const next = turns[idx + 1];
                                const nextUserText = next?.role === 'user' ? (next.text || '') : '';
                                const selectedAspect: 'vertical' | 'horizontal' | null =
                                    /9\s*:\s*16|vertical/i.test(nextUserText) ? 'vertical'
                                        : /16\s*:\s*9|horizontal/i.test(nextUserText) ? 'horizontal'
                                            : null;
                                return (
                                    <TurnBubble
                                        key={idx}
                                        turn={turn}
                                        refMap={refMap}
                                        isLast={idx === turns.length - 1}
                                        running={running}
                                        onQuickReply={(text) => { handleRun(text); }}
                                        selectedAspect={selectedAspect}
                                    />
                                );
                            });
                        })()}

                        {running && activity && sawToolCall && (
                            <div
                                style={{
                                    fontSize: '11px',
                                    color: '#337AFF',
                                    fontWeight: 600,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '6px',
                                }}
                            >
                                {/* `key` flips on each keepalive → span remounts → pulse animation replays. */}
                                <span
                                    key={`pulse-${lastHeartbeatAt}`}
                                    style={{
                                        display: 'inline-block',
                                        width: '6px',
                                        height: '6px',
                                        borderRadius: '50%',
                                        background: '#337AFF',
                                        animation: 'pulse 1.2s ease-in-out infinite',
                                    }}
                                />
                                <span>{displayActivity}</span>
                                {activityStartedAt !== null && (
                                    <span style={{ opacity: 0.65, fontVariantNumeric: 'tabular-nums' }}>
                                        · {formatElapsed(elapsedSec)}
                                    </span>
                                )}
                                {artifactsReadyCount > 0 && (
                                    <span
                                        key={`ready-${artifactFlashTick}`}
                                        style={{
                                            color: '#2BA04A',
                                            animation: 'artifactFlash 0.5s ease-out',
                                        }}
                                    >
                                        · {artifactsReadyCount} ready
                                    </span>
                                )}
                            </div>
                        )}

                        {error && (
                            <div
                                style={{
                                    padding: '10px 12px',
                                    background: 'rgba(255,82,82,0.08)',
                                    border: '1px solid rgba(255,82,82,0.2)',
                                    borderRadius: '8px',
                                    fontSize: '12px',
                                    color: '#C53030',
                                }}
                            >
                                {error}
                            </div>
                        )}
                    </div>

                    {/* Composer */}
                    <div
                        style={{
                            padding: '12px 14px',
                            borderTop: '1px solid rgba(13,27,62,0.06)',
                            background: 'white',
                            flexShrink: 0,
                            position: 'relative',
                        }}
                    >
                        {mentionOpen && (filteredMentions.length > 0 || shotPickerItem) && (
                            <MentionDropdown
                                groups={groupedMentions}
                                ordered={orderedMentions}
                                activeIndex={mentionIndex}
                                onPick={insertMention}
                                onHover={setMentionIndex}
                                shotPickerItem={shotPickerItem}
                                onPickShot={(imageUrl) => shotPickerItem && finalizeMention(shotPickerItem, imageUrl)}
                                onBackFromShotPicker={() => setShotPickerItem(null)}
                            />
                        )}
                        {attachments.length > 0 && (
                            <div
                                style={{
                                    display: 'flex',
                                    flexWrap: 'wrap',
                                    gap: '6px',
                                    marginBottom: '8px',
                                }}
                            >
                                {attachments.map((att) => (
                                    <AttachmentChip
                                        key={att.id}
                                        att={att}
                                        onRemove={() => removeAttachment(att.id)}
                                    />
                                ))}
                            </div>
                        )}
                        <input
                            ref={fileInputRef}
                            type="file"
                            accept="image/*,video/*"
                            multiple
                            style={{ display: 'none' }}
                            onChange={(e) => {
                                handleFilesPicked(e.target.files);
                                // Reset so picking the same file again still triggers onChange.
                                e.target.value = '';
                            }}
                        />
                        <div style={{ position: 'relative' }}>
                            <textarea
                                ref={textareaRef}
                                value={brief}
                                onChange={handleBriefChange}
                                onKeyDown={handleBriefKeyDown}
                                onFocus={() => { if (!mentionsLoaded) loadMentionData(); }}
                                placeholder={t('creativeOs.agent.composerPlaceholder')}
                                disabled={running}
                                rows={3}
                                style={{
                                    width: '100%',
                                    paddingTop: '10px',
                                    paddingBottom: '44px',
                                    paddingLeft: '12px',
                                    paddingRight: '84px',
                                    border: '1px solid rgba(13,27,62,0.12)',
                                    borderRadius: '12px',
                                    fontSize: '13px',
                                    fontFamily: 'inherit',
                                    color: '#0D1B3E',
                                    resize: 'none',
                                    outline: 'none',
                                    background: running ? 'rgba(13,27,62,0.03)' : 'white',
                                    display: 'block',
                                }}
                            />
                            <button
                                onClick={() => {
                                    setHistoryOpen(false);
                                    setMenuOpen((v) => !v);
                                }}
                                disabled={running}
                                title={t('creativeOs.agent.addAttachmentMenu')}
                                style={{
                                    position: 'absolute',
                                    left: '8px',
                                    bottom: '8px',
                                    width: '30px',
                                    height: '30px',
                                    borderRadius: '8px',
                                    border: '1px solid rgba(13,27,62,0.12)',
                                    background: running ? 'rgba(13,27,62,0.03)' : 'white',
                                    cursor: running ? 'not-allowed' : 'pointer',
                                    color: '#337AFF',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    padding: 0,
                                }}
                            >
                                <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: 'currentColor', strokeWidth: '2.2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                                    <line x1="12" y1="5" x2="12" y2="19" />
                                    <line x1="5" y1="12" x2="19" y2="12" />
                                </svg>
                            </button>
                            {!running && (
                                <button
                                    onClick={recording ? stopRecording : startRecording}
                                    disabled={transcribing}
                                    title={recording ? t('creativeOs.agent.stopRecording') : transcribing ? t('creativeOs.agent.transcribing') : t('creativeOs.agent.dictate')}
                                    style={{
                                        position: 'absolute',
                                        right: '46px',
                                        bottom: '8px',
                                        width: '30px',
                                        height: '30px',
                                        borderRadius: '50%',
                                        border: '1px solid rgba(13,27,62,0.12)',
                                        cursor: transcribing ? 'wait' : 'pointer',
                                        background: recording ? 'rgba(255,82,82,0.12)' : 'white',
                                        color: recording ? '#C53030' : transcribing ? '#8A93B0' : '#0D1B3E',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        padding: 0,
                                    }}
                                >
                                    {transcribing ? (
                                        <span style={{ display: 'flex', gap: '2px' }}>
                                            <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'currentColor', animation: 'pulse 1s ease-in-out infinite' }} />
                                            <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'currentColor', animation: 'pulse 1s ease-in-out 0.15s infinite' }} />
                                            <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'currentColor', animation: 'pulse 1s ease-in-out 0.3s infinite' }} />
                                        </span>
                                    ) : recording ? (
                                        <WaveformBars level={audioLevel} />
                                    ) : (
                                        <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                                            <rect x="9" y="3" width="6" height="12" rx="3" />
                                            <path d="M5 11a7 7 0 0 0 14 0" />
                                            <line x1="12" y1="18" x2="12" y2="22" />
                                        </svg>
                                    )}
                                </button>
                            )}
                            {running ? (
                                <button
                                    onClick={handleStop}
                                    title={t('creativeOs.agent.stop')}
                                    style={{
                                        position: 'absolute',
                                        right: '8px',
                                        bottom: '8px',
                                        height: '30px',
                                        padding: '0 12px',
                                        borderRadius: '8px',
                                        border: '1px solid rgba(255,82,82,0.3)',
                                        cursor: 'pointer',
                                        background: 'rgba(255,82,82,0.08)',
                                        color: '#C53030',
                                        fontSize: '12px',
                                        fontWeight: 600,
                                    }}
                                >
                                    {t('creativeOs.agent.stop')}
                                </button>
                            ) : (() => {
                                const hasReadyAttachments = attachments.some((a) => a.status === 'ready');
                                const uploading = attachments.some((a) => a.status === 'uploading');
                                const canSend = (brief.trim() !== '' || hasReadyAttachments) && !uploading;
                                return (
                                    <button
                                        onClick={() => handleRun()}
                                        disabled={!canSend}
                                        title={uploading ? t('creativeOs.agent.uploading') : t('creativeOs.agent.send')}
                                        style={{
                                            position: 'absolute',
                                            right: '8px',
                                            bottom: '8px',
                                            width: '30px',
                                            height: '30px',
                                            borderRadius: '50%',
                                            border: 'none',
                                            cursor: canSend ? 'pointer' : 'not-allowed',
                                            background: canSend
                                                ? 'linear-gradient(135deg, #337AFF 0%, #5B8FFF 100%)'
                                                : 'rgba(13,27,62,0.18)',
                                            color: 'white',
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                            padding: 0,
                                            transition: 'background 0.15s ease',
                                        }}
                                    >
                                        <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2.4', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                                            <line x1="12" y1="19" x2="12" y2="5" />
                                            <polyline points="5 12 12 5 19 12" />
                                        </svg>
                                    </button>
                                );
                            })()}
                            {menuOpen && (
                                <ComposerMenu
                                    onAttach={() => {
                                        setMenuOpen(false);
                                        fileInputRef.current?.click();
                                    }}
                                    onReference={() => {
                                        setMenuOpen(false);
                                        openReferenceDropdown();
                                    }}
                                    onHistory={() => {
                                        setMenuOpen(false);
                                        setHistoryOpen(true);
                                    }}
                                    onClose={() => setMenuOpen(false)}
                                />
                            )}
                            {historyOpen && (
                                <HistoryPopover
                                    items={orderedMentions.filter((m) => m.type === 'image' || m.type === 'video')}
                                    onPick={(m) => {
                                        insertMention(m);
                                        setHistoryOpen(false);
                                    }}
                                    onClose={() => setHistoryOpen(false)}
                                />
                            )}
                        </div>
                    </div>
        </div>
    );

    // Keyframes shared across both render modes.
    const keyframes = (
        <style jsx>{`
            @keyframes pulse {
                0%, 100% { opacity: 0.4; transform: scale(0.85); }
                50% { opacity: 1; transform: scale(1.15); }
            }
            @keyframes artifactFlash {
                0% { transform: scale(1.25); opacity: 0.4; }
                50% { transform: scale(1); opacity: 1; }
                100% { transform: scale(1); opacity: 1; }
            }
            @keyframes thinkingDot {
                0%, 80%, 100% { opacity: 0.2; transform: translateY(0); }
                40% { opacity: 1; transform: translateY(-2px); }
            }
        `}</style>
    );

    // Embedded mode: render panel content directly (parent controls dimensions).
    if (embedded) {
        return (
            <>
                {panelContent}
                {keyframes}
            </>
        );
    }

    // Floating mode: preserve the existing FAB + fixed-position modal overlay.
    return (
        <>
            {!open && (
                <button
                    onClick={() => setOpen(true)}
                    title={t('creativeOs.agent.runAgent')}
                    style={{
                        position: 'fixed',
                        right: '24px',
                        bottom: '120px',
                        zIndex: 950,
                        padding: '12px 18px',
                        borderRadius: '999px',
                        border: 'none',
                        cursor: 'pointer',
                        background: 'linear-gradient(135deg, #337AFF 0%, #5B8FFF 100%)',
                        color: 'white',
                        fontSize: '13px',
                        fontWeight: 600,
                        boxShadow: '0 6px 24px rgba(51,122,255,0.35)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                    }}
                >
                    <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                        <path d="M12 2 L13.5 8.5 L20 10 L13.5 11.5 L12 18 L10.5 11.5 L4 10 L10.5 8.5 Z" />
                    </svg>
                    {t('creativeOs.agent.agentButton')}
                </button>
            )}

            {open && (
                <div
                    style={{
                        position: 'fixed',
                        right: '24px',
                        bottom: '24px',
                        zIndex: 950,
                        width: 'min(94vw, 480px)',
                        height: 'min(calc(100vh - 80px), 720px)',
                        maxHeight: 'min(calc(100vh - 80px), 720px)',
                        background: 'white',
                        borderRadius: '16px',
                        boxShadow: '0 20px 60px rgba(13,27,62,0.18)',
                        border: '1px solid rgba(51,122,255,0.12)',
                        display: 'flex',
                        flexDirection: 'column',
                        overflow: 'hidden',
                    }}
                >
                    {panelContent}
                </div>
            )}
            {keyframes}
        </>
    );
});

/**
 * Render message text with inline markdown (**bold**) and @asset preview chips.
 * @tags are replaced with miniature thumbnail + label chips.
 */
function renderMessageContent(
    text: string,
    refMap: Map<string, AgentRef>,
    isUser: boolean,
): React.ReactNode[] {
    // Pre-pass: strip raw asset URLs that the model occasionally leaks into
    // its reply. The chat panel renders thumbnails from `turn.artifacts`
    // automatically, so the URLs are pure noise (and they overflow the bubble).
    if (!isUser) {
        const ASSET_RE = /supabase\.co|\.mp4|\.mov|\.webm|\.png|\.jpg|\.jpeg|\.webp/i;
        // Markdown links: drop entirely if asset, keep label only if non-asset.
        text = text.replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g, (_, label, url) =>
            ASSET_RE.test(url) ? '' : label,
        );
        // Bare asset URLs.
        text = text.replace(
            /https?:\/\/\S*?(supabase\.co|\.mp4|\.mov|\.webm|\.png|\.jpg|\.jpeg|\.webp)\S*/gi,
            '',
        );
        // Tidy gaps left behind by stripped links.
        text = text.replace(/\s{2,}/g, ' ').replace(/\s+([.,!?;:])/g, '$1').trim();
    }

    const parts: React.ReactNode[] = [];
    // Match **bold**, *italic*, @tag_name patterns.
    // Bold must be tested first so `**foo**` is not mistaken for two italic runs.
    const regex = /(\*\*([^*]+?)\*\*)|(\*([^*\s][^*]*?)\*)|(@([a-z0-9_]+))/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    let key = 0;

    while ((match = regex.exec(text)) !== null) {
        // Add text before this match
        if (match.index > lastIndex) {
            parts.push(text.slice(lastIndex, match.index));
        }

        if (match[1]) {
            // **bold** match
            parts.push(<strong key={`b${key++}`}>{match[2]}</strong>);
        } else if (match[3]) {
            // *italic* match
            parts.push(<em key={`i${key++}`}>{match[4]}</em>);
        } else if (match[5]) {
            // @tag match
            const tag = match[6];
            const ref = refMap.get(tag);
            if (ref && (ref.image_url || ref.video_url)) {
                // Render as asset chip with thumbnail
                parts.push(
                    <span
                        key={`ref${key++}`}
                        style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                            padding: '2px 6px 2px 2px',
                            borderRadius: '6px',
                            background: isUser
                                ? 'rgba(255,255,255,0.2)'
                                : 'rgba(51,122,255,0.08)',
                            border: isUser
                                ? '1px solid rgba(255,255,255,0.3)'
                                : '1px solid rgba(51,122,255,0.15)',
                            verticalAlign: 'middle',
                            margin: '0 1px',
                        }}
                    >
                        {ref.image_url ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                                src={ref.image_url}
                                alt={ref.name || tag}
                                style={{
                                    width: '20px',
                                    height: '20px',
                                    borderRadius: '4px',
                                    objectFit: 'cover',
                                    flexShrink: 0,
                                }}
                            />
                        ) : ref.video_url ? (
                            <video
                                src={ref.video_url}
                                muted
                                playsInline
                                preload="metadata"
                                style={{
                                    width: '20px',
                                    height: '20px',
                                    borderRadius: '4px',
                                    objectFit: 'cover',
                                    flexShrink: 0,
                                }}
                            />
                        ) : null}
                        <span
                            style={{
                                fontSize: '11px',
                                fontWeight: 600,
                                color: isUser ? 'white' : '#337AFF',
                                maxWidth: '100px',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                whiteSpace: 'nowrap',
                            }}
                        >
                            {ref.name || tag}
                        </span>
                    </span>
                );
            } else {
                // No image found for this tag — render as styled text
                parts.push(
                    <span
                        key={`tag${key++}`}
                        style={{
                            fontSize: '12px',
                            fontWeight: 600,
                            color: isUser ? 'rgba(255,255,255,0.85)' : '#337AFF',
                        }}
                    >
                        @{tag}
                    </span>
                );
            }
        }

        lastIndex = regex.lastIndex;
    }

    if (lastIndex < text.length) {
        parts.push(text.slice(lastIndex));
    }
    return parts;
}

/** Live waveform visualizer for the mic button.
 *  Five vertical bars whose heights track `level` (0-1) with a slight
 *  per-bar offset so the animation feels natural rather than rigid. */
function WaveformBars({ level }: { level: number }) {
    const offsets = [0.55, 0.85, 1.0, 0.85, 0.55];
    return (
        <span style={{ display: 'flex', alignItems: 'center', gap: '2px', height: '14px' }}>
            {offsets.map((o, i) => {
                const h = Math.max(2, Math.min(14, level * 14 * o + 2));
                return (
                    <span
                        key={i}
                        style={{
                            width: '2px',
                            height: `${h}px`,
                            borderRadius: '1px',
                            background: 'currentColor',
                            transition: 'height 60ms linear',
                        }}
                    />
                );
            })}
        </span>
    );
}

function ComposerMenu({
    onAttach,
    onReference,
    onHistory,
    onClose,
}: {
    onAttach: () => void;
    onReference: () => void;
    onHistory: () => void;
    onClose: () => void;
}) {
    const { t } = useTranslation();
    const rootRef = useRef<HTMLDivElement | null>(null);
    useEffect(() => {
        const onDocMouseDown = (e: MouseEvent) => {
            if (!rootRef.current) return;
            if (!rootRef.current.contains(e.target as Node)) onClose();
        };
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('mousedown', onDocMouseDown);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onDocMouseDown);
            document.removeEventListener('keydown', onKey);
        };
    }, [onClose]);

    const item = (label: string, icon: React.ReactNode, onClick: () => void) => (
        <button
            onClick={onClick}
            style={{
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                width: '100%',
                padding: '9px 12px',
                border: 'none',
                background: 'transparent',
                cursor: 'pointer',
                fontSize: '13px',
                color: '#0D1B3E',
                textAlign: 'left',
                borderRadius: '8px',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(51,122,255,0.08)')}
            onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
        >
            <span style={{ color: '#337AFF', display: 'flex' }}>{icon}</span>
            {label}
        </button>
    );

    return (
        <div
            ref={rootRef}
            style={{
                position: 'absolute',
                left: '4px',
                bottom: '46px',
                width: '180px',
                background: 'white',
                border: '1px solid rgba(13,27,62,0.1)',
                borderRadius: '10px',
                boxShadow: '0 8px 24px rgba(13,27,62,0.12)',
                padding: '4px',
                zIndex: 20,
            }}
        >
            {item(
                t('creativeOs.agent.menuAttach'),
                <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                </svg>,
                onAttach,
            )}
            {item(
                t('creativeOs.agent.menuReference'),
                <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                    <circle cx="12" cy="12" r="4" />
                    <path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-3.92 7.94" />
                </svg>,
                onReference,
            )}
            {item(
                t('creativeOs.agent.menuHistory'),
                <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
                    <polyline points="3 3 3 8 8 8" />
                    <polyline points="12 7 12 12 15 14" />
                </svg>,
                onHistory,
            )}
        </div>
    );
}

function HistoryPopover({
    items,
    onPick,
    onClose,
}: {
    items: MentionItem[];
    onPick: (m: MentionItem) => void;
    onClose: () => void;
}) {
    const { t } = useTranslation();
    const rootRef = useRef<HTMLDivElement | null>(null);
    useEffect(() => {
        const onDocMouseDown = (e: MouseEvent) => {
            if (!rootRef.current) return;
            if (!rootRef.current.contains(e.target as Node)) onClose();
        };
        const onKey = (e: KeyboardEvent) => {
            if (e.key === 'Escape') onClose();
        };
        document.addEventListener('mousedown', onDocMouseDown);
        document.addEventListener('keydown', onKey);
        return () => {
            document.removeEventListener('mousedown', onDocMouseDown);
            document.removeEventListener('keydown', onKey);
        };
    }, [onClose]);

    return (
        <div
            ref={rootRef}
            style={{
                position: 'absolute',
                left: '4px',
                bottom: '46px',
                width: '280px',
                maxHeight: '320px',
                overflowY: 'auto',
                background: 'white',
                border: '1px solid rgba(13,27,62,0.1)',
                borderRadius: '10px',
                boxShadow: '0 8px 24px rgba(13,27,62,0.12)',
                padding: '4px',
                zIndex: 20,
            }}
        >
            {items.length === 0 ? (
                <div style={{ padding: '16px 12px', fontSize: '12px', color: '#8A93B0', textAlign: 'center' }}>
                    {t('creativeOs.agent.noHistory')}
                </div>
            ) : (
                items.map((m) => (
                    <button
                        key={`${m.type}:${m.tag}`}
                        onClick={() => onPick(m)}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '10px',
                            width: '100%',
                            padding: '6px 8px',
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            textAlign: 'left',
                            borderRadius: '8px',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.background = 'rgba(51,122,255,0.08)')}
                        onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                    >
                        <div
                            style={{
                                width: '32px',
                                height: '32px',
                                borderRadius: '6px',
                                background: 'rgba(13,27,62,0.06)',
                                overflow: 'hidden',
                                flexShrink: 0,
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                            }}
                        >
                            {m.image_url ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img src={m.image_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                            ) : (
                                <span style={{ fontSize: '10px', color: '#8A93B0' }}>{m.type}</span>
                            )}
                        </div>
                        <div style={{ flex: 1, minWidth: 0 }}>
                            <div
                                style={{
                                    fontSize: '12px',
                                    color: '#0D1B3E',
                                    fontWeight: 500,
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                    whiteSpace: 'nowrap',
                                }}
                            >
                                {m.name}
                            </div>
                            <div style={{ fontSize: '10px', color: '#8A93B0', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                                {m.type}
                            </div>
                        </div>
                    </button>
                ))
            )}
        </div>
    );
}

// Progressive text reveal — the Managed Agents API hands us whole messages
// (no token deltas), so we animate the reveal client-side at ~60 chars/s to
// give the bubble a "streaming" feel. When `text` grows (the agent emits a
// longer version of the same message), the reveal continues from wherever the
// previous animation left off instead of snapping back to the start.
function AnimatedText({ text, refMap, speedCharsPerSec = 60 }: { text: string; refMap: Map<string, AgentRef>; speedCharsPerSec?: number }) {
    const [revealed, setRevealed] = useState(0);
    const textRef = useRef<string>(text);
    useEffect(() => {
        textRef.current = text;
        let cancelled = false;
        const startedAt = performance.now();
        const startFrom = Math.min(revealed, text.length);
        const tick = () => {
            if (cancelled) return;
            const current = textRef.current;
            const elapsedSecs = (performance.now() - startedAt) / 1000;
            const target = Math.min(current.length, startFrom + Math.floor(elapsedSecs * speedCharsPerSec));
            setRevealed(target);
            if (target < current.length) requestAnimationFrame(tick);
        };
        requestAnimationFrame(tick);
        return () => { cancelled = true; };
        // Intentionally depend only on `text` — we don't want `revealed` updates
        // to restart the animation every frame.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [text, speedCharsPerSec]);
    const shown = text.slice(0, revealed);
    return <>{renderMessageContent(shown, refMap, false)}</>;
}

function TurnBubble({ turn, refMap, isLast, running, onQuickReply, selectedAspect }: { turn: AgentTurn; refMap: Map<string, AgentRef>; isLast?: boolean; running?: boolean; onQuickReply?: (text: string) => void; selectedAspect?: 'vertical' | 'horizontal' | null }) {
    const { t } = useTranslation();
    const isUser = turn.role === 'user';
    const hasRefPreviews = isUser && !!turn.refs?.some((r) => r.image_url || r.video_url);
    // Detect the `[[ASPECT_BUTTONS]]` marker emitted by the agent when asking
    // for aspect ratio. ALWAYS strip it from display — the marker is an
    // internal signal, never user-facing. Render the two quick-reply buttons
    // alongside the question; on the active turn they are clickable, on
    // historical turns they reflect the user's selection (filled vs. muted).
    const rawText = turn.text || '';
    const hasAspectMarker = !isUser && rawText.includes('[[ASPECT_BUTTONS]]');
    const displayText = hasAspectMarker
        ? rawText.replace(/\s*\[\[ASPECT_BUTTONS\]\]\s*/g, '').trim()
        : rawText;
    const aspectButtonsActive = hasAspectMarker && !!isLast && !!onQuickReply && !selectedAspect;
    const hasContent = !!displayText || !!turn.artifacts?.length || turn.interrupted || hasRefPreviews || hasAspectMarker;
    // While a run is active, show a placeholder "…" bubble (three breathing
    // dots) in place of the empty agent turn so the UI never looks frozen
    // while waiting for the first `agent_message`. Historical empty turns
    // (e.g. mid-run refresh from Supabase) still render nothing.
    const showThinkingDots = !isUser && !hasContent && !!isLast && !!running;
    if (!isUser && !hasContent && !showThinkingDots) return null;
    return (
        <div
            style={{
                display: 'flex',
                justifyContent: isUser ? 'flex-end' : 'flex-start',
            }}
        >
            <div
                style={{
                    maxWidth: '85%',
                    minWidth: 0,
                    wordBreak: 'break-word',
                    overflowWrap: 'anywhere',
                    padding: '10px 13px',
                    borderRadius: isUser ? '14px 14px 4px 14px' : '14px 14px 14px 4px',
                    background: isUser
                        ? 'linear-gradient(135deg, #337AFF 0%, #5B8FFF 100%)'
                        : 'white',
                    color: isUser ? 'white' : '#0D1B3E',
                    fontSize: '13px',
                    lineHeight: 1.5,
                    border: isUser ? 'none' : '1px solid rgba(13,27,62,0.08)',
                    boxShadow: isUser ? 'none' : '0 1px 3px rgba(13,27,62,0.04)',
                }}
            >
                {isUser && turn.refs && turn.refs.some((r) => r.image_url || r.video_url) && (
                    <div
                        style={{
                            display: 'flex',
                            flexWrap: 'wrap',
                            gap: '4px',
                            marginBottom: turn.text ? '8px' : 0,
                        }}
                    >
                        {turn.refs
                            .filter((r) => r.image_url || r.video_url)
                            .map((r, i) => (
                                <a
                                    key={`${r.tag}-${i}`}
                                    href={r.image_url || r.video_url}
                                    target="_blank"
                                    rel="noreferrer"
                                    title={r.name || r.tag}
                                    style={{
                                        display: 'block',
                                        width: '56px',
                                        height: '56px',
                                        borderRadius: '8px',
                                        overflow: 'hidden',
                                        background: 'rgba(255,255,255,0.18)',
                                        border: '1px solid rgba(255,255,255,0.3)',
                                        flexShrink: 0,
                                    }}
                                >
                                    {r.video_url && !r.image_url ? (
                                        <video src={r.video_url} muted playsInline style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    ) : (
                                        // eslint-disable-next-line @next/next/no-img-element
                                        <img src={r.image_url || r.video_url} alt={r.name || ''} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    )}
                                </a>
                            ))}
                    </div>
                )}

                {showThinkingDots && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '2px 0' }}>
                        {[0, 1, 2].map((i) => (
                            <span
                                key={i}
                                style={{
                                    display: 'inline-block',
                                    width: '6px',
                                    height: '6px',
                                    borderRadius: '50%',
                                    background: '#8A93B0',
                                    animation: `thinkingDot 1.2s ease-in-out ${i * 0.15}s infinite`,
                                }}
                            />
                        ))}
                    </div>
                )}

                {displayText && (
                    <div style={{ whiteSpace: 'pre-wrap' }}>
                        {/* Progressive reveal only for the agent's active last bubble — gives
                            a streaming feel even though Managed Agents delivers whole messages. */}
                        {!isUser && !!isLast && !!running
                            ? <AnimatedText text={displayText} refMap={refMap} />
                            : renderMessageContent(displayText, refMap, isUser)}
                    </div>
                )}

                {hasAspectMarker && (
                    <div style={{ display: 'flex', gap: '8px', marginTop: displayText ? '10px' : 0, flexWrap: 'wrap' }}>
                        {(['vertical', 'horizontal'] as const).map((kind) => {
                            const label = kind === 'vertical'
                                ? t('creativeOs.agent.aspectVertical')
                                : t('creativeOs.agent.aspectHorizontal');
                            const isSelected = selectedAspect === kind;
                            const muted = !!selectedAspect && !isSelected;
                            return (
                                <button
                                    key={kind}
                                    type="button"
                                    disabled={!aspectButtonsActive}
                                    onClick={() => aspectButtonsActive && onQuickReply?.(label)}
                                    style={{
                                        padding: '6px 14px',
                                        borderRadius: '8px',
                                        border: isSelected
                                            ? '1px solid #337AFF'
                                            : '1px solid rgba(51,122,255,0.15)',
                                        background: isSelected
                                            ? 'linear-gradient(135deg, #337AFF 0%, #5B8FFF 100%)'
                                            : muted
                                                ? 'rgba(51,122,255,0.03)'
                                                : 'white',
                                        color: isSelected ? 'white' : muted ? '#8A93B0' : '#337AFF',
                                        fontSize: '13px',
                                        fontWeight: 500,
                                        cursor: aspectButtonsActive ? 'pointer' : 'default',
                                    }}
                                >
                                    {label}
                                </button>
                            );
                        })}
                    </div>
                )}

                {(() => {
                    const mediaArts = (turn.artifacts || []).filter(a => a.type === 'video' || a.type === 'image');
                    const styleArts = (turn.artifacts || []).filter(a => a.type === 'caption_styles_preview');
                    return (
                        <>
                            {mediaArts.length > 0 && (
                                <div
                                    style={{
                                        marginTop: turn.text ? '10px' : 0,
                                        display: 'grid',
                                        gridTemplateColumns: mediaArts.length === 1 ? '1fr' : '1fr 1fr',
                                        gap: '6px',
                                    }}
                                >
                                    {mediaArts.map((a, i) => (
                                        <a
                                            key={i}
                                            href={a.url}
                                            target="_blank"
                                            rel="noreferrer"
                                            style={{
                                                display: 'block',
                                                aspectRatio: '9 / 16',
                                                borderRadius: '8px',
                                                overflow: 'hidden',
                                                background: '#F4F6FA',
                                                border: '1px solid rgba(13,27,62,0.08)',
                                            }}
                                        >
                                            {a.type === 'video' ? (
                                                <video src={a.url} muted loop autoPlay playsInline style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                            ) : (
                                                // eslint-disable-next-line @next/next/no-img-element
                                                <img src={a.url} alt="artifact" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                            )}
                                        </a>
                                    ))}
                                </div>
                            )}
                            {styleArts.map((a, i) => (
                                <CaptionStylesPreviewCard key={`cs-${i}`} styles={a.styles || []} />
                            ))}
                        </>
                    );
                })()}

                {turn.interrupted && (
                    <div
                        style={{
                            marginTop: '6px',
                            fontSize: '11px',
                            color: isUser ? 'rgba(255,255,255,0.75)' : '#C53030',
                            fontStyle: 'italic',
                        }}
                    >
                        {t('creativeOs.agent.stopped')}
                    </div>
                )}
            </div>
        </div>
    );
}

function CaptionStylesPreviewCard({ styles }: { styles: CaptionStylePreview[] }) {
    if (!styles || styles.length === 0) return null;
    return (
        <div
            style={{
                marginTop: '10px',
                display: 'grid',
                gridTemplateColumns: 'repeat(2, 1fr)',
                gap: '8px',
            }}
        >
            {styles.map((s) => (
                <CaptionStylePreviewCard key={s.id} style={s} size="sm" />
            ))}
        </div>
    );
}

function AttachmentChip({ att, onRemove }: { att: AttachedFile; onRemove: () => void }) {
    const { t } = useTranslation();
    const thumb = att.previewUrl || att.url;
    const isVideo = att.type === 'video';
    return (
        <div
            style={{
                position: 'relative',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '4px 10px 4px 4px',
                borderRadius: '8px',
                background: att.status === 'error'
                    ? 'rgba(255,82,82,0.08)'
                    : 'rgba(51,122,255,0.06)',
                border: att.status === 'error'
                    ? '1px solid rgba(255,82,82,0.25)'
                    : '1px solid rgba(51,122,255,0.18)',
                maxWidth: '180px',
            }}
        >
            <div
                style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '6px',
                    overflow: 'hidden',
                    background: '#F4F6FA',
                    flexShrink: 0,
                    position: 'relative',
                }}
            >
                {thumb ? (
                    isVideo ? (
                        <video
                            src={thumb}
                            muted
                            playsInline
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                    ) : (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                            src={thumb}
                            alt={att.name}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                        />
                    )
                ) : null}
                {att.status === 'uploading' && (
                    <div
                        style={{
                            position: 'absolute',
                            inset: 0,
                            background: 'rgba(13,27,62,0.55)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: 'white',
                            fontSize: '9px',
                            fontWeight: 600,
                        }}
                    >
                        …
                    </div>
                )}
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
                <span
                    style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        color: '#0D1B3E',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        maxWidth: '110px',
                    }}
                    title={att.name}
                >
                    {att.name}
                </span>
                <span
                    style={{
                        fontSize: '9px',
                        color: att.status === 'error' ? '#C53030' : '#8A93B0',
                        textTransform: 'uppercase',
                        letterSpacing: '0.4px',
                        fontWeight: 600,
                    }}
                >
                    {att.status === 'uploading'
                        ? t('creativeOs.agent.uploadingChip')
                        : att.status === 'error'
                            ? t('creativeOs.agent.failedChip')
                            : att.type}
                </span>
            </div>
            <button
                type="button"
                onClick={onRemove}
                title={t('creativeOs.agent.remove')}
                style={{
                    width: '18px',
                    height: '18px',
                    borderRadius: '50%',
                    border: 'none',
                    background: 'rgba(13,27,62,0.12)',
                    color: 'white',
                    cursor: 'pointer',
                    fontSize: '12px',
                    lineHeight: 1,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    marginLeft: '2px',
                }}
            >
                ×
            </button>
        </div>
    );
}

interface MentionDropdownProps {
    groups: Record<'product' | 'influencer' | 'image' | 'video', MentionItem[]>;
    ordered: MentionItem[];
    activeIndex: number;
    onPick: (item: MentionItem) => void;
    onHover: (idx: number) => void;
    shotPickerItem?: MentionItem | null;
    onPickShot?: (imageUrl: string) => void;
    onBackFromShotPicker?: () => void;
}

function MentionDropdown({ groups, ordered, activeIndex, onPick, onHover, shotPickerItem, onPickShot, onBackFromShotPicker }: MentionDropdownProps) {
    const { t } = useTranslation();
    const GROUP_LABELS_T: Record<MentionItem['type'], string> = {
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
        maxHeight: '320px',
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
            {groupOrder.map((g) => {
                const items = groups[g];
                if (!items || items.length === 0) return null;
                return (
                    <div key={g} style={{ marginBottom: '6px' }}>
                        <div
                            style={{
                                fontSize: '10px',
                                fontWeight: 700,
                                color: '#8A93B0',
                                textTransform: 'uppercase',
                                letterSpacing: '0.5px',
                                padding: '4px 6px',
                            }}
                        >
                            {GROUP_LABELS_T[g]}
                        </div>
                        <div
                            style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(4, 1fr)',
                                gap: '6px',
                            }}
                        >
                            {items.map((item) => {
                                const idx = ordered.indexOf(item);
                                const active = idx === activeIndex;
                                return (
                                    <button
                                        key={`${item.type}-${item.tag}`}
                                        type="button"
                                        onMouseDown={(e) => {
                                            e.preventDefault();
                                            onPick(item);
                                        }}
                                        onMouseEnter={() => onHover(idx)}
                                        title={item.name}
                                        style={{
                                            display: 'flex',
                                            flexDirection: 'column',
                                            alignItems: 'center',
                                            gap: '4px',
                                            padding: '6px 4px',
                                            border: active
                                                ? '1px solid rgba(51,122,255,0.5)'
                                                : '1px solid transparent',
                                            background: active
                                                ? 'rgba(51,122,255,0.08)'
                                                : 'transparent',
                                            borderRadius: '8px',
                                            cursor: 'pointer',
                                            minWidth: 0,
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
                );
            })}
        </div>
    );
}
