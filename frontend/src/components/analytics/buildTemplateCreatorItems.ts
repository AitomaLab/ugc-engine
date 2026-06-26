import type { AgentRef } from '@/lib/creative-os-api';
import type { MentionGroups, MentionItem } from '@/components/studio/mention-utils';
import { slugifyName } from '@/lib/utils';

export function buildTemplateCreatorGroups(
    influencers: Array<{ id?: string; name?: string; image_url?: string; character_views?: string[] }>,
    clones: Array<{ id?: string; name?: string; looks?: Array<{ id?: string; image_url?: string; is_base?: boolean; label?: string }> }>,
): MentionGroups {
    const items: MentionItem[] = [];
    const seenInfluencerTags = new Set<string>();

    for (const inf of influencers) {
        const name = inf.name || 'model';
        const tag = slugifyName(name);
        if (!tag || seenInfluencerTags.has(tag)) continue;
        seenInfluencerTags.add(tag);
        items.push({
            type: 'influencer',
            tag,
            name,
            image_url: inf.image_url || undefined,
            ref: { type: 'influencer', tag, name, id: inf.id, image_url: inf.image_url || undefined },
        });
    }

    const seenCloneTags = new Set<string>();
    for (const clone of clones) {
        const name = clone.name || 'clone';
        const tag = `${slugifyName(name)}_clone`;
        if (!tag || seenCloneTags.has(tag)) continue;
        const validLooks = (Array.isArray(clone.looks) ? clone.looks : []).filter(
            (l) => l.image_url && l.image_url !== 'error' && String(l.image_url).startsWith('http'),
        );
        if (!validLooks.length) continue;
        seenCloneTags.add(tag);
        const baseLook = validLooks.find((l) => l.is_base) || validLooks[0];
        const thumb = baseLook.image_url!;
        items.push({
            type: 'clone',
            tag,
            name,
            image_url: thumb,
            views: validLooks.length > 1 ? validLooks.map((l) => l.image_url!) : undefined,
            looksByImage: Object.fromEntries(
                validLooks.map((l) => [l.image_url!, { look_id: l.id || '', label: l.label }]),
            ),
            ref: {
                type: 'clone',
                tag,
                name,
                id: clone.id,
                image_url: thumb,
                look_id: baseLook.id,
            },
        });
    }

    const influencersList = items.filter((i) => i.type === 'influencer');
    const clonesList = items.filter((i) => i.type === 'clone');

    return {
        product: [],
        influencer: influencersList,
        clone: clonesList,
        image: [],
        video: [],
    };
}

export type { AgentRef };
