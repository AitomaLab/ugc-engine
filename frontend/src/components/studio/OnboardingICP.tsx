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
    emoji: string;
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
            { emoji: '🛍️', labelEn: 'Brand Owner', labelEs: 'Dueño de marca', value: 'Brand Owner' },
            { emoji: '📣', labelEn: 'Marketing Manager', labelEs: 'Director de marketing', value: 'Marketing Manager' },
            { emoji: '🎯', labelEn: 'Media Buyer', labelEs: 'Comprador de medios', value: 'Media Buyer' },
            { emoji: '🏢', labelEn: 'Agency', labelEs: 'Agencia', value: 'Agency' },
            { emoji: '🎨', labelEn: 'Content Creator', labelEs: 'Creador de contenido', value: 'Content Creator' },
            { emoji: '🔧', labelEn: 'Other', labelEs: 'Otro', value: 'Other' },
        ],
    },
    {
        id: 'team_size',
        questionEn: 'How big is your team?',
        questionEs: '¿Cuántas personas hay en tu equipo?',
        options: [
            { emoji: '👤', labelEn: 'Just me', labelEs: 'Solo', value: 'Solo' },
            { emoji: '👥', labelEn: '2–5 people', labelEs: '2–5 personas', value: '2–5' },
            { emoji: '🏬', labelEn: '6–20 people', labelEs: '6–20 personas', value: '6–20' },
            { emoji: '🏢', labelEn: '21+ people', labelEs: '21+ personas', value: '21+' },
        ],
    },
    {
        id: 'challenge',
        questionEn: "What's your biggest content challenge right now?",
        questionEs: '¿Cuál es tu mayor reto con el contenido hoy?',
        options: [
            { emoji: '⏱️', labelEn: 'Takes too long to produce', labelEs: 'Tarda demasiado', value: 'Takes too long' },
            { emoji: '💸', labelEn: 'Too expensive', labelEs: 'Es muy costoso', value: 'Too expensive' },
            { emoji: '📉', labelEn: "Doesn't convert", labelEs: 'No convierte', value: "Doesn't convert" },
            { emoji: '🔁', labelEn: 'Need more volume', labelEs: 'Necesito más volumen', value: 'Need more volume' },
            { emoji: '🤷', labelEn: "Don't know where to start", labelEs: 'No sé por dónde empezar', value: "Don't know where to start" },
        ],
    },
    {
        id: 'content_type',
        questionEn: 'What type of content do you mainly want to create?',
        questionEs: '¿Qué tipo de contenido quieres crear principalmente?',
        options: [
            { emoji: '📱', labelEn: 'UGC Videos', labelEs: 'UGC Videos', value: 'UGC Videos' },
            { emoji: '🎬', labelEn: 'Cinematic Ads', labelEs: 'Anuncios cinemáticos', value: 'Cinematic Ads' },
            { emoji: '🖼️', labelEn: 'Image Ads', labelEs: 'Creativos de imagen', value: 'Image Ads' },
            { emoji: '📦', labelEn: 'Product Shots', labelEs: 'Fotos de producto', value: 'Product Shots' },
            { emoji: '📊', labelEn: 'All of the above', labelEs: 'Todo lo anterior', value: 'All of the above' },
        ],
    },
    {
        id: 'monthly_volume',
        questionEn: 'How many content pieces do you produce per month?',
        questionEs: '¿Cuántas piezas de contenido produces al mes?',
        options: [
            { emoji: '0️⃣', labelEn: 'None yet', labelEs: 'Ninguna todavía', value: 'None yet' },
            { emoji: '🔢', labelEn: '1–10', labelEs: '1–10', value: '1–10' },
            { emoji: '🔢', labelEn: '11–50', labelEs: '11–50', value: '11–50' },
            { emoji: '🔢', labelEn: '51–200', labelEs: '51–200', value: '51–200' },
            { emoji: '🔢', labelEn: '200+', labelEs: '200+', value: '200+' },
        ],
    },
];

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
    const subQuestion = lang === 'es' ? question.questionEn : question.questionEs;

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
                        margin: '0 0 8px',
                        fontSize: 22,
                        fontWeight: 700,
                        color: '#0D1B3E',
                        textAlign: 'center',
                        lineHeight: 1.35,
                    }}
                >
                    {primaryQuestion}
                </h2>
                <p
                    style={{
                        margin: '0 0 28px',
                        fontSize: 14,
                        color: '#8A93B0',
                        textAlign: 'center',
                        lineHeight: 1.5,
                    }}
                >
                    {subQuestion}
                </p>

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
                                    gap: 12,
                                    padding: '16px 20px',
                                    borderRadius: 14,
                                    border: isSelected ? '1.5px solid #337AFF' : '1.5px solid #E5E9F2',
                                    background: isSelected ? 'rgba(51,122,255,0.08)' : '#FFFFFF',
                                    cursor: selectedValue !== null ? 'default' : 'pointer',
                                    textAlign: 'left',
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
                                <span style={{ fontSize: 24, lineHeight: 1, flexShrink: 0 }} aria-hidden="true">
                                    {option.emoji}
                                </span>
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
