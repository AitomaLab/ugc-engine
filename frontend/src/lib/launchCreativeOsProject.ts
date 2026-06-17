import type { AppRouterInstance } from 'next/dist/shared/lib/app-router-context.shared-runtime';
import { creativeFetch, type AgentRef } from '@/lib/creative-os-api';

export interface LaunchCreativeOsProjectOptions {
    brief: string;
    refs?: AgentRef[];
    seedance?: boolean;
}

/**
 * Create a Creative OS project and navigate with prefilled agent brief + @mention refs.
 * Mirrors the home dashboard submit flow in app/page.tsx.
 */
export async function launchCreativeOsProject(
    router: AppRouterInstance,
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
    const refsParam = refsArray.length > 0
        ? `&refs=${encodeURIComponent(JSON.stringify(refsArray))}`
        : '';
    const seedanceParam = seedance ? '&seedance=1' : '';
    router.push(
        `/projects/${newProject.id}?brief=${encodeURIComponent(trimmed)}${refsParam}${seedanceParam}`,
    );
    return newProject.id;
}
