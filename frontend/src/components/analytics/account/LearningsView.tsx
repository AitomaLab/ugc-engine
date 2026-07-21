'use client';

import { useCreativeGuidelines } from '../analytics-types';
import AccountLearningsTab from './AccountLearningsTab';

interface Props {
    refreshKey?: number;
}

/**
 * Self-fetching wrapper for the AI Learnings body. The creative-guidelines
 * loop is user-level (spans every connected account), so both the
 * All-accounts scope and a scoped Studio account render the same content —
 * this wrapper dedupes the fetch wiring for both call sites.
 */
export default function LearningsView({ refreshKey = 0 }: Props) {
    const { data: guidelines, loading } = useCreativeGuidelines(refreshKey);

    return (
        <AccountLearningsTab
            guidelines={guidelines?.guidelines ?? null}
            updatedAt={guidelines?.updated_at ?? null}
            loading={loading}
        />
    );
}
