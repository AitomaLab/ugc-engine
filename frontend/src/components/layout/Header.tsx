'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';
import { useApp } from '@/providers/AppProvider';
import { ProjectSwitcher } from '@/components/layout/ProjectSwitcher';
import { supabase } from '@/lib/supabaseClient';

// SVG icon components — no emoji allowed
const IconGrid = () => <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></svg>;
const IconPlay = () => <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" /><polygon points="10,8 16,12 10,16" /></svg>;
const IconVideo = () => <svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" /><path d="M8 21h8M12 17v4" /></svg>;
const IconUser = () => <svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" /></svg>;
const IconFile = () => <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /></svg>;
const IconPhone = () => <svg viewBox="0 0 24 24"><rect x="5" y="2" width="14" height="20" rx="2" /><line x1="12" y1="18" x2="12.01" y2="18" /></svg>;
const IconBox = () => <svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /></svg>;
const IconActivity = () => <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12" /></svg>;
const IconArrowRight = () => <svg viewBox="0 0 24 24"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" /><polyline points="10 17 15 12 10 7" /><line x1="15" y1="12" x2="3" y2="12" /></svg>;
const IconPlus = () => <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>;
const IconBell = () => <svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.73 21a2 2 0 0 1-3.46 0" /></svg>;
const IconSettings = () => <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>;
const IconStar = () => <svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" /></svg>;
const IconLogOut = () => <svg viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>;
const NAV_ITEMS = [
    { href: '/', label: 'Studio', Icon: IconGrid },
    { href: '/create', label: 'Create', Icon: IconPlay },
    { divider: true },
    { href: '/videos', label: 'Videos', Icon: IconVideo },
    { href: '/influencers', label: 'Influencers', Icon: IconUser },
    { href: '/scripts', label: 'Scripts', Icon: IconFile },
    { href: '/app-clips', label: 'App Clips', Icon: IconPhone },
    { href: '/products', label: 'Products', Icon: IconBox },
    { divider: true },
    { href: '/activity', label: 'Activity', Icon: IconActivity },
];

function NavItem({ href, label, Icon }: { href: string; label: string; Icon: React.ComponentType }) {
    const pathname = usePathname();
    const isActive = pathname === href || (href !== '/' && pathname.startsWith(href));
    return (
        <Link href={href} className={`nav-item ${isActive ? 'active' : ''}`}>
            <Icon />
            {label}
        </Link>
    );
}

function ProfileDropdown() {
    const [open, setOpen] = useState(false);
    const { profile, subscription, wallet } = useApp();

    const initials = profile?.name
        ? profile.name.split(' ').map(w => w[0]).join('').toUpperCase().slice(0, 2)
        : profile?.email
            ? profile.email[0].toUpperCase()
            : 'U';

    const planName = subscription?.plan?.name || 'Free';
    const balance = wallet?.balance ?? 0;
    const monthlyCredits = subscription?.plan?.credits_monthly ?? 0;
    const used = monthlyCredits > 0 ? monthlyCredits - balance : 0;
    const percentage = monthlyCredits > 0 ? Math.round((balance / monthlyCredits) * 100) : 0;

    const handleSignOut = async () => {
        await supabase.auth.signOut();
        window.location.href = '/login';
    };

    return (
        <div className={`profile-wrapper ${open ? 'open' : ''}`} onClick={() => setOpen(!open)}>
            <div className="avatar">{initials}</div>
            <div className="profile-dropdown" onClick={e => e.stopPropagation()}>
                <div className="pd-header">
                    <div className="pd-avatar">{initials}</div>
                    <div>
                        <div className="pd-name">{profile?.name || profile?.email || 'User'}</div>
                        <div className="pd-plan">{planName} Plan</div>
                    </div>
                </div>
                <div className="pd-credits">
                    <div className="pd-credits-label">Monthly Credits</div>
                    <div className="pd-credits-row">
                        <span className="pd-credits-value">{balance.toLocaleString()}</span>
                        {monthlyCredits > 0 && <span className="pd-credits-total">of {monthlyCredits.toLocaleString()}</span>}
                    </div>
                    {monthlyCredits > 0 && (
                        <>
                            <div className="pd-bar-bg"><div className="pd-bar-fill" style={{ width: `${percentage}%` }} /></div>
                            <div className="pd-bar-labels"><span>Used: {used.toLocaleString()}</span><span>{percentage}% remaining</span></div>
                        </>
                    )}
                    <button className="pd-topup" onClick={() => { window.location.href = '/manage?topup=1'; }}>Top Up Credits</button>
                </div>
                <Link href="/profile" className="pd-menu-item"><IconUser />View Profile</Link>
                <Link href="/projects" className="pd-menu-item"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>My Projects</Link>
                <Link href="/manage" className="pd-menu-item"><IconSettings />Manage Account</Link>
                <Link href="/upgrade" className="pd-menu-item"><IconStar />Upgrade Plan</Link>
                <div className="pd-divider" />
                <div className="pd-menu-item danger" onClick={handleSignOut}><IconLogOut />Sign Out</div>
            </div>
        </div>
    );
}

export function Header() {
    const [menuOpen, setMenuOpen] = useState(false);
    return (
        <header className="header">
            <Link href="/" className="logo">
                <img src="/StudioLogo_Black.svg" alt="Studio Logo" style={{ height: '32px' }} />
            </Link>

            <button className="menu-toggle" onClick={() => setMenuOpen(!menuOpen)} aria-label="Toggle menu">
                <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2">
                    {menuOpen ? (
                        <><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></>
                    ) : (
                        <><line x1="3" y1="6" x2="21" y2="6" /><line x1="3" y1="12" x2="21" y2="12" /><line x1="3" y1="18" x2="21" y2="18" /></>
                    )}
                </svg>
            </button>

            <nav className={`main-nav ${menuOpen ? 'open' : ''}`}>
                {NAV_ITEMS.map((item, i) =>
                    'divider' in item ? (
                        <div key={`div-${i}`} className="nav-divider" />
                    ) : (
                        <NavItem key={item.href} href={item.href!} label={item.label!} Icon={item.Icon!} />
                    )
                )}
            </nav>

            <div className="header-actions">
                <ProjectSwitcher />
                <Link href="/cinematic" className="btn-cinematic">
                    <IconArrowRight />
                    <span className="btn-label">Cinematic Shots</span>
                </Link>
                <Link href="/create" className="btn-create">
                    <IconPlus />
                    <span className="btn-label">Create Video</span>
                </Link>
                <div className="nav-divider hide-mobile" />
                <button className="icon-btn">
                    <IconBell />
                    <span className="notif-dot" />
                </button>
                <ProfileDropdown />
            </div>
        </header>
    );
}
