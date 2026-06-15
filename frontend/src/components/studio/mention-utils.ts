import type { AgentRef } from '@/lib/creative-os-api';

export interface MentionItem {
    type: AgentRef['type'];
    tag: string;
    name: string;
    image_url?: string;
    views?: string[];
    ref: AgentRef;
    product_type?: 'physical' | 'digital';
    clipsByFrame?: Record<string, { clip_id: string; video_url?: string }>;
    looksByImage?: Record<string, { look_id: string; label?: string }>;
}

export type MentionGroupType = 'product' | 'influencer' | 'clone' | 'image' | 'video';

export type MentionGroups = Record<MentionGroupType, MentionItem[]>;

/** Build the AgentRef payload for a picked mention (composer or inline chat selector). */
export function buildMentionRef(item: MentionItem, chosenImageUrl?: string): AgentRef {
    let finalRef: AgentRef = chosenImageUrl
        ? { ...item.ref, image_url: chosenImageUrl }
        : item.ref;
    if (chosenImageUrl && item.clipsByFrame && item.clipsByFrame[chosenImageUrl]) {
        finalRef = { ...finalRef, app_clip_id: item.clipsByFrame[chosenImageUrl].clip_id };
    } else if (chosenImageUrl && item.looksByImage && item.looksByImage[chosenImageUrl]) {
        finalRef = { ...finalRef, look_id: item.looksByImage[chosenImageUrl].look_id };
    } else if (!chosenImageUrl && item.clipsByFrame) {
        const entries = Object.entries(item.clipsByFrame);
        if (entries.length === 1) {
            const [frameUrl, { clip_id }] = entries[0];
            finalRef = { ...finalRef, image_url: frameUrl, app_clip_id: clip_id };
        }
    }
    return finalRef;
}

/** Whether picking this item should open the multi-shot sub-picker first. */
export function mentionItemNeedsShotPicker(item: MentionItem): boolean {
    return (
        (item.type === 'product' || item.type === 'influencer' || item.type === 'clone') &&
        !!item.views &&
        item.views.length > 1
    );
}
