/**
 * Shared coordinator for POST /creative-os/projects/:id/jobs-status.
 * One in-flight request per project, queued follow-up, failure backoff.
 */

import {
    creativeFetch,
    CreativeFetchAbortedError,
    JOBS_STATUS_FETCH_ATTEMPTS,
    JOBS_STATUS_FETCH_TIMEOUT_MS,
} from '@/lib/creative-os-api';

export type JobsStatusImage = {
    id?: string;
    status?: string;
    status_message?: string;
    progress?: number;
    preview_url?: string;
    image_url?: string;
    created_at?: string;
};

export type JobsStatusVideo = {
    id?: string;
    status?: string;
    status_message?: string;
    progress?: number;
    preview_url?: string;
    preview_type?: string;
    final_video_url?: string;
    video_url?: string;
    thumbnail_url?: string;
    created_at?: string;
};

export type JobsStatusResponse = {
    images: JobsStatusImage[];
    videos: JobsStatusVideo[];
};

type PendingIds = {
    imageIds: Set<string>;
    videoIds: Set<string>;
    signal?: AbortSignal;
};

type ProjectPollState = {
    inFlight: Promise<JobsStatusResponse> | null;
    pending: PendingIds | null;
    backoffMs: number;
    consecutiveFailures: number;
    lastFailureAt: number;
};

const states = new Map<string, ProjectPollState>();

const BACKOFF_STEPS_MS = [2000, 5000, 10000] as const;

function getState(projectId: string): ProjectPollState {
    let state = states.get(projectId);
    if (!state) {
        state = {
            inFlight: null,
            pending: null,
            backoffMs: 0,
            consecutiveFailures: 0,
            lastFailureAt: 0,
        };
        states.set(projectId, state);
    }
    return state;
}

function mergePending(
    state: ProjectPollState,
    imageIds: string[],
    videoIds: string[],
    signal?: AbortSignal,
) {
    if (!state.pending) {
        state.pending = { imageIds: new Set(), videoIds: new Set(), signal };
    }
    for (const id of imageIds) state.pending.imageIds.add(id);
    for (const id of videoIds) state.pending.videoIds.add(id);
    if (signal) state.pending.signal = signal;
}

function sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
}

function isBackoffError(err: unknown): boolean {
    if (err instanceof CreativeFetchAbortedError) return err.kind === 'timeout';
    if (err instanceof TypeError) {
        const msg = String(err.message || err).toLowerCase();
        return msg.includes('failed to fetch') || msg.includes('network') || msg.includes('load failed');
    }
    return false;
}

/** Milliseconds to wait before the next poll attempt (0 when healthy). */
export function getJobsStatusPollDelayMs(projectId: string): number {
    const state = getState(projectId);
    if (state.backoffMs <= 0) return 0;
    const elapsed = Date.now() - state.lastFailureAt;
    return Math.max(0, state.backoffMs - elapsed);
}

/** Coalesced jobs-status fetch — at most one in-flight per project. */
export async function fetchJobsStatus(
    projectId: string,
    imageIds: string[],
    videoIds: string[],
    options?: { signal?: AbortSignal },
): Promise<JobsStatusResponse> {
    const state = getState(projectId);

    if (state.inFlight) {
        mergePending(state, imageIds, videoIds, options?.signal);
        return state.inFlight;
    }

    const delayMs = getJobsStatusPollDelayMs(projectId);
    if (delayMs > 0) {
        await sleep(delayMs);
        if (options?.signal?.aborted) {
            throw new CreativeFetchAbortedError('unmount');
        }
    }

    const run = async (): Promise<JobsStatusResponse> => {
        try {
            const result = await creativeFetch<JobsStatusResponse>(
                `/creative-os/projects/${projectId}/jobs-status`,
                {
                    method: 'POST',
                    body: JSON.stringify({ image_ids: imageIds, video_ids: videoIds }),
                    signal: options?.signal,
                },
                JOBS_STATUS_FETCH_TIMEOUT_MS,
                JOBS_STATUS_FETCH_ATTEMPTS,
            );
            state.consecutiveFailures = 0;
            state.backoffMs = 0;
            return result;
        } catch (err) {
            if (err instanceof CreativeFetchAbortedError && err.kind === 'unmount') {
                throw err;
            }
            if (isBackoffError(err)) {
                state.consecutiveFailures += 1;
                const step = Math.min(state.consecutiveFailures - 1, BACKOFF_STEPS_MS.length - 1);
                state.backoffMs = BACKOFF_STEPS_MS[step];
                state.lastFailureAt = Date.now();
            }
            throw err;
        } finally {
            state.inFlight = null;
            const pending = state.pending;
            state.pending = null;
            if (pending && (pending.imageIds.size > 0 || pending.videoIds.size > 0)) {
                void fetchJobsStatus(
                    projectId,
                    [...pending.imageIds],
                    [...pending.videoIds],
                    { signal: pending.signal },
                );
            }
        }
    };

    state.inFlight = run();
    return state.inFlight;
}
