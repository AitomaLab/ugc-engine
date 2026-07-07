'use client';

import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/utils';

export type CreditCostTable = Record<string, number>;

const DEFAULT_COSTS: CreditCostTable = {
  digital_15s: 67,
  digital_30s: 134,
  physical_15s: 101,
  physical_30s: 202,
  creative_os_image: 10,
  cinematic_image_2k: 10,
  cinematic_video_8s: 44,
  video_clip_veo_fast_720p: 34,
  video_clip_cinematic_per_s: 12,
  cinematic_clip_5s: 60,
  brand_studio_ideas_batch_min: 6,
  brand_studio_slide_render: 25,
};

let cache: CreditCostTable | null = null;
let inflight: Promise<CreditCostTable> | null = null;

export async function fetchCreditCosts(): Promise<CreditCostTable> {
  if (cache) return cache;
  if (!inflight) {
    inflight = apiFetch<CreditCostTable>('/api/credits/costs')
      .then((table) => {
        cache = { ...DEFAULT_COSTS, ...table };
        return cache;
      })
      .catch(() => {
        cache = DEFAULT_COSTS;
        return cache;
      });
  }
  return inflight;
}

export function useCreditCosts() {
  const [costs, setCosts] = useState<CreditCostTable>(DEFAULT_COSTS);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchCreditCosts()
      .then((table) => {
        if (!cancelled) setCosts(table);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { costs, loading };
}

export function costForUgc(
  costs: CreditCostTable,
  productType: 'digital' | 'physical',
  duration: 15 | 30,
  seedance = false,
): number {
  const prefix = seedance ? `${productType}_seedance` : productType;
  return costs[`${prefix}_${duration}s`] ?? DEFAULT_COSTS[`${productType}_${duration}s`] ?? 67;
}

export function costForVideoClip(
  costs: CreditCostTable,
  mode: string,
  clipLength: number,
  hasReference = false,
): number {
  if (mode === 'ugc' || mode.includes('veo')) {
    return costs.video_clip_veo_fast_720p ?? 34;
  }
  if (mode === 'cinematic_video') {
    const flat = costs[`cinematic_clip_${clipLength}s`];
    if (flat) return flat;
    const perS = costs.video_clip_cinematic_per_s ?? 12;
    return perS * clipLength;
  }
  if (mode.startsWith('seedance')) {
    const perS = hasReference
      ? (costs.video_clip_seedance_with_ref_per_s ?? 14)
      : (costs.video_clip_seedance_no_ref_per_s ?? 23);
    return perS * clipLength;
  }
  return costs.video_clip_veo_fast_720p ?? 34;
}

export function costForImage(costs: CreditCostTable): number {
  return costs.creative_os_image ?? 10;
}

export function costForBrandStudioIdeas(costs: CreditCostTable, ideaCount: number): number {
  const perIdea = costs.brand_studio_ideas_per_idea ?? 2;
  const minBatch = costs.brand_studio_ideas_batch_min ?? 6;
  const n = Math.max(1, Math.min(8, Math.round(ideaCount)));
  return Math.max(minBatch, perIdea * n);
}

export function costForBrandStudioSlide(costs: CreditCostTable): number {
  return costs.brand_studio_slide_render ?? 25;
}

export function costForBrandStudioCarousel(costs: CreditCostTable, slideCount: number): number {
  return costForBrandStudioSlide(costs) * Math.max(1, slideCount);
}

export function costForCinematicShotImage(costs: CreditCostTable): number {
  return costs.cinematic_image_2k ?? 10;
}

export function costForCinematicShotVideo(costs: CreditCostTable): number {
  return costs.cinematic_video_8s ?? 44;
}

export function creditsFromJobMetadata(job: {
  metadata?: { credits_deducted?: number } | null;
}): number | null {
  const raw = job.metadata?.credits_deducted;
  if (raw == null) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}
