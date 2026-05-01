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
        `Generate a cinematic product shot of @${product} with dramatic lighting`,
        `Make a UGC video of @${influencer} unboxing @${product} and reacting with genuine excitement`,
    ];
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
                    apiFetch<RealInfluencer[]>('/influencers', { skipProjectScope: true }).catch(() => []),
                ]);
                if (cancelled) return;
                // Fall back to template products when user has none
                const finalProducts = (prods || []).length > 0 ? (prods || []).slice(0, 3) : TEMPLATE_PRODUCTS;
                setProducts(finalProducts);
                setInfluencers((infs || []).slice(0, 3));
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
        onComplete({
            productId: product.id,
            productName: product.name,
            productImageUrl: getProductImage(product),
            influencerId: influencer.id,
            influencerName: influencer.name,
            influencerImageUrl: getInfluencerImage(influencer),
            prompt: `${selectedPrompt} [9:16 vertical] [5s clip duration] [ONBOARDING_FIRST_VIDEO — this is the user's welcome video, it must be FREE (0 credits). Use the product image_url as a reference_image in Seedance so the product is visible in the video.]`,
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

                                {/* ── Selected product chip + change link ── */}
                                {selectedProduct && (
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

                                {/* ── Selected influencer chip + change link ── */}
                                {selectedInfluencer && (
                                    <div style={{
                                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                        padding: '8px 14px', borderRadius: '10px',
                                        background: 'rgba(51,122,255,0.06)', border: '1px solid rgba(51,122,255,0.15)',
                                        marginBottom: '16px',
                                    }}>
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                            {influencer && getInfluencerImage(influencer) && (
                                                <img src={getInfluencerImage(influencer)!} alt="" style={{ width: '28px', height: '28px', borderRadius: '50%', objectFit: 'cover' }} />
                                            )}
                                            <span style={{ fontSize: '13px', fontWeight: 700, color: '#0D1B3E' }}>{influencer?.name}</span>
                                        </div>
                                        <button
                                            onClick={() => { setSelectedInfluencer(''); setSelectedPrompt(''); }}
                                            style={{ background: 'none', border: 'none', color: '#337AFF', fontSize: '12px', fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}
                                        >
                                            Change
                                        </button>
                                    </div>
                                )}

                                {/* ── Prompt suggestions (after both selected) ── */}
                                {prompts.length > 0 && selectedProduct && selectedInfluencer && (
                                    <>
                                        <div style={{ fontSize: '12px', fontWeight: 700, color: '#8A93B0', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                                            {t('onboarding.suggestedPrompts')}
                                        </div>
                                        <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginBottom: '16px' }}>
                                            {prompts.map((p, i) => (
                                                <button
                                                    key={i}
                                                    onClick={() => setSelectedPrompt(p)}
                                                    style={{
                                                        padding: '10px 14px',
                                                        borderRadius: '10px',
                                                        border: selectedPrompt === p ? '2px solid #337AFF' : '1px solid rgba(0,0,0,0.08)',
                                                        background: selectedPrompt === p ? 'rgba(51,122,255,0.04)' : 'white',
                                                        cursor: 'pointer',
                                                        textAlign: 'left',
                                                        fontSize: '12px',
                                                        color: '#0D1B3E',
                                                        lineHeight: 1.4,
                                                        transition: 'all 0.15s',
                                                        fontFamily: 'inherit',
                                                    }}
                                                >
                                                    {p}
                                                </button>
                                            ))}
                                        </div>
                                    </>
                                )}
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
            {/* Modal */}
            <div style={{
                position: 'fixed',
                top: '50%', left: '50%',
                transform: 'translate(-50%, -50%)',
                width: '640px',
                maxWidth: '92vw',
                maxHeight: '90vh',
                overflowY: 'auto',
                background: 'white',
                borderRadius: '20px',
                boxShadow: '0 32px 80px rgba(0,0,0,0.25)',
                zIndex: 9999,
                animation: 'onboardingScaleIn 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
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
            <style>{`
                @keyframes onboardingScaleIn {
                    from { opacity: 0; transform: translate(-50%, -50%) scale(0.95); }
                    to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
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
