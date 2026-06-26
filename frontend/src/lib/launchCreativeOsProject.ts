import type { AppRouterInstance } from 'next/dist/shared/lib/app-router-context.shared-runtime';
import { storeAgentLaunchDraft } from '@/lib/agentLaunchDraft';
import { creativeFetch, type AgentRef } from '@/lib/creative-os-api';

export interface LaunchCreativeOsProjectOptions {
    brief: string;
    refs?: AgentRef[];
    seedance?: boolean;
}

/**
 * Create a Creative OS project and navigate with prefilled agent brief + @mention refs.
 * Large briefs are stored in sessionStorage — the URL only carries `?launch=1`.
 */
export async function launchCreativeOsProject(
    _router: AppRouterInstance,
    { brief, refs = [], seedance = false }: LaunchCreativeOsProjectOptions,
): Promise<string | null> {
    const trimmed = brief.trim();
    if (!trimmed) return null;

    const nameRes = await creativeFetch<{ name: string }>('/creative-os/projects/generate-name', {
        method: 'POST',
        body: JSON.stringify({ prompt: trimmed }),
    });
    const projectName = nameRes.name || 'New Project';
    const newProject = await creativeFetch<{ id: string }>('/creative-os/projects/', {
        method: 'POST',
        body: JSON.stringify({ name: projectName }),
    });
    if (!newProject?.id) return null;

    const mentionRefs = refs.filter((r) => trimmed.includes(`@${r.tag}`));
    const refsArray = mentionRefs.length > 0 ? mentionRefs : refs;

    storeAgentLaunchDraft(newProject.id, {
        brief: trimmed,
        refs: refsArray,
        seedance,
    });

    try {
        localStorage.setItem('activeProjectId', newProject.id);
    } catch {
        // ignore
    }

    const target = `/projects/${newProject.id}?launch=1`;
    // Hard navigation — soft router.push from Analytics modals is cancelled
    // when PostDetailModal's onClose triggers router.replace on /schedule.
    window.location.assign(target);
    return newProject.id;
}
