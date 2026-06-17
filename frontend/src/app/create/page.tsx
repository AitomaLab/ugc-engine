'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { apiFetch, slugifyName } from '@/lib/utils';
import { launchCreativeOsProject } from '@/lib/launchCreativeOsProject';
import type { AgentRef } from '@/lib/creative-os-api';
import { useTranslation } from '@/lib/i18n';

function buildBrief(template: string, vars: Record<string, string>): string {
    return Object.entries(vars).reduce(
        (s, [k, v]) => s.replace(new RegExp(`\\{${k}\\}`, 'g'), v),
        template,
    );
}

function CreateLauncher() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const { t } = useTranslation();
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;

        const run = async () => {
            const qs = searchParams.toString();
            if (!qs) {
                router.replace('/');
                return;
            }

            try {
                const influencerId = searchParams.get('influencer_id');
                const productId = searchParams.get('product_id');
                const scriptId = searchParams.get('script_id');
                const customScript = searchParams.get('customScript');

                if (influencerId) {
                    const influencers = await apiFetch<Array<{ id: string; name: string; image_url?: string }>>('/influencers');
                    const inf = (influencers || []).find((i) => i.id === influencerId);
                    if (!inf) throw new Error('Influencer not found');
                    const tag = slugifyName(inf.name);
                    const brief = buildBrief(t('influencers.useVideoPrompt'), { name: tag });
                    const refs: AgentRef[] = [{
                        type: 'influencer',
                        tag,
                        name: inf.name,
                        id: inf.id,
                        image_url: inf.image_url,
                    }];
                    await launchCreativeOsProject(router, { brief, refs });
                    return;
                }

                if (productId) {
                    const products = await apiFetch<Array<{ id: string; name: string; image_url?: string; type?: string }>>('/api/products');
                    const product = (products || []).find((p) => p.id === productId);
                    if (!product) throw new Error('Product not found');
                    const tag = slugifyName(product.name);
                    const brief = buildBrief(t('products.useVideoPrompt'), { name: tag });
                    const refs: AgentRef[] = [{
                        type: 'product',
                        tag,
                        name: product.name,
                        id: product.id,
                        image_url: product.image_url,
                        product_type: product.type === 'digital' ? 'digital' : 'physical',
                    }];
                    await launchCreativeOsProject(router, { brief, refs });
                    return;
                }

                if (scriptId) {
                    const scripts = await apiFetch<Array<{ id: string; name?: string; text?: string; script_json?: { hook?: string; scenes?: { dialogue?: string }[] } }>>('/api/scripts');
                    const script = (scripts || []).find((s) => s.id === scriptId);
                    apiFetch(`/api/scripts/${scriptId}/use`, { method: 'POST' }).catch(() => {});
                    const hook = script?.script_json?.hook || script?.text?.split('|||')[0]?.trim() || script?.name || '';
                    const dialogue = (script?.script_json?.scenes || [])
                        .map((sc) => sc.dialogue)
                        .filter(Boolean)
                        .join(' ');
                    const scriptText = [hook, dialogue].filter(Boolean).join('. ').trim();
                    const brief = buildBrief(t('scripts.useVideoPrompt'), { script: scriptText || 'script' });
                    await launchCreativeOsProject(router, { brief });
                    return;
                }

                if (customScript) {
                    const brief = `create a video inspired by this template:\n\n${customScript}`.slice(0, 4000);
                    await launchCreativeOsProject(router, { brief });
                    return;
                }

                router.replace('/');
            } catch (e) {
                if (!cancelled) {
                    setError(e instanceof Error ? e.message : 'Failed to start project');
                }
            }
        };

        run();
        return () => { cancelled = true; };
    }, [router, searchParams, t]);

    return (
        <div className="empty-state" style={{ minHeight: '40vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
            {error ? (
                <>
                    <div className="empty-title">{error}</div>
                    <button type="button" className="btn-primary" style={{ marginTop: '12px' }} onClick={() => router.push('/')}>
                        Go to Studio
                    </button>
                </>
            ) : (
                <div className="empty-title">Starting your project…</div>
            )}
        </div>
    );
}

export default function CreatePage() {
    return (
        <Suspense fallback={<div className="empty-state"><div className="empty-title">Loading…</div></div>}>
            <CreateLauncher />
        </Suspense>
    );
}
