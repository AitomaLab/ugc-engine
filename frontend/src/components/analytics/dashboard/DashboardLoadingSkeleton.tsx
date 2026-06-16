'use client';

/** Shared shimmer block for dashboard loading states. */
export function ShimmerBlock({
    height,
    width = '100%',
    radius = 10,
}: {
    height: number | string;
    width?: number | string;
    radius?: number;
}) {
    return (
        <div
            aria-hidden
            style={{
                height,
                width,
                borderRadius: radius,
                background: 'linear-gradient(90deg, #E2E8F0 0%, #F1F5F9 50%, #E2E8F0 100%)',
                backgroundSize: '200% 100%',
                animation: 'dashShimmer 1.4s ease-in-out infinite',
            }}
        />
    );
}

export function KpiCardsSkeleton() {
    return (
        <div className="dash-kpi-grid">
            {Array.from({ length: 3 }).map((_, i) => (
                <div
                    key={i}
                    style={{
                        background: '#FFFFFF',
                        border: '1px solid #E2E8F0',
                        borderRadius: 18,
                        padding: '16px 18px',
                        minHeight: 152,
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 10,
                    }}
                >
                    <ShimmerBlock height={12} width="55%" radius={6} />
                    <ShimmerBlock height={34} width="45%" radius={8} />
                    <ShimmerBlock height={11} width="40%" radius={6} />
                    <div style={{ marginTop: 'auto', paddingTop: 8 }}>
                        <ShimmerBlock height={44} radius={8} />
                    </div>
                </div>
            ))}
            <style>{`
                @keyframes dashShimmer {
                    0% { background-position: 200% 0; }
                    100% { background-position: -200% 0; }
                }
            `}</style>
        </div>
    );
}

export function ChartSkeleton({ height = 240 }: { height?: number }) {
    return (
        <div
            style={{
                height,
                borderRadius: 14,
                border: '1px solid #E2E8F0',
                background: '#F8FAFC',
                padding: 20,
                display: 'flex',
                flexDirection: 'column',
                gap: 12,
            }}
        >
            <ShimmerBlock height={14} width="30%" radius={6} />
            <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: 8 }}>
                {Array.from({ length: 12 }).map((_, i) => (
                    <ShimmerBlock
                        key={i}
                        height={`${30 + (i % 4) * 12}%`}
                        radius={4}
                    />
                ))}
            </div>
            <style>{`
                @keyframes dashShimmer {
                    0% { background-position: 200% 0; }
                    100% { background-position: -200% 0; }
                }
            `}</style>
        </div>
    );
}

export function PanelSkeleton() {
    return (
        <div
            style={{
                background: '#FFFFFF',
                border: '1px solid #E2E8F0',
                borderRadius: 18,
                padding: 22,
                flex: 1,
                minHeight: 220,
                display: 'flex',
                flexDirection: 'column',
                gap: 16,
            }}
        >
            <ShimmerBlock height={18} width="50%" radius={6} />
            <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <ShimmerBlock height={140} width={140} radius={999} />
            </div>
        </div>
    );
}
