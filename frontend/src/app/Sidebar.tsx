'use client';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState, useCallback } from 'react';
import { getApiUrl } from '@/lib/utils';

// ---------------------------------------------------------------------------
// SVG Icon Components
// ---------------------------------------------------------------------------

function StudioIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="7" height="7" rx="2" />
            <rect x="14" y="3" width="7" height="7" rx="2" />
            <rect x="3" y="14" width="7" height="7" rx="2" />
            <rect x="14" y="14" width="7" height="7" rx="2" />
        </svg>
    );
}

function CreateIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 5v14m-7-7h14" />
            <circle cx="12" cy="12" r="10" />
        </svg>
    );
}

function LibraryIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M4 19.5A2.5 2.5 0 016.5 17H20" />
            <path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" />
            <path d="M8 7h8m-8 4h6" />
        </svg>
    );
}

function ActivityIcon() {
    return (
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
        </svg>
    );
}

function BellIcon() {
    return (
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M18 8A6 6 0 006 8c0 7-3 9-3 9h18s-3-2-3-9" />
            <path d="M13.73 21a2 2 0 01-3.46 0" />
        </svg>
    );
}

// ---------------------------------------------------------------------------
// Navigation Items
// ---------------------------------------------------------------------------

const navItems = [
    { href: '/', label: 'Studio', icon: StudioIcon, shortcut: null },
    { href: '/create', label: 'Create', icon: CreateIcon, shortcut: 'N' },
    { href: '/library', label: 'Library', icon: LibraryIcon, shortcut: 'L' },
    { href: '/activity', label: 'Activity', icon: ActivityIcon, shortcut: null },
];

// ---------------------------------------------------------------------------
// Sidebar Component
// ---------------------------------------------------------------------------

export default function Sidebar() {
    const pathname = usePathname();
    const router = useRouter();
    const [notifications, setNotifications] = useState<string[]>([]);
    const [showNotifications, setShowNotifications] = useState(false);

    // Keyboard shortcuts
    useEffect(() => {
        function handleKeyDown(e: KeyboardEvent) {
            if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement || e.target instanceof HTMLSelectElement) return;

            if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
                e.preventDefault();
                router.push('/create');
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'l') {
                e.preventDefault();
                router.push('/library');
            } else if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
                e.preventDefault();
                router.push('/library');
                // Focus search is handled by the Library page itself
            } else if (e.key === 'Escape') {
                setShowNotifications(false);
                // Modals handle their own Esc
            }
        }

        window.addEventListener('keydown', handleKeyDown);
        return () => window.removeEventListener('keydown', handleKeyDown);
    }, [router]);

    // Poll for notifications (recently completed/failed jobs)
    const fetchNotifications = useCallback(async () => {
        try {
            const res = await fetch(`${getApiUrl()}/jobs?limit=10`);
            if (!res.ok) return;
            const jobs = await res.json();
            const recent = jobs
                .filter((j: { status: string; created_at: string }) => {
                    const age = Date.now() - new Date(j.created_at).getTime();
                    return age < 3600000 && (j.status === 'success' || j.status === 'failed');
                })
                .map((j: { id: string; status: string }) =>
                    j.status === 'success'
                        ? `Video ${j.id.substring(0, 6)} completed! ✅`
                        : `Job ${j.id.substring(0, 6)} failed. ❌`
                );
            setNotifications(recent);
        } catch { /* silent */ }
    }, []);

    useEffect(() => {
        fetchNotifications();
        const interval = setInterval(fetchNotifications, 30000);
        return () => clearInterval(interval);
    }, [fetchNotifications]);

    const isActive = (href: string) => {
        if (href === '/') return pathname === '/';
        return pathname.startsWith(href);
    };

    return (
        <aside className="w-64 border-r border-slate-800/60 bg-slate-900/40 backdrop-blur-2xl flex flex-col sticky top-0 h-screen">
            {/* Logo */}
            <div className="p-6 border-b border-slate-800/40">
                <h1 className="text-xl font-bold gradient-text tracking-tight">UGC Engine</h1>
                <p className="text-[10px] text-slate-500 mt-1 uppercase tracking-[0.2em] font-semibold">Creative Platform</p>
            </div>

            {/* Navigation */}
            <nav className="flex-1 p-3 space-y-1 mt-2">
                {navItems.map(({ href, label, icon: Icon, shortcut }) => {
                    const active = isActive(href);
                    return (
                        <Link
                            key={href}
                            href={href}
                            className={`
                sidebar-link group flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200
                ${active
                                    ? 'bg-blue-500/10 text-white border-l-2 border-blue-500 shadow-[inset_0_0_20px_rgba(59,130,246,0.06)]'
                                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border-l-2 border-transparent'
                                }
              `}
                        >
                            <span className={`transition-colors duration-200 ${active ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-300'}`}>
                                <Icon />
                            </span>
                            <span className="font-medium text-sm">{label}</span>
                            {shortcut && (
                                <span className="ml-auto text-[10px] text-slate-600 font-mono opacity-0 group-hover:opacity-100 transition-opacity">
                                    ⌘{shortcut}
                                </span>
                            )}
                        </Link>
                    );
                })}
            </nav>

            {/* Notifications */}
            <div className="px-4 pb-2 relative">
                <button
                    onClick={() => setShowNotifications(!showNotifications)}
                    className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 transition-all text-sm"
                >
                    <BellIcon />
                    <span className="font-medium">Notifications</span>
                    {notifications.length > 0 && (
                        <span className="ml-auto w-5 h-5 rounded-full bg-blue-500 text-white text-[10px] font-bold flex items-center justify-center">
                            {notifications.length}
                        </span>
                    )}
                </button>

                {showNotifications && (
                    <div className="absolute bottom-14 left-3 right-3 bg-slate-900 border border-slate-700/60 rounded-xl shadow-2xl p-3 space-y-2 z-50 max-h-60 overflow-y-auto">
                        {notifications.length === 0 ? (
                            <p className="text-xs text-slate-500 text-center py-4 italic">No recent notifications</p>
                        ) : (
                            notifications.map((n, i) => (
                                <div key={i} className="text-xs text-slate-300 p-2 rounded-lg bg-slate-800/50 border border-slate-700/30">
                                    {n}
                                </div>
                            ))
                        )}
                    </div>
                )}
            </div>

            {/* User Profile */}
            <div className="p-4 border-t border-slate-800/40">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-blue-500/20 flex items-center justify-center text-blue-400 font-bold text-sm">
                        U
                    </div>
                    <div className="overflow-hidden">
                        <p className="text-white font-medium text-sm truncate">Creator</p>
                        <p className="text-[10px] text-slate-500">Pro Account</p>
                    </div>
                </div>
            </div>
        </aside>
    );
}
