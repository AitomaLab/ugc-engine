import { waitForFreshSession } from '@/lib/auth';
import {
    creativeFetch,
    GALLERY_FETCH_ATTEMPTS,
    GALLERY_FETCH_TIMEOUT_MS,
} from '@/lib/creative-os-api';

export const projectsListKey = '/creative-os/projects/';

export function projectFullKey(projectId: string): string {
    return `/creative-os/projects/${projectId}/full`;
}

export const studioSwrOptions = {
    refreshInterval: 30_000,
    revalidateOnFocus: true,
    keepPreviousData: true,
    dedupingInterval: 5_000,
    revalidateOnReconnect: true,
} as const;

export async function creativeOsFetcher<T>(path: string): Promise<T> {
    await waitForFreshSession();
    return creativeFetch<T>(path);
}

export async function projectFullFetcher<T>(path: string): Promise<T> {
    await waitForFreshSession();
    return creativeFetch<T>(
        path,
        undefined,
        GALLERY_FETCH_TIMEOUT_MS,
        GALLERY_FETCH_ATTEMPTS,
    );
}
