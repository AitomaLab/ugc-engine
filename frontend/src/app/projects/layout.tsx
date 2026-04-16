import type { Metadata } from 'next';

export const metadata: Metadata = {
    title: 'Aitoma Studio',
    description: 'Project-based creative workspace for AI image and video generation',
};

export default function StudioLayout({ children }: { children: React.ReactNode }) {
    return <>{children}</>;
}
