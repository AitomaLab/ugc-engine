const shimmerBg = 'linear-gradient(90deg, rgba(51,122,255,0.06) 0%, rgba(51,122,255,0.14) 50%, rgba(51,122,255,0.06) 100%)';
const blockBase = {
    background: shimmerBg,
    backgroundSize: '200% 100%',
    animation: 'shimmer 1.6s ease-in-out infinite',
    borderRadius: '10px',
};

function Block({ w, h, r, style }: { w?: number | string; h: number | string; r?: number | string; style?: React.CSSProperties }) {
    return (
        <div
            style={{
                ...blockBase,
                width: w ?? '100%',
                height: h,
                borderRadius: r ?? 10,
                ...style,
            }}
        />
    );
}

export function PageSkeleton() {
    return (
        <div style={{ padding: '32px 40px', maxWidth: 1200, margin: '0 auto' }}>
            <Block w={220} h={28} style={{ marginBottom: 24 }} />
            <Block w="60%" h={20} style={{ marginBottom: 40 }} />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 16 }}>
                {Array.from({ length: 8 }).map((_, i) => (
                    <Block key={i} h={180} />
                ))}
            </div>
        </div>
    );
}

export function ProjectsListSkeleton() {
    return (
        <div style={{ padding: '32px 40px', maxWidth: 1400, margin: '0 auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 32 }}>
                <Block w={180} h={28} />
                <Block w={140} h={36} r={18} />
            </div>
            <Block w={320} h={40} r={12} style={{ marginBottom: 24 }} />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: 20 }}>
                {Array.from({ length: 9 }).map((_, i) => (
                    <div key={i} style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 14, padding: 14 }}>
                        <Block h={140} style={{ marginBottom: 12 }} />
                        <Block w="70%" h={16} style={{ marginBottom: 8 }} />
                        <Block w="40%" h={12} />
                    </div>
                ))}
            </div>
        </div>
    );
}

export function ProjectDetailSkeleton() {
    return (
        <div style={{ display: 'flex', gap: 16, padding: '24px 32px', height: 'calc(100vh - var(--header-h))' }}>
            <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Block w={220} h={26} />
                    <div style={{ display: 'flex', gap: 8 }}>
                        <Block w={90} h={32} r={16} />
                        <Block w={90} h={32} r={16} />
                    </div>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 12, flex: 1 }}>
                    {Array.from({ length: 12 }).map((_, i) => (
                        <Block key={i} h={180} />
                    ))}
                </div>
            </div>
            <div style={{ width: 380, flexShrink: 0, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 14, padding: 16, display: 'flex', flexDirection: 'column', gap: 12 }}>
                <Block w={140} h={18} />
                <Block h={80} />
                <Block h={80} />
                <Block h={80} />
                <div style={{ flex: 1 }} />
                <Block h={48} r={24} />
            </div>
        </div>
    );
}
