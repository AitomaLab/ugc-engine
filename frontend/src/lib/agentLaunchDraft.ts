import type { AgentRef } from '@/lib/creative-os-api';

export interface AgentLaunchDraft {
    brief: string;
    refs: AgentRef[];
    seedance: boolean;
}

function storageKey(projectId: string): string {
    return `agent-launch:${projectId}`;
}

/** Persist a large agent brief + refs for handoff after project creation. */
export function storeAgentLaunchDraft(projectId: string, draft: AgentLaunchDraft): void {
    if (typeof window === 'undefined') return;
    try {
        sessionStorage.setItem(storageKey(projectId), JSON.stringify(draft));
        const verify = sessionStorage.getItem(storageKey(projectId));
        if (!verify) {
            throw new Error('sessionStorage write failed');
        }
    } catch {
        throw new Error(
            'Could not save launch brief — check browser privacy settings and try again.',
        );
    }
}

/** Read and remove a launch draft (one-time consume on project page mount). */
export function consumeAgentLaunchDraft(projectId: string): AgentLaunchDraft | null {
    if (typeof window === 'undefined') return null;
    try {
        const raw = sessionStorage.getItem(storageKey(projectId));
        sessionStorage.removeItem(storageKey(projectId));
        if (!raw) return null;
        const parsed = JSON.parse(raw) as AgentLaunchDraft;
        if (!parsed?.brief || typeof parsed.brief !== 'string') return null;
        return {
            brief: parsed.brief,
            refs: Array.isArray(parsed.refs) ? parsed.refs : [],
            seedance: Boolean(parsed.seedance),
        };
    } catch {
        return null;
    }
}
