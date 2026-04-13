'use client';

import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import {
    creativeFetch,
    getAgentThread,
    resetAgentThread,
    stopAgent,
    streamAgent,
    uploadAgentFile,
    type AgentTurn,
    type AgentArtifact,
    type AgentRef,
    type AgentStreamEvent,
} from '@/lib/creative-os-api';
import { supabase } from '@/lib/supabaseClient';

interface AgentPanelProps {
    projectId: string;
    onArtifact?: () => void;
}

interface MentionItem {
    type: AgentRef['type'];
    tag: string;          // unique @-token
    name: string;         // display label
    image_url?: string;   // thumbnail
    ref: AgentRef;        // payload sent to backend
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

export function AgentPanel({ projectId, onArtifact }: AgentPanelProps) {
    const [open, setOpen] = useState(false);
    const [brief, setBrief] = useState('');
    const [turns, setTurns] = useState<AgentTurn[]>([]);
    const [, setSessionId] = useState<string | null>(null);
    const [running, setRunning] = useState(false);
    const [activity, setActivity] = useState<string>('');
    const [error, setError] = useState<string | null>(null);
    const [hydrating, setHydrating] = useState(false);
    const abortRef = useRef<AbortController | null>(null);
    const scrollerRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // ── File attachments ────────────────────────────────────────────────
    const [attachments, setAttachments] = useState<AttachedFile[]>([]);

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
                setError(`Unsupported file type: ${ct || 'unknown'}`);
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
            items.push({
                type: 'product',
                tag: slugify(name),
                name,
                image_url: p.image_url,
                ref: { type: 'product', tag: slugify(name), name, id: p.id, image_url: p.image_url },
            });
        }
        for (const inf of influencers) {
            const name = inf.name || 'model';
            items.push({
                type: 'influencer',
                tag: slugify(name),
                name,
                image_url: inf.image_url,
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
        if (!open || !projectId) return;
        let cancelled = false;
        setHydrating(true);
        getAgentThread(projectId)
            .then((thread) => {
                if (cancelled) return;
                setTurns(thread.turns || []);
                setSessionId(thread.session_id);
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
    }, [open, projectId]);

    // Auto-scroll on new content
    useEffect(() => {
        const el = scrollerRef.current;
        if (el) el.scrollTop = el.scrollHeight;
    }, [turns, activity, hydrating]);

    const handleRun = useCallback(async () => {
        const text = brief.trim();
        const readyAttachments = attachments.filter((a) => a.status === 'ready' && a.url);
        const stillUploading = attachments.some((a) => a.status === 'uploading');
        if (stillUploading) {
            setError('Wait for uploads to finish before sending.');
            return;
        }
        if ((!text && readyAttachments.length === 0) || running) return;

        // Build refs payload from active mentions that are still present in
        // the final text (user may have deleted a tag manually).
        const refsForRequest: AgentRef[] = [];
        for (const [tag, ref] of activeRefs.entries()) {
            if (text.includes(`@${tag}`)) refsForRequest.push(ref);
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
        setActivity('Thinking…');

        const controller = new AbortController();
        abortRef.current = controller;

        const updatePlaceholder = (mut: (t: AgentTurn) => AgentTurn) => {
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
                    updatePlaceholder((t) => ({
                        ...t,
                        text: (t.text ? t.text + '\n\n' : '') + e.text,
                    }));
                    break;
                case 'tool_call':
                    setActivity(
                        e.name === 'animate_image'
                            ? 'Animating image (Kling 3.0, ~1-3 min)…'
                            : e.name === 'generate_video'
                                ? (e.input_summary?.includes('cinematic')
                                    ? 'Generating cinematic clip (Kling 3.0, ~1-3 min)…'
                                    : 'Generating UGC clip (Veo 3.1, ~1-3 min)…')
                                : e.name === 'create_ugc_video' || e.name === 'create_clone_video'
                                    ? `Producing full video (${e.name}, ~5-12 min)…`
                                    : e.name === 'create_bulk_campaign'
                                        ? 'Dispatching bulk campaign…'
                                        : e.name === 'render_edited_video'
                                            ? 'Rendering edited video (~1-10 min)…'
                                            : `Calling ${e.name}…`
                    );
                    updatePlaceholder((t) => ({
                        ...t,
                        tool_calls: [
                            ...(t.tool_calls || []),
                            { name: e.name, input_summary: e.input_summary },
                        ],
                    }));
                    break;
                case 'tool_result':
                    setActivity('');
                    break;
                case 'keepalive':
                    // SSE keepalive ping — prevents connection timeout, no UI action needed
                    break;
                case 'artifact': {
                    const art = e.artifact as AgentArtifact;
                    updatePlaceholder((t) => ({
                        ...t,
                        artifacts: [...(t.artifacts || []), art],
                    }));
                    onArtifact?.();
                    break;
                }
                case 'done':
                    setRunning(false);
                    setActivity('');
                    abortRef.current = null;
                    break;
                case 'interrupted':
                    updatePlaceholder((t) => ({ ...t, interrupted: true }));
                    setRunning(false);
                    setActivity('');
                    abortRef.current = null;
                    break;
                case 'error':
                    setError(e.message);
                    setRunning(false);
                    setActivity('');
                    abortRef.current = null;
                    break;
            }
        };

        try {
            await streamAgent(text, projectId, onEvent, controller.signal, refsForRequest);
        } catch (err) {
            if ((err as Error).name === 'AbortError') {
                updatePlaceholder((t) => ({ ...t, interrupted: true }));
            } else {
                const msg = err instanceof Error ? err.message : String(err);
                // If the stream never started (e.g. 409 concurrency guard),
                // remove the optimistically-added user + placeholder turns.
                if (msg.includes('already running')) {
                    setTurns((prev) => prev.slice(0, -2));
                }
                setError(msg);
            }
        } finally {
            setRunning(false);
            setActivity('');
            abortRef.current = null;
        }
    }, [brief, running, projectId, onArtifact, activeRefs, attachments]);

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

    const insertMention = useCallback((item: MentionItem) => {
        const cursor = textareaRef.current?.selectionStart ?? brief.length;
        const before = brief.slice(0, mentionCursorStart);
        const after = brief.slice(cursor);
        const tagText = `@${item.tag}`;
        const newBrief = before + tagText + ' ' + after;
        setBrief(newBrief);
        setActiveRefs((prev) => {
            const next = new Map(prev);
            next.set(item.tag, item.ref);
            return next;
        });
        setMentionOpen(false);
        // restore focus + place caret after the inserted tag
        setTimeout(() => {
            const pos = before.length + tagText.length + 1;
            textareaRef.current?.focus();
            textareaRef.current?.setSelectionRange(pos, pos);
        }, 0);
    }, [brief, mentionCursorStart]);

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
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
            e.preventDefault();
            handleRun();
        }
    };

    const handleStop = useCallback(() => {
        abortRef.current?.abort();
        // fire-and-forget backend interrupt as a fallback
        stopAgent(projectId).catch(() => {});
    }, [projectId]);

    const handleReset = useCallback(async () => {
        if (!confirm('Clear this agent chat? This cannot be undone.')) return;
        try {
            await resetAgentThread(projectId);
            setTurns([]);
            setSessionId(null);
            setError(null);
        } catch (err) {
            setError(err instanceof Error ? err.message : String(err));
        }
    }, [projectId]);

    return (
        <>
            {!open && (
                <button
                    onClick={() => setOpen(true)}
                    title="Run AI agent"
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
                    Agent
                </button>
            )}

            {open && (
                <div
                    style={{
                        position: 'fixed',
                        right: '24px',
                        bottom: '24px',
                        zIndex: 950,
                        width: '480px',
                        height: 'calc(100vh - 80px)',
                        maxHeight: '720px',
                        background: 'white',
                        borderRadius: '16px',
                        boxShadow: '0 20px 60px rgba(13,27,62,0.18)',
                        border: '1px solid rgba(51,122,255,0.12)',
                        display: 'flex',
                        flexDirection: 'column',
                        overflow: 'hidden',
                    }}
                >
                    {/* Header */}
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
                            <span style={{ fontSize: '14px', fontWeight: 700, color: '#0D1B3E' }}>Creative Agent</span>
                            <span style={{ fontSize: '10px', fontWeight: 600, color: '#337AFF', background: 'rgba(51,122,255,0.12)', padding: '2px 6px', borderRadius: '4px' }}>BETA</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <button
                                onClick={handleReset}
                                title="Clear chat"
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
                            <button
                                onClick={() => setOpen(false)}
                                title="Close"
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
                        </div>
                    </div>

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
                                Loading chat…
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
                                Describe what you want the agent to make. It can chain image generation, animation, and video tools to deliver finished assets.
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
                            return turns.map((turn, idx) => (
                                <TurnBubble key={idx} turn={turn} refMap={refMap} />
                            ));
                        })()}

                        {running && activity && (
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
                                <span
                                    style={{
                                        display: 'inline-block',
                                        width: '6px',
                                        height: '6px',
                                        borderRadius: '50%',
                                        background: '#337AFF',
                                        animation: 'pulse 1.2s ease-in-out infinite',
                                    }}
                                />
                                {activity}
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
                        {mentionOpen && filteredMentions.length > 0 && (
                            <MentionDropdown
                                groups={groupedMentions}
                                ordered={orderedMentions}
                                activeIndex={mentionIndex}
                                onPick={insertMention}
                                onHover={setMentionIndex}
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
                        <textarea
                            ref={textareaRef}
                            value={brief}
                            onChange={handleBriefChange}
                            onKeyDown={handleBriefKeyDown}
                            placeholder="Ask the agent… use @ to reference products, models, images, or videos"
                            disabled={running}
                            rows={2}
                            style={{
                                width: '100%',
                                padding: '8px 10px',
                                border: '1px solid rgba(13,27,62,0.12)',
                                borderRadius: '10px',
                                fontSize: '13px',
                                fontFamily: 'inherit',
                                color: '#0D1B3E',
                                resize: 'none',
                                outline: 'none',
                                background: running ? 'rgba(13,27,62,0.03)' : 'white',
                                marginBottom: '8px',
                            }}
                        />
                        <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <button
                                onClick={() => fileInputRef.current?.click()}
                                disabled={running}
                                title="Attach image or video"
                                style={{
                                    width: '38px',
                                    height: '38px',
                                    flexShrink: 0,
                                    borderRadius: '10px',
                                    border: '1px solid rgba(13,27,62,0.12)',
                                    background: running ? 'rgba(13,27,62,0.03)' : 'white',
                                    cursor: running ? 'not-allowed' : 'pointer',
                                    color: '#337AFF',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                }}
                            >
                                <svg viewBox="0 0 24 24" style={{ width: '18px', height: '18px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                                    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
                                </svg>
                            </button>
                            {running ? (
                                <button
                                    onClick={handleStop}
                                    style={{
                                        flex: 1,
                                        padding: '9px 14px',
                                        borderRadius: '10px',
                                        border: '1px solid rgba(255,82,82,0.3)',
                                        cursor: 'pointer',
                                        background: 'rgba(255,82,82,0.08)',
                                        color: '#C53030',
                                        fontSize: '13px',
                                        fontWeight: 600,
                                    }}
                                >
                                    Stop
                                </button>
                            ) : (() => {
                                const hasReadyAttachments = attachments.some((a) => a.status === 'ready');
                                const uploading = attachments.some((a) => a.status === 'uploading');
                                const canSend = (brief.trim() !== '' || hasReadyAttachments) && !uploading;
                                return (
                                    <button
                                        onClick={handleRun}
                                        disabled={!canSend}
                                        style={{
                                            flex: 1,
                                            padding: '9px 14px',
                                            borderRadius: '10px',
                                            border: 'none',
                                            cursor: !canSend ? 'not-allowed' : 'pointer',
                                            background: !canSend
                                                ? 'rgba(13,27,62,0.08)'
                                                : 'linear-gradient(135deg, #337AFF 0%, #5B8FFF 100%)',
                                            color: !canSend ? '#8A93B0' : 'white',
                                            fontSize: '13px',
                                            fontWeight: 600,
                                        }}
                                    >
                                        {uploading ? 'Uploading…' : 'Send'}
                                    </button>
                                );
                            })()}
                        </div>
                    </div>
                </div>
            )}
            <style jsx>{`
                @keyframes pulse {
                    0%, 100% { opacity: 0.4; transform: scale(0.85); }
                    50% { opacity: 1; transform: scale(1.15); }
                }
            `}</style>
        </>
    );
}

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
    // Match **bold**, @tag_name patterns
    const regex = /(\*\*(.+?)\*\*)|(@([a-z0-9_]+))/g;
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
            // @tag match
            const tag = match[4];
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
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                            src={ref.image_url || ref.video_url}
                            alt={ref.name || tag}
                            style={{
                                width: '20px',
                                height: '20px',
                                borderRadius: '4px',
                                objectFit: 'cover',
                                flexShrink: 0,
                            }}
                        />
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

function TurnBubble({ turn, refMap }: { turn: AgentTurn; refMap: Map<string, AgentRef> }) {
    const isUser = turn.role === 'user';
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
                {turn.text && (
                    <div style={{ whiteSpace: 'pre-wrap' }}>{renderMessageContent(turn.text, refMap, isUser)}</div>
                )}

                {turn.artifacts && turn.artifacts.length > 0 && (
                    <div
                        style={{
                            marginTop: turn.text ? '10px' : 0,
                            display: 'grid',
                            gridTemplateColumns: turn.artifacts.length === 1 ? '1fr' : '1fr 1fr',
                            gap: '6px',
                        }}
                    >
                        {turn.artifacts.map((a, i) => (
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

                {turn.interrupted && (
                    <div
                        style={{
                            marginTop: '6px',
                            fontSize: '11px',
                            color: isUser ? 'rgba(255,255,255,0.75)' : '#C53030',
                            fontStyle: 'italic',
                        }}
                    >
                        (stopped)
                    </div>
                )}
            </div>
        </div>
    );
}

function AttachmentChip({ att, onRemove }: { att: AttachedFile; onRemove: () => void }) {
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
                        ? 'Uploading'
                        : att.status === 'error'
                            ? 'Failed'
                            : att.type}
                </span>
            </div>
            <button
                type="button"
                onClick={onRemove}
                title="Remove"
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
}

const GROUP_LABELS: Record<MentionItem['type'], string> = {
    product: 'Products',
    influencer: 'Models',
    image: 'Images',
    video: 'Videos',
};

function MentionDropdown({ groups, ordered, activeIndex, onPick, onHover }: MentionDropdownProps) {
    const groupOrder: MentionItem['type'][] = ['product', 'influencer', 'image', 'video'];
    return (
        <div
            style={{
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
            }}
        >
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
                            {GROUP_LABELS[g]}
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
