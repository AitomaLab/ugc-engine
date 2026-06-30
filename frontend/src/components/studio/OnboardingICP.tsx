'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useTranslation } from '@/lib/i18n';

export interface ICPAnswers {
    role: string;
    team_size: string;
    challenge: string;
    content_type: string;
    monthly_volume: string;
}

interface OnboardingICPProps {
    userId: string;
    onComplete: (answers: ICPAnswers) => void;
}

type ICPQuestionId = keyof ICPAnswers;

interface ICPOption {
    labelEn: string;
    labelEs: string;
    value: string;
}

interface ICPQuestion {
    id: ICPQuestionId;
    questionEn: string;
    questionEs: string;
    options: ICPOption[];
}

const ICP_QUESTIONS: ICPQuestion[] = [
    {
        id: 'role',
        questionEn: 'What best describes you?',
        questionEs: '¿Cuál es tu rol principal?',
        options: [
            { labelEn: 'Brand Owner', labelEs: 'Dueño de marca', value: 'Brand Owner' },
            { labelEn: 'Marketing Manager', labelEs: 'Director de marketing', value: 'Marketing Manager' },
            { labelEn: 'Media Buyer', labelEs: 'Comprador de medios', value: 'Media Buyer' },
            { labelEn: 'Agency', labelEs: 'Agencia', value: 'Agency' },
            { labelEn: 'Content Creator', labelEs: 'Creador de contenido', value: 'Content Creator' },
            { labelEn: 'Other', labelEs: 'Otro', value: 'Other' },
        ],
    },
    {
        id: 'team_size',
        questionEn: 'How big is your team?',
        questionEs: '¿Cuántas personas hay en tu equipo?',
        options: [
            { labelEn: 'Just me', labelEs: 'Solo', value: 'Just me' },
            { labelEn: '2–5 people', labelEs: '2–5 personas', value: '2–5' },
            { labelEn: '6–20 people', labelEs: '6–20 personas', value: '6–20' },
            { labelEn: '21+ people', labelEs: '21+ personas', value: '21+' },
        ],
    },
    {
        id: 'challenge',
        questionEn: "What's your biggest content challenge right now?",
        questionEs: '¿Cuál es tu mayor reto con el contenido hoy?',
        options: [
            { labelEn: 'Takes too long to produce', labelEs: 'Tarda demasiado', value: 'Takes too long' },
            { labelEn: 'Too expensive', labelEs: 'Es muy costoso', value: 'Too expensive' },
            { labelEn: "Doesn't convert", labelEs: 'No convierte', value: "Doesn't convert" },
            { labelEn: 'Need more volume', labelEs: 'Necesito más volumen', value: 'Need more volume' },
            { labelEn: "Don't know where to start", labelEs: 'No sé por dónde empezar', value: "Don't know where to start" },
        ],
    },
    {
        id: 'content_type',
        questionEn: 'What type of content do you mainly want to create?',
        questionEs: '¿Qué tipo de contenido quieres crear principalmente?',
        options: [
            { labelEn: 'UGC Videos', labelEs: 'UGC Videos', value: 'UGC Videos' },
            { labelEn: 'Cinematic Ads', labelEs: 'Anuncios cinemáticos', value: 'Cinematic Ads' },
            { labelEn: 'Image Ads', labelEs: 'Creativos de imagen', value: 'Image Ads' },
            { labelEn: 'Product Shots', labelEs: 'Fotos de producto', value: 'Product Shots' },
            { labelEn: 'All of the above', labelEs: 'Todo lo anterior', value: 'All of the above' },
        ],
    },
    {
        id: 'monthly_volume',
        questionEn: 'How many content pieces do you produce per month?',
        questionEs: '¿Cuántas piezas de contenido produces al mes?',
        options: [
            { labelEn: 'None yet', labelEs: 'Ninguna todavía', value: 'None yet' },
            { labelEn: '1–10', labelEs: '1–10', value: '1–10' },
            { labelEn: '11–50', labelEs: '11–50', value: '11–50' },
            { labelEn: '51–200', labelEs: '51–200', value: '51–200' },
            { labelEn: '200+', labelEs: '200+', value: '200+' },
        ],
    },
];

function IcpLangToggle() {
    const { lang, setLang } = useTranslation();
    return (
        <button
            type="button"
            onClick={() => setLang(lang === 'en' ? 'es' : 'en')}
            title={lang === 'en' ? 'Switch to Spanish' : 'Cambiar a Inglés'}
            style={{
                position: 'absolute',
                top: 24,
                right: 24,
                display: 'flex',
                alignItems: 'center',
                gap: 2,
                padding: '4px 8px',
                borderRadius: 6,
                border: '1px solid #E5E9F2',
                background: '#FFFFFF',
                cursor: 'pointer',
                fontSize: 12,
                fontWeight: 600,
                color: '#64748B',
                transition: 'all 0.15s ease',
                whiteSpace: 'nowrap' as const,
            }}
        >
            <span
                style={{
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: lang === 'en' ? '#337AFF' : 'transparent',
                    color: lang === 'en' ? '#fff' : '#94A3B8',
                    transition: 'all 0.15s ease',
                    fontWeight: lang === 'en' ? 700 : 500,
                }}
            >
                EN
            </span>
            <span
                style={{
                    padding: '2px 6px',
                    borderRadius: 4,
                    background: lang === 'es' ? '#337AFF' : 'transparent',
                    color: lang === 'es' ? '#fff' : '#94A3B8',
                    transition: 'all 0.15s ease',
                    fontWeight: lang === 'es' ? 700 : 500,
                }}
            >
                ES
            </span>
        </button>
    );
}

export function OnboardingICP({ userId: _userId, onComplete }: OnboardingICPProps) {
    const { t, lang } = useTranslation();
    const [step, setStep] = useState(0);
    const [answers, setAnswers] = useState<Partial<ICPAnswers>>({});
    const [selectedValue, setSelectedValue] = useState<string | null>(null);
    const [visible, setVisible] = useState(true);
    const [narrow, setNarrow] = useState(false);
    const advanceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        const check = () => setNarrow(window.innerWidth < 640);
        check();
        window.addEventListener('resize', check);
        return () => window.removeEventListener('resize', check);
    }, []);

    useEffect(() => {
        return () => {
            if (advanceTimerRef.current) clearTimeout(advanceTimerRef.current);
        };
    }, []);

    const question = ICP_QUESTIONS[step];
    const total = ICP_QUESTIONS.length;

    const progressLabel = t('onboarding.icp.progress')
        .replace('{current}', String(step + 1))
        .replace('{total}', String(total));

    const handleSelect = useCallback((option: ICPOption) => {
        if (selectedValue !== null) return;

        setSelectedValue(option.value);

        advanceTimerRef.current = setTimeout(() => {
            setVisible(false);

            advanceTimerRef.current = setTimeout(() => {
                const nextAnswers = { ...answers, [question.id]: option.value };
                setAnswers(nextAnswers);
                setSelectedValue(null);

                if (step >= total - 1) {
                    onComplete(nextAnswers as ICPAnswers);
                    return;
                }

                setStep((s) => s + 1);
                setVisible(true);
            }, 150);
        }, 200);
    }, [answers, onComplete, question.id, selectedValue, step, total]);

    const primaryQuestion = lang === 'es' ? question.questionEs : question.questionEn;

    return (
        <div
            style={{
                position: 'fixed',
                inset: 0,
                zIndex: 9999,
                background: 'var(--bg-app, #f7f8fa)',
                overflowY: 'auto',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                padding: '32px 24px 48px',
            }}
        >
            <IcpLangToggle />

            <header style={{ textAlign: 'center', marginBottom: 32, flexShrink: 0 }}>
                <img
                    src="/StudioLogo_Black.svg"
                    alt="Aitoma Studio"
                    style={{ width: 130, height: 'auto', objectFit: 'contain' }}
                />
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, marginTop: 16 }}>
                    {ICP_QUESTIONS.map((_, i) => (
                        <div
                            key={i}
                            style={{
                                width: i === step ? 24 : 8,
                                height: 4,
                                borderRadius: 2,
                                background: i <= step ? '#337AFF' : 'rgba(0,0,0,0.1)',
                                transition: 'all 0.3s',
                            }}
                        />
                    ))}
                </div>
                <p style={{ margin: '10px 0 0', fontSize: 13, color: '#8A93B0', fontWeight: 600 }}>
                    {progressLabel}
                </p>
            </header>

            <div
                style={{
                    width: '100%',
                    maxWidth: 560,
                    opacity: visible ? 1 : 0,
                    transform: visible ? 'translateY(0)' : 'translateY(8px)',
                    transition: 'opacity 150ms ease-out, transform 150ms ease-out',
                }}
            >
                <h2
                    style={{
                        margin: '0 0 28px',
                        fontSize: 22,
                        fontWeight: 700,
                        color: '#0D1B3E',
                        textAlign: 'center',
                        lineHeight: 1.35,
                    }}
                >
                    {primaryQuestion}
                </h2>

                <div
                    style={{
                        display: 'grid',
                        gridTemplateColumns: narrow ? '1fr' : '1fr 1fr',
                        gap: 12,
                    }}
                >
                    {question.options.map((option) => {
                        const isSelected = selectedValue === option.value;
                        const label = lang === 'es' ? option.labelEs : option.labelEn;

                        return (
                            <button
                                key={option.value}
                                type="button"
                                onClick={() => handleSelect(option)}
                                disabled={selectedValue !== null && !isSelected}
                                style={{
                                    position: 'relative',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    padding: '16px 20px',
                                    borderRadius: 14,
                                    border: isSelected ? '1.5px solid #337AFF' : '1.5px solid #E5E9F2',
                                    background: isSelected ? 'rgba(51,122,255,0.08)' : '#FFFFFF',
                                    cursor: selectedValue !== null ? 'default' : 'pointer',
                                    textAlign: 'center',
                                    fontFamily: 'inherit',
                                    transition: 'border-color 0.15s, background 0.15s',
                                    opacity: selectedValue !== null && !isSelected ? 0.5 : 1,
                                }}
                                onMouseEnter={(e) => {
                                    if (selectedValue !== null) return;
                                    e.currentTarget.style.borderColor = '#337AFF';
                                    e.currentTarget.style.background = 'rgba(51,122,255,0.04)';
                                }}
                                onMouseLeave={(e) => {
                                    if (isSelected) return;
                                    e.currentTarget.style.borderColor = '#E5E9F2';
                                    e.currentTarget.style.background = '#FFFFFF';
                                }}
                            >
                                <span style={{ fontSize: 14, fontWeight: 600, color: '#0D1B3E', lineHeight: 1.35 }}>
                                    {label}
                                </span>
                                {isSelected && (
                                    <span
                                        style={{
                                            position: 'absolute',
                                            top: 10,
                                            right: 10,
                                            width: 20,
                                            height: 20,
                                            borderRadius: '50%',
                                            background: '#337AFF',
                                            color: '#FFFFFF',
                                            fontSize: 12,
                                            fontWeight: 700,
                                            display: 'flex',
                                            alignItems: 'center',
                                            justifyContent: 'center',
                                        }}
                                        aria-hidden="true"
                                    >
                                        ✓
                                    </span>
                                )}
                            </button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
