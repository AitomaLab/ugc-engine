'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

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
    return (
        <div className={`profile-wrapper ${open ? 'open' : ''}`} onClick={() => setOpen(!open)}>
            <div className="avatar">AS</div>
            <div className="profile-dropdown" onClick={e => e.stopPropagation()}>
                <div className="pd-header">
                    <div className="pd-avatar">AS</div>
                    <div>
                        <div className="pd-name">Studio Logo</div>
                        <div className="pd-plan">Creator Plan</div>
                    </div>
                </div>
                <div className="pd-credits">
                    <div className="pd-credits-label">Monthly Credits</div>
                    <div className="pd-credits-row">
                        <span className="pd-credits-value">1,860</span>
                        <span className="pd-credits-total">of 3,000</span>
                    </div>
                    <div className="pd-bar-bg"><div className="pd-bar-fill" /></div>
                    <div className="pd-bar-labels"><span>Used: 1,140</span><span>62% remaining</span></div>
                    <button className="pd-topup">Top Up Credits</button>
                </div>
                <div className="pd-menu-item"><IconUser />View Profile</div>
                <Link href="/manage" className="pd-menu-item"><IconSettings />Manage Account</Link>
                <div className="pd-menu-item"><IconStar />Upgrade Plan</div>
                <div className="pd-divider" />
                <div className="pd-menu-item danger"><IconLogOut />Sign Out</div>
            </div>
        </div>
    );
}

export function Header() {
    return (
        <header className="header">
            <Link href="/" className="logo">
                <img src="/StudioLogo_Black.svg" alt="Studio Logo" style={{ height: '32px' }} />
            </Link>

            <nav className="main-nav">
                {NAV_ITEMS.map((item, i) =>
                    'divider' in item ? (
                        <div key={`div-${i}`} className="nav-divider" />
                    ) : (
                        <NavItem key={item.href} href={item.href!} label={item.label!} Icon={item.Icon!} />
                    )
                )}
            </nav>

            <div className="header-actions">
                <Link href="/cinematic" className="btn-cinematic">
                    <IconArrowRight />
                    Cinematic Shots
                </Link>
                <Link href="/create" className="btn-create">
                    <IconPlus />
                    Create Video
                </Link>
                <div className="nav-divider" />
                <button className="icon-btn">
                    <IconBell />
                    <span className="notif-dot" />
                </button>
                <ProfileDropdown />
            </div>
        </header>
    );
}
