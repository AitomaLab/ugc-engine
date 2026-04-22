import type { CaptionStylePreview } from './styles';

interface CaptionStylePreviewCardProps {
    style: CaptionStylePreview;
    selected?: boolean;
    onSelect?: (id: string) => void;
    size?: 'sm' | 'md';
}

export function CaptionStylePreviewCard({ style, selected, onSelect, size = 'sm' }: CaptionStylePreviewCardProps) {
    const sm = size === 'sm';
    const words = style.sample_text.split(' ');
    const hi = style.highlight_word_index ?? -1;

    const baseFontSize = sm ? 18 : 28;
    const fontSize = style.id === 'minimal' ? baseFontSize - 2 : baseFontSize;

    const textShadow = style.stroke_color
        ? `-1.5px -1.5px 0 ${style.stroke_color}, 1.5px -1.5px 0 ${style.stroke_color}, -1.5px 1.5px 0 ${style.stroke_color}, 1.5px 1.5px 0 ${style.stroke_color}`
        : '1px 1px 4px rgba(0,0,0,0.9)';

    const interactive = typeof onSelect === 'function';

    return (
        <button
            type="button"
            onClick={interactive ? () => onSelect!(style.id) : undefined}
            disabled={!interactive}
            style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '8px',
                padding: 0,
                border: selected ? '2px solid #337AFF' : '1px solid rgba(13,27,62,0.1)',
                borderRadius: '12px',
                overflow: 'hidden',
                background: 'transparent',
                cursor: interactive ? 'pointer' : 'default',
                textAlign: 'left',
                width: '100%',
            }}
        >
            <div
                style={{
                    position: 'relative',
                    width: '100%',
                    paddingTop: '56%',
                    backgroundImage: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)',
                }}
            >
                <div
                    style={{
                        position: 'absolute',
                        left: '50%',
                        top: '50%',
                        transform: 'translate(-50%, -50%)',
                        width: '90%',
                        textAlign: 'center',
                        display: 'flex',
                        flexWrap: 'wrap',
                        justifyContent: 'center',
                        gap: style.id === 'bold' ? '4px' : '3px',
                    }}
                >
                    {words.map((w, i) => {
                        const isHi = i === hi;
                        const displayWord = style.uppercase ? w.toUpperCase() : w;
                        return (
                            <span
                                key={i}
                                style={{
                                    fontFamily: style.font_family,
                                    fontSize: `${fontSize}px`,
                                    fontWeight: style.font_weight,
                                    color: isHi ? style.highlight_color : style.color,
                                    textShadow,
                                    textTransform: style.uppercase ? 'uppercase' : 'none',
                                    display: 'inline-block',
                                    transform: isHi && style.id === 'hormozi' ? 'scale(1.1)' : 'scale(1)',
                                    letterSpacing: '0.5px',
                                }}
                            >
                                {displayWord}
                            </span>
                        );
                    })}
                </div>
            </div>
            <div style={{ padding: '8px 10px 12px' }}>
                <div style={{ fontSize: sm ? '12px' : '14px', fontWeight: 700, color: '#0D1B3E' }}>{style.name}</div>
                <div style={{ fontSize: sm ? '10px' : '12px', color: '#6B7280', lineHeight: 1.3, marginTop: '2px' }}>
                    {style.description}
                </div>
            </div>
        </button>
    );
}
