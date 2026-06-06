'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from '@/lib/i18n';
import { apiFetch } from '@/lib/utils';
import { creativeFetch } from '@/lib/creative-os-api';

/* ── Types ────────────────────────────────────────────────────── */

interface RealProduct {
    id: string;
    name: string;
    description?: string;
    image_url?: string;
    product_image?: string;
}

interface RealInfluencer {
    id: string;
    name: string;
    description?: string;
    profile_image_url?: string;
    image_url?: string;
    thumbnail_url?: string;
}

/* ── Hardcoded showcase videos ─────────────────────────────────── */
const SHOWCASE_VIDEOS = [
    { label: 'UGC Videos', url: 'https://res.cloudinary.com/ducrze2ys/video/upload/v1777294804/MariaVideo_avxpjt.mp4' },
    { label: 'Cinematic Ads', url: 'https://res.cloudinary.com/ducrze2ys/video/upload/v1777322746/Poppi_-_Product_puarix.mov' },
    { label: 'Ad Creatives', url: 'https://res.cloudinary.com/ducrze2ys/video/upload/v1777294720/KaiVideo_ssbyz8.mp4' },
];

/* ── Template products for new users without any products ───── */
const TEMPLATE_PRODUCTS: RealProduct[] = [
    {
        id: '434540e2-2b00-49fa-8749-3bd3e6f71ff3',
        name: 'Protein',
        image_url: 'https://kzvdfponrzwfwdbkpfjf.supabase.co/storage/v1/object/public/product-images/35c48749-25d5-462d-9503-c1e275f2c417.png',
    },
    {
        id: 'fd752583-4988-48ed-84e1-c371b7b6cc05',
        name: 'Skincare',
        image_url: 'https://kzvdfponrzwfwdbkpfjf.supabase.co/storage/v1/object/public/product-images/f7979a91-f483-42c3-9c6c-aec8013f6021.png',
    },
    {
        id: 'd377775e-afac-4af4-a133-dcb64babf739',
        name: 'Apple Headphones',
        image_url: 'https://kzvdfponrzwfwdbkpfjf.supabase.co/storage/v1/object/public/product-images/8130031c-5b67-43d0-8558-3e516656309d.png',
    },
];

/* ── Helpers ───────────────────────────────────────────────────── */

function getInfluencerImage(inf: RealInfluencer): string | null {
    return inf.profile_image_url || inf.image_url || inf.thumbnail_url || null;
}

function getProductImage(p: RealProduct): string | null {
    return p.image_url || p.product_image || null;
}

function getSuggestedPrompts(product: string, influencer: string): string[] {
    return [
        `Create a UGC ad with @${influencer} showing @${product} and explaining why it's a must-have this summer`,
        `Generate 3 image ads of @${influencer} holding @${product} in different scenarios`,
        `Create an eye-grabbing cinematic ad of @${product}`,
    ];
}

/* ── @-mention pill (mirrors chat styling) ──────────────────────────── */

function MentionPill({ image, name }: { image?: string | null; name: string }) {
    return (
        <span style={{
            display: 'inline-flex', alignItems: 'center', gap: '4px',
            padding: '2px 8px 2px 2px', borderRadius: '6px',
            background: 'rgba(51,122,255,0.08)', border: '1px solid rgba(51,122,255,0.15)',
            verticalAlign: 'baseline',
        }}>
            {image && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={image} alt="" style={{ width: '18px', height: '18px', borderRadius: '4px', objectFit: 'cover', flexShrink: 0 }} />
            )}
            <span style={{ fontSize: '12px', fontWeight: 600, color: '#337AFF', maxWidth: '120px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{name}</span>
        </span>
    );
}

/** Parse "@<name>" tokens in a prompt and render matches as MentionPill.
 *  Matching is case-insensitive against the product + influencer names. */
function renderPromptWithPills(
    prompt: string,
    refs: { name: string; image: string | null }[],
): React.ReactNode {
    if (!prompt) return prompt;
    // Match against the literal @<name> strings (longest first so multi-word
    // names like "@Apple Headphones" win over a partial "@Apple" match).
    const tokens = refs
        .map(r => ({ ...r, token: `@${r.name}` }))
        .sort((a, b) => b.token.length - a.token.length);
    if (!tokens.length) return prompt;
    const nodes: React.ReactNode[] = [];
    let remaining = prompt;
    let key = 0;
    while (remaining.length) {
        // Find the earliest token occurrence in the remaining string.
        let bestIdx = -1;
        let bestTok: typeof tokens[number] | null = null;
        for (const t of tokens) {
            const idx = remaining.toLowerCase().indexOf(t.token.toLowerCase());
            if (idx !== -1 && (bestIdx === -1 || idx < bestIdx)) {
                bestIdx = idx;
                bestTok = t;
            }
        }
        if (!bestTok || bestIdx === -1) {
            nodes.push(<span key={key++}>{remaining}</span>);
            break;
        }
        if (bestIdx > 0) nodes.push(<span key={key++}>{remaining.slice(0, bestIdx)}</span>);
        nodes.push(<MentionPill key={key++} image={bestTok.image || undefined} name={bestTok.name} />);
        remaining = remaining.slice(bestIdx + bestTok.token.length);
    }
    return nodes;
}

/* ── 9:16 image card with hover-revealed edit icon (top-right) ─────── */

function HoverEditableCard({ imageUrl, onEdit, title }: { imageUrl: string | null; onEdit: () => void; title: string }) {
    const [hovered, setHovered] = useState(false);
    return (
        <div
            onMouseEnter={() => setHovered(true)}
            onMouseLeave={() => setHovered(false)}
            style={{
                position: 'relative',
                height: 'min(360px, 42vh)',
                aspectRatio: '9 / 16',
                borderRadius: '18px',
                overflow: 'hidden',
                background: '#F4F6FA',
                border: '1px solid rgba(0,0,0,0.06)',
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                transform: hovered ? 'scale(1.01)' : 'none',
                boxShadow: hovered ? '0 8px 24px rgba(0,0,0,0.12)' : 'none',
            }}
        >
            {imageUrl && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={imageUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            )}
            <button
                onClick={onEdit}
                title={title}
                style={{
                    position: 'absolute',
                    top: '10px',
                    right: '10px',
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    background: 'rgba(255,255,255,0.95)',
                    border: '1px solid rgba(0,0,0,0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    cursor: 'pointer',
                    boxShadow: '0 2px 6px rgba(0,0,0,0.15)',
                    padding: 0,
                    opacity: hovered ? 1 : 0,
                    transform: hovered ? 'scale(1)' : 'scale(0.85)',
                    transition: 'opacity 0.18s ease, transform 0.18s ease',
                    pointerEvents: hovered ? 'auto' : 'none',
                }}
            >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#0D1B3E" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
                    <path d="M18.5 2.5a2.121 2.121 0 1 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
                </svg>
            </button>
        </div>
    );
}

/* ── Component ────────────────────────────────────────────────── */

interface OnboardingModalProps {
    onComplete: (params: {
        productId: string;
        productName: string;
        productImageUrl: string | null;
        influencerId: string;
        influencerName: string;
        influencerImageUrl: string | null;
        prompt: string;
    }) => void;
    onSkip: () => void;
}

export function OnboardingModal({ onComplete, onSkip }: OnboardingModalProps) {
    const { t } = useTranslation();
    const [step, setStep] = useState(0);
    const [selectedProduct, setSelectedProduct] = useState('');
    const [selectedInfluencer, setSelectedInfluencer] = useState('');
    const [selectedPrompt, setSelectedPrompt] = useState('');

    // Real data from DB
    const [products, setProducts] = useState<RealProduct[]>([]);
    const [influencers, setInfluencers] = useState<RealInfluencer[]>([]);
    const [loading, setLoading] = useState(true);

    // Fetch real products & influencers on mount
    useEffect(() => {
        let cancelled = false;
        const load = async () => {
            try {
                const [prods, infs] = await Promise.all([
                    apiFetch<RealProduct[]>('/api/products', { skipProjectScope: true }).catch(() => []),
                    // Do NOT skip project scope here — the project-scoped influencer
                    // endpoint triggers the auto-seed in list_influencers_scoped
                    // (db_manager.py) which clones the 18 template influencers
                    // (Mateo, Lexi, Amelie, …) into the user's default project on
                    // first read. The skip-scope branch in main.py doesn't
                    // auto-seed, which is why brand-new users saw an empty list.
                    apiFetch<RealInfluencer[]>('/influencers').catch(() => []),
                ]);
                if (cancelled) return;
                // Fall back to template products when user has none
                const finalProducts = (prods || []).length > 0 ? (prods || []).slice(0, 3) : TEMPLATE_PRODUCTS;
                setProducts(finalProducts);

                // Pick the curated template trio for first-time users. If the
                // user has built up their own roster, fall back to the first
                // three of theirs (mirrors the prior behavior).
                const TEMPLATE_NAMES = ['Mateo', 'Lexi', 'Amelie'];
                const all = infs || [];
                const templates = TEMPLATE_NAMES
                    .map(n => all.find(i => (i.name || '').toLowerCase() === n.toLowerCase()))
                    .filter((i): i is RealInfluencer => !!i);
                setInfluencers(templates.length > 0 ? templates : all.slice(0, 3));
            } catch (err) {
                console.warn('Onboarding data load failed:', err);
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        load();
        return () => { cancelled = true; };
    }, []);

    const product = products.find(p => p.id === selectedProduct);
    const influencer = influencers.find(i => i.id === selectedInfluencer);
    const prompts = product && influencer ? getSuggestedPrompts(product.name, influencer.name) : [];

    const handleCreate = () => {
        if (!product || !influencer || !selectedPrompt) return;
        const productImageUrl = getProductImage(product);
        const influencerImageUrl = getInfluencerImage(influencer);
        // Prompt #2 (3 image ads) uses template products whose UUIDs may not
        // exist in the user's DB → backend 404s on product_id lookup. Tell the
        // agent to use reference_image_urls instead so the pipeline takes the
        // upload-only branch which works without a DB row.
        const isImageAdsPrompt = selectedPrompt.toLowerCase().includes('image ads');
        const refImageHint = isImageAdsPrompt
            ? ` [USE reference_image_urls (NOT product_id) when calling generate_image. URLs to pass: ${[productImageUrl, influencerImageUrl].filter(Boolean).join(' AND ')}. The pipeline takes the upload-only branch and renders 3 composites from these two images.]`
            : '';
        onComplete({
            productId: product.id,
            productName: product.name,
            productImageUrl,
            influencerId: influencer.id,
            influencerName: influencer.name,
            influencerImageUrl,
            prompt: `${selectedPrompt} [9:16 vertical] [5s clip duration] [SCRIPT LENGTH: hook/dialogue MUST be ≤12 words total — anything longer cannot be spoken in 5 seconds.] [PRODUCT INTERACTION: if the product has a cap, lid, seal, or wrapper (bottle, jar, tube, can, pouch), the character MUST visibly open/unscrew/remove it BEFORE drinking, eating, or using — never drink through a closed cap or use a sealed product. No impossible interactions, no hallucinations.] [ONBOARDING_FIRST_VIDEO — this is the user's welcome video, it must be FREE (0 credits). Use the product image_url as a reference_image in Seedance so the product is visible in the video.]${refImageHint}`,
        });
    };

    const renderStep = () => {
        switch (step) {
            /* ── Step 1: Welcome ── */
            case 0:
                return (
                    <div style={{ textAlign: 'center', padding: '40px 30px' }}>
                        {/* Real Studio Logo — large & visible */}
                        <div style={{
                            margin: '0 auto 28px',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                        }}>
                            <img
                                src="/StudioLogo_Black.svg"
                                alt="Aitoma Studio"
                                style={{ width: '180px', height: 'auto', objectFit: 'contain' }}
                            />
                        </div>
                        <h2 style={{ fontSize: '24px', fontWeight: 800, color: '#0D1B3E', margin: '0 0 12px', lineHeight: 1.2 }}>
                            {t('onboarding.welcomeTitle')}
                        </h2>
                        <p style={{ fontSize: '15px', color: '#5A6178', margin: '0 0 20px', lineHeight: 1.6 }}>
                            {t('onboarding.welcomeSubtitle')}
                        </p>
                        {/* Credits badge — blue theme */}
                        <div style={{
                            display: 'inline-flex', alignItems: 'center', gap: '8px',
                            padding: '10px 20px', borderRadius: '999px',
                            background: 'rgba(51,122,255,0.08)', color: '#337AFF',
                            fontSize: '14px', fontWeight: 700,
                            border: '1px solid rgba(51,122,255,0.15)',
                        }}>
                            <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: '#337AFF', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                                <rect x="3" y="8" width="18" height="13" rx="2" />
                                <path d="M12 8v13" />
                                <path d="M3 13h18" />
                                <path d="M7.5 8C7.5 8 7 3 12 3s4.5 5 4.5 5" />
                            </svg>
                            {t('onboarding.freeCredits')}
                        </div>
                        <div style={{ marginTop: '32px' }}>
                            <button onClick={() => setStep(1)} style={primaryBtnStyle}>
                                {t('onboarding.getStarted')}
                            </button>
                        </div>
                    </div>
                );

            /* ── Step 2: Capabilities with 9:16 video previews ── */
            case 1:
                return (
                    <div style={{ padding: '30px' }}>
                        <h3 style={{ fontSize: '20px', fontWeight: 800, color: '#0D1B3E', margin: '0 0 6px', textAlign: 'center' }}>
                            {t('onboarding.capabilitiesTitle')}
                        </h3>
                        <p style={{ fontSize: '14px', color: '#6b7280', margin: '0 0 20px', textAlign: 'center', lineHeight: 1.4 }}>
                            {t('onboarding.capabilitiesSubtitle')}
                        </p>
                        <div style={{ display: 'flex', gap: '12px', justifyContent: 'center' }}>
                            {SHOWCASE_VIDEOS.map((sv, i) => (
                                <ShowcaseVideoCard key={i} url={sv.url} label={sv.label} />
                            ))}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '24px' }}>
                            <button onClick={() => setStep(0)} style={secondaryBtnStyle}>{t('onboarding.back')}</button>
                            <button onClick={() => setStep(2)} style={primaryBtnStyle}>{t('onboarding.next')}</button>
                        </div>
                    </div>
                );

            /* ── Step 3: How Agent Works ── */
            case 2:
                return (
                    <div style={{ padding: '30px' }}>
                        <h3 style={{ fontSize: '20px', fontWeight: 800, color: '#0D1B3E', margin: '0 0 12px', textAlign: 'center' }}>
                            {t('onboarding.agentTitle')}
                        </h3>
                        <p style={{ fontSize: '14px', color: '#5A6178', textAlign: 'center', margin: '0 0 20px', lineHeight: 1.6 }}>
                            {t('onboarding.agentDesc')}
                        </p>
                        <div style={{
                            borderRadius: '12px',
                            overflow: 'hidden',
                            border: '1px solid rgba(0,0,0,0.08)',
                            marginBottom: '12px',
                            width: '70%',
                            maxWidth: '70%',
                            marginLeft: 'auto',
                            marginRight: 'auto',
                        }}>
                            <video
                                src="https://res.cloudinary.com/ducrze2ys/video/upload/v1777570469/StudioRecording_final_edxjzf.mp4"
                                muted
                                autoPlay
                                loop
                                playsInline
                                preload="auto"
                                style={{
                                    width: '100%',
                                    display: 'block',
                                    borderRadius: '12px',
                                }}
                            />
                        </div>
                        <div style={{
                            fontSize: '12px', color: '#8A93B0', textAlign: 'center',
                            background: 'rgba(0,0,0,0.03)', padding: '8px 12px', borderRadius: '8px',
                        }}>
                            {t('onboarding.agentHint')}
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '24px' }}>
                            <button onClick={() => setStep(1)} style={secondaryBtnStyle}>{t('onboarding.back')}</button>
                            <button onClick={() => setStep(3)} style={primaryBtnStyle}>{t('onboarding.next')}</button>
                        </div>
                    </div>
                );

            /* ── Step 4: Pick Product + Influencer (sequential reveal) ── */
            case 3:
                return (
                    <div style={{ padding: '24px 30px' }}>
                        <h3 style={{ fontSize: '20px', fontWeight: 800, color: '#0D1B3E', margin: '0 0 16px', textAlign: 'center' }}>
                            {t('onboarding.pickTitle')}
                        </h3>

                        {loading ? (
                            <div style={{ textAlign: 'center', padding: '40px 0', color: '#8A93B0', fontSize: '13px' }}>
                                Loading...
                            </div>
                        ) : (
                            <>
                                {/* ── Products (always visible) ── */}
                                {!selectedProduct && (
                                    <>
                                        <div style={{ fontSize: '12px', fontWeight: 700, color: '#8A93B0', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                                            {t('onboarding.pickProduct')}
                                        </div>
                                        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                                            {products.map(p => (
                                                <PickerCard
                                                    key={p.id}
                                                    selected={selectedProduct === p.id}
                                                    onClick={() => setSelectedProduct(p.id)}
                                                    imageUrl={getProductImage(p)}
                                                    name={p.name}
                                                />
                                            ))}
                                        </div>
                                    </>
                                )}

                                {/* ── Selected product chip (only while picking influencer) ── */}
                                {selectedProduct && !selectedInfluencer && (
                                    <div style={{
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                        padding: '8px 14px', borderRadius: '10px',
                                        background: 'rgba(51,122,255,0.06)', border: '1px solid rgba(51,122,255,0.15)',
                                        marginBottom: '16px',
                                    }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            {product && getProductImage(product) && (
                                                <img src={getProductImage(product)!} alt="" style={{ width: '28px', height: '28px', borderRadius: '6px', objectFit: 'cover' }} />
                                            )}
                                            <span style={{ fontSize: '13px', fontWeight: 700, color: '#0D1B3E' }}>{product?.name}</span>
                                        </div>
                                        <button
                                            onClick={() => { setSelectedProduct(''); setSelectedInfluencer(''); setSelectedPrompt(''); }}
                                            style={{ background: 'none', border: 'none', color: '#337AFF', fontSize: '12px', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
                                        >
                                            Change
                                        </button>
                                    </div>
                                )}

                                {/* ── Influencers (after product selected) ── */}
                                {selectedProduct && !selectedInfluencer && (
                                    <>
                                        <div style={{ fontSize: '12px', fontWeight: 700, color: '#8A93B0', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                                            {t('onboarding.pickInfluencer')}
                                        </div>
                                        <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
                                            {influencers.map(inf => (
                                                <PickerCard
                                                    key={inf.id}
                                                    selected={selectedInfluencer === inf.id}
                                                    onClick={() => setSelectedInfluencer(inf.id)}
                                                    imageUrl={getInfluencerImage(inf)}
                                                    name={inf.name}
                                                />
                                            ))}
                                        </div>
                                    </>
                                )}

                                {/* ── Two-column layout when both are selected:
                                    LEFT = product + influencer as 9:16 cards
                                    RIGHT = prompt suggestions ── */}
                                {selectedProduct && selectedInfluencer && (() => {
                                    const promptRefs = [
                                        product ? { name: product.name, image: getProductImage(product) } : null,
                                        influencer ? { name: influencer.name, image: getInfluencerImage(influencer) } : null,
                                    ].filter(Boolean) as { name: string; image: string | null }[];

                                    return (
                                        <div style={{ display: 'flex', gap: '20px', marginBottom: '16px', alignItems: 'flex-start' }}>
                                            {/* LEFT column — two 9:16 cards, ~202×360 each. Edit icon shows on hover, top-right. */}
                                            <div style={{ display: 'flex', flexDirection: 'row', gap: '8px' }}>
                                                <HoverEditableCard
                                                    imageUrl={product ? getProductImage(product) : null}
                                                    onEdit={() => { setSelectedProduct(''); setSelectedInfluencer(''); setSelectedPrompt(''); }}
                                                    title="Change product"
                                                />
                                                <HoverEditableCard
                                                    imageUrl={influencer ? getInfluencerImage(influencer) : null}
                                                    onEdit={() => { setSelectedInfluencer(''); setSelectedPrompt(''); }}
                                                    title="Change influencer"
                                                />
                                            </div>

                                            {/* RIGHT column — prompts; column stretches to match
                                                the height of the 9:16 cards on the left so the
                                                whole row reads as one balanced block. */}
                                            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', height: 'min(360px, 42vh)' }}>
                                                <div style={{ fontSize: '12px', fontWeight: 700, color: '#8A93B0', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '20px' }}>
                                                    {t('onboarding.suggestedPrompts')}
                                                </div>
                                                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', flex: 1, justifyContent: 'flex-start' }}>
                                                    {prompts.map((p, i) => (
                                                        <button
                                                            key={i}
                                                            onClick={() => setSelectedPrompt(p)}
                                                            style={{
                                                                padding: '16px 18px',
                                                                borderRadius: '10px',
                                                                border: selectedPrompt === p ? '2px solid #337AFF' : '1px solid rgba(0,0,0,0.08)',
                                                                background: selectedPrompt === p ? 'rgba(51,122,255,0.08)' : 'rgba(51,122,255,0.025)',
                                                                cursor: 'pointer',
                                                                textAlign: 'left',
                                                                fontSize: '13px',
                                                                color: '#0D1B3E',
                                                                lineHeight: 1.6,
                                                                transition: 'all 0.15s',
                                                                fontFamily: 'inherit',
                                                                minHeight: 'min(88px, 10vh)',
                                                                display: 'flex',
                                                                alignItems: 'center',
                                                            }}
                                                        >
                                                            <span>{renderPromptWithPills(p, promptRefs)}</span>
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })()}
                            </>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <button onClick={() => setStep(2)} style={secondaryBtnStyle}>{t('onboarding.back')}</button>
                            <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
                                <button
                                    onClick={handleCreate}
                                    disabled={!selectedProduct || !selectedInfluencer || !selectedPrompt}
                                    style={{
                                        ...primaryBtnStyle,
                                        opacity: (!selectedProduct || !selectedInfluencer || !selectedPrompt) ? 0.5 : 1,
                                        cursor: (!selectedProduct || !selectedInfluencer || !selectedPrompt) ? 'not-allowed' : 'pointer',
                                    }}
                                >
                                    {t('onboarding.createFirst')}
                                </button>
                            </div>
                        </div>
                    </div>
                );

            default: return null;
        }
    };

    return (
        <>
            {/* Backdrop */}
            <div style={{
                position: 'fixed', inset: 0,
                background: 'rgba(0,0,0,0.5)',
                backdropFilter: 'blur(8px)',
                zIndex: 9998,
            }} />
            {/* Modal — content drives the size; 4% padding gutter on all sides via
                an outer flex viewport wrapper, then the modal sits inside it at
                content-natural width/height (capped by the wrapper). */}
            <div style={{
                position: 'fixed', inset: 0,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: '4vh 4vw',
                pointerEvents: 'none',
                zIndex: 9999,
            }}>
                <div style={{
                    width: 'auto',
                    maxWidth: 'min(900px, 100%)',
                    maxHeight: '100%',
                    overflowY: 'auto',
                    background: 'white',
                    borderRadius: '20px',
                    boxShadow: '0 32px 80px rgba(0,0,0,0.25)',
                    animation: 'onboardingScaleIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    pointerEvents: 'auto',
                    display: 'flex',
                    flexDirection: 'column',
                }}>
                    {/* Step indicator */}
                    <div style={{
                        display: 'flex', gap: '4px', justifyContent: 'center',
                        padding: '16px 0 0',
                    }}>
                        {[0, 1, 2, 3].map(i => (
                            <div key={i} style={{
                                width: step === i ? '24px' : '8px',
                                height: '4px',
                                borderRadius: '2px',
                                background: step === i ? '#337AFF' : 'rgba(0,0,0,0.1)',
                                transition: 'all 0.3s',
                            }} />
                        ))}
                    </div>
                    {renderStep()}
                </div>
            </div>
            <style>{`
                @keyframes onboardingScaleIn {
                    from { opacity: 0; transform: scale(0.95); }
                    to { opacity: 1; transform: scale(1); }
                }
            `}</style>
        </>
    );
}

/* ── Shared styles ─────────────────────────────────────────────── */

const primaryBtnStyle: React.CSSProperties = {
    padding: '12px 28px',
    borderRadius: '12px',
    border: 'none',
    background: 'linear-gradient(135deg, #337AFF, #6C5CE7)',
    color: 'white',
    fontSize: '14px',
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.2s',
    boxShadow: '0 4px 16px rgba(51,122,255,0.25)',
    fontFamily: 'inherit',
};

const secondaryBtnStyle: React.CSSProperties = {
    padding: '8px 16px',
    borderRadius: '10px',
    border: 'none',
    background: 'transparent',
    color: '#8A93B0',
    fontSize: '13px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
};

/* ── Sub-components ────────────────────────────────────────────── */

function PickerCard({ selected, onClick, imageUrl, name }: {
    selected: boolean; onClick: () => void; imageUrl: string | null; name: string;
}) {
    return (
        <button
            onClick={onClick}
            style={{
                flex: 1,
                padding: 0,
                borderRadius: '12px',
                border: selected ? '2px solid #337AFF' : '1px solid rgba(0,0,0,0.08)',
                background: selected ? 'rgba(51,122,255,0.04)' : '#f0f0f5',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.2s',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                overflow: 'hidden',
                fontFamily: 'inherit',
                position: 'relative',
            }}
        >
            {/* 9:16 portrait image */}
            {imageUrl ? (
                <img
                    src={imageUrl}
                    alt={name}
                    style={{
                        width: '100%',
                        aspectRatio: '9 / 16',
                        objectFit: 'cover',
                        display: 'block',
                    }}
                />
            ) : (
                <div style={{
                    width: '100%',
                    aspectRatio: '9 / 16',
                    background: 'linear-gradient(135deg, #337AFF, #6C5CE7)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    color: 'white', fontSize: '24px', fontWeight: 700,
                }}>
                    {name.charAt(0).toUpperCase()}
                </div>
            )}
            {/* Name overlay */}
            <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                padding: '20px 6px 8px',
                background: 'linear-gradient(transparent, rgba(0,0,0,0.65))',
            }}>
                <span style={{ fontSize: '12px', fontWeight: 700, color: 'white' }}>{name}</span>
            </div>
        </button>
    );
}

function ShowcaseVideoCard({ url, label }: { url: string; label: string }) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const [muted, setMuted] = useState(true);

    const toggleMute = () => {
        const v = videoRef.current;
        if (!v) return;
        v.muted = !v.muted;
        setMuted(v.muted);
    };

    return (
        <div style={{
            flex: '0 0 160px',
            borderRadius: '14px',
            overflow: 'hidden',
            border: '1px solid rgba(0,0,0,0.08)',
            position: 'relative',
        }}>
            <video
                ref={videoRef}
                src={url}
                muted
                autoPlay
                loop
                playsInline
                preload="auto"
                style={{
                    width: '160px', height: '284px',
                    objectFit: 'cover',
                    display: 'block',
                }}
            />
            {/* Sound toggle */}
            <button
                onClick={toggleMute}
                style={{
                    position: 'absolute', top: '8px', right: '8px',
                    width: '28px', height: '28px',
                    borderRadius: '50%',
                    border: 'none',
                    background: 'rgba(0,0,0,0.45)',
                    backdropFilter: 'blur(4px)',
                    cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    padding: 0,
                    transition: 'background 0.15s',
                }}
            >
                {muted ? (
                    <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'white', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                        <polygon points="11,5 6,9 2,9 2,15 6,15 11,19" />
                        <line x1="23" y1="9" x2="17" y2="15" />
                        <line x1="17" y1="9" x2="23" y2="15" />
                    </svg>
                ) : (
                    <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'white', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                        <polygon points="11,5 6,9 2,9 2,15 6,15 11,19" />
                        <path d="M15.54 8.46a5 5 0 0 1 0 7.07" />
                        <path d="M19.07 4.93a10 10 0 0 1 0 14.14" />
                    </svg>
                )}
            </button>
            {/* Label overlay */}
            <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                padding: '24px 10px 10px',
                background: 'linear-gradient(transparent, rgba(0,0,0,0.7))',
            }}>
                <div style={{ fontSize: '12px', fontWeight: 700, color: 'white' }}>{label}</div>
            </div>
        </div>
    );
}
