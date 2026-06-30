'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { supabase } from '@/lib/supabaseClient';
import InvitesTab from './InvitesTab';
import FeedbackTab from './FeedbackTab';
import OnboardingTab from './OnboardingTab';

const ADMIN_EMAIL = 'max@aitoma.ai';
const PRIMARY = '#337AFF';

type AdminTab = 'invites' | 'feedback' | 'onboarding';

export default function AdminPage() {
    const router = useRouter();
    const [checked, setChecked] = useState(false);
    const [allowed, setAllowed] = useState(false);
    const [tab, setTab] = useState<AdminTab>('invites');

    useEffect(() => {
        (async () => {
            const { data } = await supabase.auth.getSession();
            const email = data.session?.user?.email?.toLowerCase() ?? null;
            if (email !== ADMIN_EMAIL) {
                router.replace('/');
                return;
            }
            setAllowed(true);
            setChecked(true);
        })();
    }, [router]);

    if (!checked || !allowed) {
        return (
            <div style={{ padding: 48, color: '#64748B', fontSize: 14 }}>
                Checking access…
            </div>
        );
    }

    return (
        <div style={{ maxWidth: 1160, margin: '0 auto', padding: '32px 24px', display: 'flex', flexDirection: 'column', gap: 24 }}>
            <header>
                <h1 style={{ margin: 0, fontSize: 24, fontWeight: 800, color: '#0F172A' }}>Admin</h1>
                <p style={{ margin: '6px 0 0', color: '#64748B', fontSize: 14 }}>
                    Manage beta invites, review tester feedback, and view onboarding responses. Admin-only.
                </p>
            </header>

            <div style={{ display: 'flex', gap: 8, borderBottom: '1px solid #E2E8F0', paddingBottom: 0 }}>
                {([
                    { id: 'invites' as const, label: 'Invites' },
                    { id: 'feedback' as const, label: 'Feedback' },
                    { id: 'onboarding' as const, label: 'Onboarding' },
                ]).map(({ id, label }) => (
                    <button
                        key={id}
                        type="button"
                        onClick={() => setTab(id)}
                        style={{
                            padding: '10px 16px',
                            marginBottom: -1,
                            border: 'none',
                            borderBottom: tab === id ? `2px solid ${PRIMARY}` : '2px solid transparent',
                            background: 'transparent',
                            color: tab === id ? PRIMARY : '#64748B',
                            fontSize: 14,
                            fontWeight: 700,
                            cursor: 'pointer',
                        }}
                    >
                        {label}
                    </button>
                ))}
            </div>

            {tab === 'invites' && <InvitesTab />}
            {tab === 'feedback' && <FeedbackTab />}
            {tab === 'onboarding' && <OnboardingTab />}
        </div>
    );
}
