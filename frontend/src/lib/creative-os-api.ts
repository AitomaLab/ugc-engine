/**
 * Creative OS — API Client
 *
 * Utility for calling the Creative OS microservice (port 8001).
 * Auto-attaches Supabase JWT and project ID, same pattern as utils.ts apiFetch.
 */

import { supabase } from '@/lib/supabaseClient';

const CREATIVE_OS_URL = process.env.NEXT_PUBLIC_CREATIVE_OS_URL || 'http://localhost:8001';

async function getAuthToken(): Promise<string | null> {
    try {
        const { data: { session } } = await supabase.auth.getSession();
        return session?.access_token ?? null;
    } catch {
        return null;
    }
}

export async function creativeFetch<T = unknown>(
    path: string,
    options?: RequestInit,
    timeoutMs: number = 120_000,
): Promise<T> {
    const method = options?.method?.toUpperCase() || 'GET';
    const headers: Record<string, string> = {};

    if (method !== 'GET' && method !== 'DELETE') {
        headers['Content-Type'] = 'application/json';
    }

    const token = await getAuthToken();
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    if (typeof window !== 'undefined') {
        const projectId = localStorage.getItem('activeProjectId');
        if (projectId) {
            headers['X-Project-Id'] = projectId;
        }
    }

    // Configurable timeout — default 2 min, longer for heavy generation pipelines
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

    try {
        const res = await fetch(`${CREATIVE_OS_URL}${path}`, {
            ...options,
            headers: { ...headers, ...options?.headers },
            signal: controller.signal,
        });

        if (!res.ok) {
            const error = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(error.detail || `Creative OS error: ${res.status}`);
        }
        return res.json();
    } finally {
        clearTimeout(timeoutId);
    }
}

// ── Types ──────────────────────────────────────────────────────────────

export interface PromptOption {
    title: string;
    prompt: string;
}

export interface EnhanceResponse {
    options: PromptOption[];
    mode: string;
    model: string;
}

export interface ImageMode {
    id: string;
    label: string;
}

export interface VideoMode {
    id: string;
    label: string;
    clip_lengths: number[];
}

export interface AnimationStyle {
    id: string;
    label: string;
    model?: string;
}

export interface CreativeOSConfig {
    image_modes: ImageMode[];
    video_modes: VideoMode[];
    animation_styles: {
        director: AnimationStyle[];
        ugc: AnimationStyle[];
    };
}

export interface AnimateResult {
    status: string;
    task_id: string;
    model: string;
    style: string;
    prompt: string;
    duration?: number;
}

export interface TaskStatus {
    status: 'processing' | 'complete' | 'failed';
    task_id: string;
    video_url?: string;
    error?: string;
}

export interface CostBreakdown {
    total_credits: number;
    breakdown: { item: string; credits: number }[];
}

// ── File uploads ───────────────────────────────────────────────────────
export interface UploadResult {
    url: string;
    type: 'image' | 'video';
    name: string;
    size: number;
}

/** Upload an image or video to the Creative OS user-uploads bucket. */
export async function uploadAgentFile(file: File): Promise<UploadResult> {
    const token = await getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const form = new FormData();
    form.append('file', file);
    const res = await fetch(`${CREATIVE_OS_URL}/creative-os/upload/file`, {
        method: 'POST',
        headers,
        body: form,
    });
    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || `Upload failed: ${res.status}`);
    }
    return res.json();
}

/** Transcribe a recorded audio blob via ElevenLabs Scribe. */
export async function transcribeAudio(blob: Blob): Promise<{ text: string; language: string }> {
    const token = await getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const form = new FormData();
    const ext = blob.type.includes('webm') ? 'webm' : blob.type.includes('mp4') ? 'mp4' : blob.type.includes('ogg') ? 'ogg' : 'wav';
    form.append('file', blob, `dictation.${ext}`);
    const res = await fetch(`${CREATIVE_OS_URL}/creative-os/transcribe`, {
        method: 'POST',
        headers,
        body: form,
    });
    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || `Transcription failed: ${res.status}`);
    }
    return res.json();
}

// ── Managed Agent ──────────────────────────────────────────────────────
export interface CaptionStylePreview {
    id: string;
    name: string;
    description: string;
    sample_text: string;
    highlight_word_index: number;
    font_family: string;
    font_weight: number;
    color: string;
    highlight_color: string;
    stroke_color?: string;
    uppercase?: boolean;
}

export interface AgentArtifact {
    type: 'image' | 'video' | 'caption_styles_preview';
    url?: string;
    shot_id?: string;
    job_id?: string;
    styles?: CaptionStylePreview[];
}

export type AgentTurnRole = 'user' | 'agent';

export interface AgentToolCallSummary {
    name: string;
    input_summary: string;
    mode?: string | null;
}

export type AgentRefType = 'product' | 'influencer' | 'image' | 'video';

export interface AgentRef {
    type: AgentRefType;
    tag: string;
    name?: string;
    id?: string;
    image_url?: string;
    video_url?: string;
    shot_id?: string;
    job_id?: string;
    app_clip_id?: string;
    product_type?: 'physical' | 'digital';
}

export interface AgentPendingConfirmation {
    credits: number;
    summaries: string[];
}

export interface AgentTurn {
    role: AgentTurnRole;
    text: string;
    artifacts?: AgentArtifact[];
    tool_calls?: AgentToolCallSummary[];
    refs?: AgentRef[];
    interrupted?: boolean;
    pendingConfirmation?: AgentPendingConfirmation;
    ts: number;
}

export interface AgentThread {
    session_id: string | null;
    turns: AgentTurn[];
}

export type AgentStreamEvent =
    | { type: 'session'; session_id: string }
    | { type: 'agent_message'; text: string }
    | { type: 'tool_call'; name: string; input_summary: string; mode?: string | null; tool_use_id: string }
    | { type: 'tool_result'; tool_use_id: string; summary: string; is_error: boolean }
    | { type: 'artifact'; artifact: AgentArtifact }
    | { type: 'confirmation_pending'; credits: number; summaries: string[] }
    | { type: 'done'; session_id: string }
    | { type: 'interrupted' }
    | { type: 'keepalive'; tool_use_id?: string; elapsed_seconds: number; phase?: string }
    | { type: 'disconnected' }
    | { type: 'error'; message: string };

/** Load the persisted thread for the current project. */
export async function getAgentThread(projectId: string): Promise<AgentThread> {
    const token = await getAuthToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(
        `${CREATIVE_OS_URL}/creative-os/agent/thread?project_id=${encodeURIComponent(projectId)}`,
        { headers },
    );
    if (!res.ok) {
        if (res.status === 404) return { session_id: null, turns: [] };
        throw new Error(`Failed to load agent thread: ${res.status}`);
    }
    return res.json();
}

/** Wipe the persisted thread for the current project. */
export async function resetAgentThread(projectId: string): Promise<void> {
    const token = await getAuthToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${CREATIVE_OS_URL}/creative-os/agent/reset`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ project_id: projectId }),
    });
    if (!res.ok) throw new Error(`Failed to reset agent thread: ${res.status}`);
}

/**
 * Eagerly create the Anthropic session for this project so the user's first
 * `streamAgent` call doesn't pay for `_create_session`. Fire-and-forget — any
 * failure falls back to the on-demand session creation in the send path.
 */
export async function prewarmAgentSession(projectId: string): Promise<void> {
    const token = await getAuthToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    try {
        await fetch(`${CREATIVE_OS_URL}/creative-os/agent/session/prewarm`, {
            method: 'POST',
            headers,
            body: JSON.stringify({ project_id: projectId }),
        });
    } catch {
        // best effort — the send path has its own session-create fallback.
    }
}

/** Best-effort: tell backend to interrupt the active session for this project. */
export async function stopAgent(projectId: string): Promise<void> {
    const token = await getAuthToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    try {
        await fetch(`${CREATIVE_OS_URL}/creative-os/agent/stop`, {
            method: 'POST',
            headers,
            body: JSON.stringify({ project_id: projectId }),
        });
    } catch {
        // best effort
    }
}

/**
 * Stream one turn of the managed agent over SSE. Each parsed event is
 * delivered to `onEvent`. Pass an `AbortSignal` so the caller can stop
 * mid-stream — that triggers backend `user.interrupt`.
 *
 * Uses fetch + ReadableStream rather than EventSource so we can POST a
 * body and attach an Authorization header.
 */
export async function streamAgent(
    brief: string,
    projectId: string,
    onEvent: (e: AgentStreamEvent) => void,
    signal: AbortSignal,
    refs?: AgentRef[],
    useSeedance?: boolean,
    lang?: 'en' | 'es',
    quickMode?: boolean,
): Promise<void> {
    const token = await getAuthToken();
    const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        Accept: 'text/event-stream',
    };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${CREATIVE_OS_URL}/creative-os/agent/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
            brief,
            project_id: projectId,
            refs: refs ?? undefined,
            use_seedance: useSeedance ?? false,
            lang: lang ?? undefined,
            quick_mode: quickMode ?? false,
        }),
        signal,
    });
    if (!res.ok || !res.body) {
        const error = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(error.detail || `Agent stream error: ${res.status}`);
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let sawToolCall = false;
    let sawDone = false;

    while (true) {
        let value: Uint8Array | undefined;
        let done = false;
        try {
            const r = await reader.read();
            value = r.value;
            done = r.done;
        } catch (err) {
            // Connection dropped mid-stream. If tools were in flight, treat it as
            // a soft disconnect — backend keeps running, user can refresh to
            // reconnect. Otherwise surface the original error.
            if (sawToolCall && !sawDone) {
                onEvent({ type: 'disconnected' });
                return;
            }
            throw err;
        }
        if (done) {
            if (sawToolCall && !sawDone) onEvent({ type: 'disconnected' });
            break;
        }
        buffer += decoder.decode(value, { stream: true });

        // Parse complete SSE frames (separated by blank lines).
        let sep = buffer.indexOf('\n\n');
        while (sep !== -1) {
            const frame = buffer.slice(0, sep);
            buffer = buffer.slice(sep + 2);
            sep = buffer.indexOf('\n\n');

            // Each frame is `data: {...}` (possibly multi-line).
            const dataLines = frame
                .split('\n')
                .filter((l) => l.startsWith('data:'))
                .map((l) => l.slice(5).trimStart());
            if (dataLines.length === 0) continue;
            const payload = dataLines.join('\n');
            try {
                const parsed = JSON.parse(payload) as AgentStreamEvent;
                if (parsed.type === 'tool_call') sawToolCall = true;
                if (parsed.type === 'done') sawDone = true;
                onEvent(parsed);
            } catch (err) {
                console.warn('agent SSE parse error:', err, payload);
            }
        }
    }
}
