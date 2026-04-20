'use client';

import { useState, useEffect, useCallback } from 'react';
import { useApp } from '@/providers/AppProvider';
import { creativeFetch } from '@/lib/creative-os-api';
import { ProjectCard } from '@/components/studio/ProjectCard';
import { useTranslation } from '@/lib/i18n';

interface ProjectWithCounts {
    id: string;
    name: string;
    is_default?: boolean;
    created_at?: string;
    recent_previews?: { url: string; type: 'image' | 'video' }[];
    asset_counts?: {
        images?: number;
        videos?: number;
        influencers?: number;
        products?: number;
    };
}

export default function StudioDashboard() {
    const { session, isLoading } = useApp();
    const { t } = useTranslation();
    const [projects, setProjects] = useState<ProjectWithCounts[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [showCreate, setShowCreate] = useState(false);
    const [newName, setNewName] = useState('');
    const [creating, setCreating] = useState(false);
    const [search, setSearch] = useState('');

    // ── Selection state ──────────────────────────────────────────────
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [deleting, setDeleting] = useState(false);

    const fetchProjects = useCallback(async () => {
        if (!session) return;
        setLoading(true);
        try {
            const data = await creativeFetch<ProjectWithCounts[]>('/creative-os/projects/');
            setProjects(data);
            setError(null);
        } catch (err: unknown) {
            console.error('Failed to load projects:', err);
            setError(err instanceof Error ? err.message : 'Failed to load projects');
        } finally {
            setLoading(false);
        }
    }, [session]);

    useEffect(() => { fetchProjects(); }, [fetchProjects]);

    const handleCreate = async () => {
        const name = newName.trim();
        if (!name || creating) return;
        setCreating(true);
        try {
            await creativeFetch('/creative-os/projects/', {
                method: 'POST',
                body: JSON.stringify({ name }),
            });
            setNewName('');
            setShowCreate(false);
            await fetchProjects();
        } catch (err) {
            console.error('Failed to create project:', err);
            alert(t('creativeOs.projects.createFailed').replace('{err}', err instanceof Error ? err.message : 'Unknown error'));
        } finally {
            setCreating(false);
        }
    };

    // ── Selection helpers ─────────────────────────────────────────────
    const toggleSelect = (id: string) => {
        setSelected(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const selectAll = () => {
        const filtered = getFiltered();
        if (selected.size === filtered.length) {
            setSelected(new Set());
        } else {
            setSelected(new Set(filtered.map(p => p.id)));
        }
    };

    const clearSelection = () => setSelected(new Set());

    const handleDelete = async () => {
        if (selected.size === 0 || deleting) return;
        const count = selected.size;
        if (!confirm(t('creativeOs.projects.deleteCountConfirm').replace('{n}', String(count)))) return;
        setDeleting(true);
        try {
            await Promise.all(
                Array.from(selected).map(id =>
                    creativeFetch(`/creative-os/projects/${id}`, { method: 'DELETE' })
                )
            );
            setSelected(new Set());
            await fetchProjects();
        } catch (err) {
            console.error('Failed to delete projects:', err);
            alert(t('creativeOs.projects.deleteFailed').replace('{err}', err instanceof Error ? err.message : 'Unknown error'));
        } finally {
            setDeleting(false);
        }
    };

    const getFiltered = () => {
        if (!search.trim()) return projects;
        return projects.filter(p => p.name.toLowerCase().includes(search.trim().toLowerCase()));
    };

    const selectionMode = selected.size > 0;

    if (isLoading || loading) {
        return (
            <div style={{
                padding: '60px 32px',
                maxWidth: '1200px',
                margin: '0 auto',
            }}>
                <div style={{ marginBottom: '40px' }}>
                    <div style={{
                        width: '240px',
                        height: '32px',
                        borderRadius: '8px',
                        background: 'linear-gradient(90deg, rgba(51,122,255,0.06) 25%, rgba(51,122,255,0.12) 50%, rgba(51,122,255,0.06) 75%)',
                        backgroundSize: '200% 100%',
                        animation: 'shimmer 1.5s infinite linear',
                    }} />
                </div>
                <div style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                    gap: '20px',
                }}>
                    {[1, 2, 3].map(i => (
                        <div key={i} style={{
                            height: '180px',
                            borderRadius: '16px',
                            background: 'linear-gradient(90deg, rgba(51,122,255,0.04) 25%, rgba(51,122,255,0.08) 50%, rgba(51,122,255,0.04) 75%)',
                            backgroundSize: '200% 100%',
                            animation: `shimmer 1.5s infinite linear ${i * 0.2}s`,
                        }} />
                    ))}
                </div>
                <style>{`
                    @keyframes shimmer {
                        0% { background-position: 200% 0; }
                        100% { background-position: -200% 0; }
                    }
                `}</style>
            </div>
        );
    }

    const filtered = getFiltered();

    return (
        <div style={{
            padding: '40px 32px 120px',
            maxWidth: '1200px',
            margin: '0 auto',
        }}>
            {/* Header row — title, search, actions — all same line */}
            <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginBottom: '28px',
                gap: '16px',
                flexWrap: 'wrap',
            }}>
                {/* Left side: title or selection info */}
                {selectionMode ? (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        {/* Select all / deselect checkbox */}
                        <button
                            onClick={selectAll}
                            style={{
                                width: '20px', height: '20px', borderRadius: '5px',
                                border: selected.size === filtered.length
                                    ? '2px solid #337AFF'
                                    : '2px solid rgba(0,0,0,0.15)',
                                background: selected.size === filtered.length ? '#337AFF' : 'white',
                                cursor: 'pointer', display: 'flex', alignItems: 'center',
                                justifyContent: 'center', padding: 0, flexShrink: 0,
                                transition: 'all 0.15s',
                            }}
                        >
                            {selected.size === filtered.length && (
                                <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <polyline points="2,6 5,9 10,3" />
                                </svg>
                            )}
                        </button>
                        <span style={{ fontSize: '14px', fontWeight: 600, color: '#0D1B3E' }}>
                            {t('creativeOs.projects.selected').replace('{n}', String(selected.size))}
                        </span>
                        <button
                            onClick={clearSelection}
                            style={{
                                padding: '4px 10px', borderRadius: '6px',
                                border: '1px solid rgba(0,0,0,0.08)',
                                background: 'white', color: '#4A5578',
                                fontSize: '12px', fontWeight: 500,
                                cursor: 'pointer', transition: 'background 0.15s',
                            }}
                            onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.03)')}
                            onMouseLeave={e => (e.currentTarget.style.background = 'white')}
                        >{t('creativeOs.projects.cancel')}</button>
                    </div>
                ) : (
                    <p style={{
                        fontSize: '15px',
                        color: '#8A93B0',
                        margin: 0,
                        flexShrink: 0,
                    }}>
                        {t('creativeOs.projects.selectPrompt')}
                    </p>
                )}

                {/* Right side: search, count, actions */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    {/* Delete button — visible when projects selected */}
                    {selectionMode && (
                        <button
                            onClick={handleDelete}
                            disabled={deleting}
                            style={{
                                display: 'flex', alignItems: 'center', gap: '6px',
                                padding: '8px 16px', borderRadius: '10px',
                                border: 'none',
                                background: deleting ? 'rgba(239,68,68,0.4)' : '#EF4444',
                                color: 'white', fontSize: '13px', fontWeight: 600,
                                cursor: deleting ? 'default' : 'pointer',
                                transition: 'all 0.2s',
                                boxShadow: '0 2px 8px rgba(239,68,68,0.25)',
                            }}
                            onMouseEnter={e => {
                                if (!deleting) {
                                    e.currentTarget.style.background = '#DC2626';
                                    e.currentTarget.style.boxShadow = '0 4px 14px rgba(239,68,68,0.3)';
                                }
                            }}
                            onMouseLeave={e => {
                                if (!deleting) {
                                    e.currentTarget.style.background = '#EF4444';
                                    e.currentTarget.style.boxShadow = '0 2px 8px rgba(239,68,68,0.25)';
                                }
                            }}
                        >
                            <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                                <polyline points="3 6 5 6 21 6" />
                                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                            {deleting ? t('creativeOs.projects.deleting') : t('creativeOs.projects.deleteWithCount').replace('{n}', String(selected.size))}
                        </button>
                    )}

                    {/* Search Bar */}
                    {projects.length > 0 && (
                        <div style={{
                            position: 'relative',
                            width: '220px',
                        }}>
                            <svg
                                viewBox="0 0 24 24"
                                style={{
                                    position: 'absolute',
                                    left: '12px',
                                    top: '50%',
                                    transform: 'translateY(-50%)',
                                    width: '14px',
                                    height: '14px',
                                    fill: 'none',
                                    stroke: '#8A93B0',
                                    strokeWidth: '2',
                                    strokeLinecap: 'round',
                                    strokeLinejoin: 'round',
                                    pointerEvents: 'none',
                                }}
                            >
                                <circle cx="11" cy="11" r="8" />
                                <line x1="21" y1="21" x2="16.65" y2="16.65" />
                            </svg>
                            <input
                                id="project-search"
                                type="text"
                                value={search}
                                onChange={e => setSearch(e.target.value)}
                                placeholder={t('creativeOs.projects.searchPlaceholder')}
                                style={{
                                    width: '100%',
                                    padding: '8px 30px 8px 34px',
                                    borderRadius: '10px',
                                    border: '1.5px solid rgba(0,0,0,0.08)',
                                    background: 'white',
                                    fontSize: '13px',
                                    color: '#0D1B3E',
                                    outline: 'none',
                                    boxSizing: 'border-box',
                                    fontFamily: 'inherit',
                                    transition: 'border-color 0.2s, box-shadow 0.2s',
                                }}
                                onFocus={e => {
                                    e.currentTarget.style.borderColor = '#337AFF';
                                    e.currentTarget.style.boxShadow = '0 0 0 3px rgba(51,122,255,0.1)';
                                }}
                                onBlur={e => {
                                    e.currentTarget.style.borderColor = 'rgba(0,0,0,0.08)';
                                    e.currentTarget.style.boxShadow = 'none';
                                }}
                            />
                            {search && (
                                <button
                                    onClick={() => setSearch('')}
                                    style={{
                                        position: 'absolute',
                                        right: '8px',
                                        top: '50%',
                                        transform: 'translateY(-50%)',
                                        width: '18px',
                                        height: '18px',
                                        borderRadius: '50%',
                                        border: 'none',
                                        background: 'rgba(0,0,0,0.08)',
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        padding: 0,
                                    }}
                                >
                                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none" stroke="#666" strokeWidth="1.5" strokeLinecap="round">
                                        <line x1="1" y1="1" x2="7" y2="7" />
                                        <line x1="7" y1="1" x2="1" y2="7" />
                                    </svg>
                                </button>
                            )}
                        </div>
                    )}

                    {/* Project count badge */}
                    <div style={{
                        padding: '6px 14px',
                        borderRadius: '8px',
                        background: 'rgba(51,122,255,0.08)',
                        fontSize: '13px',
                        fontWeight: 600,
                        color: '#337AFF',
                    }}>
                        {(projects.length === 1 ? t('creativeOs.projects.countOne') : t('creativeOs.projects.countOther')).replace('{n}', String(projects.length))}
                    </div>

                    {/* New Project button */}
                    {!selectionMode && (
                        <button
                            id="new-project-btn"
                            onClick={() => setShowCreate(true)}
                            style={{
                                display: 'flex',
                                alignItems: 'center',
                                gap: '6px',
                                padding: '9px 18px',
                                borderRadius: '10px',
                                border: 'none',
                                background: '#337AFF',
                                color: 'white',
                                fontSize: '14px',
                                fontWeight: 600,
                                cursor: 'pointer',
                                transition: 'all 0.2s ease',
                                boxShadow: '0 2px 8px rgba(51,122,255,0.3)',
                                letterSpacing: '0.1px',
                            }}
                            onMouseEnter={e => {
                                e.currentTarget.style.background = '#2868E5';
                                e.currentTarget.style.boxShadow = '0 4px 14px rgba(51,122,255,0.4)';
                                e.currentTarget.style.transform = 'translateY(-1px)';
                            }}
                            onMouseLeave={e => {
                                e.currentTarget.style.background = '#337AFF';
                                e.currentTarget.style.boxShadow = '0 2px 8px rgba(51,122,255,0.3)';
                                e.currentTarget.style.transform = 'none';
                            }}
                        >
                            <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: 'currentColor', strokeWidth: '2.5' }}>
                                <line x1="12" y1="5" x2="12" y2="19" />
                                <line x1="5" y1="12" x2="19" y2="12" />
                            </svg>
                            {t('creativeOs.projects.newProjectBtn')}
                        </button>
                    )}
                </div>
            </div>

            {/* Create Project Modal */}
            {showCreate && (
                <>
                    <div
                        onClick={() => { setShowCreate(false); setNewName(''); }}
                        style={{
                            position: 'fixed',
                            inset: 0,
                            background: 'rgba(0,0,0,0.35)',
                            backdropFilter: 'blur(4px)',
                            zIndex: 9999,
                            animation: 'fadeIn 0.15s ease',
                        }}
                    />
                    <div style={{
                        position: 'fixed',
                        top: '50%',
                        left: '50%',
                        transform: 'translate(-50%, -50%)',
                        width: '420px',
                        maxWidth: '90vw',
                        background: '#FFF',
                        borderRadius: '20px',
                        padding: '32px',
                        boxShadow: '0 24px 60px rgba(0,0,0,0.2)',
                        zIndex: 10000,
                        animation: 'scaleIn 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                    }}>
                        <h2 style={{
                            fontSize: '18px',
                            fontWeight: 700,
                            color: '#0D1B3E',
                            margin: '0 0 4px',
                            letterSpacing: '-0.3px',
                        }}>
                            {t('creativeOs.projects.newProjectBtn')}
                        </h2>
                        <p style={{
                            fontSize: '13px',
                            color: '#8A93B0',
                            margin: '0 0 20px',
                        }}>
                            {t('creativeOs.projects.createBlurb')}
                        </p>
                        <input
                            id="new-project-name"
                            type="text"
                            value={newName}
                            onChange={e => setNewName(e.target.value)}
                            onKeyDown={e => { if (e.key === 'Enter') handleCreate(); }}
                            placeholder={t('creativeOs.projects.createExample')}
                            autoFocus
                            style={{
                                width: '100%',
                                padding: '12px 14px',
                                borderRadius: '10px',
                                border: '1.5px solid rgba(51,122,255,0.2)',
                                background: 'rgba(51,122,255,0.03)',
                                fontSize: '14px',
                                color: '#0D1B3E',
                                outline: 'none',
                                boxSizing: 'border-box',
                                fontFamily: 'inherit',
                                transition: 'border-color 0.15s',
                            }}
                            onFocus={e => (e.currentTarget.style.borderColor = '#337AFF')}
                            onBlur={e => (e.currentTarget.style.borderColor = 'rgba(51,122,255,0.2)')}
                        />
                        <div style={{ display: 'flex', gap: '8px', marginTop: '16px', justifyContent: 'flex-end' }}>
                            <button
                                onClick={() => { setShowCreate(false); setNewName(''); }}
                                style={{
                                    padding: '9px 18px',
                                    borderRadius: '10px',
                                    border: '1px solid rgba(0,0,0,0.08)',
                                    background: 'white',
                                    color: '#4A5578',
                                    fontSize: '13px',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                    transition: 'background 0.15s',
                                }}
                                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(0,0,0,0.03)')}
                                onMouseLeave={e => (e.currentTarget.style.background = 'white')}
                            >{t('creativeOs.projects.cancel')}</button>
                            <button
                                id="create-project-submit"
                                onClick={handleCreate}
                                disabled={!newName.trim() || creating}
                                style={{
                                    padding: '9px 22px',
                                    borderRadius: '10px',
                                    border: 'none',
                                    background: !newName.trim() || creating ? 'rgba(51,122,255,0.4)' : '#337AFF',
                                    color: 'white',
                                    fontSize: '13px',
                                    fontWeight: 600,
                                    cursor: !newName.trim() || creating ? 'default' : 'pointer',
                                    transition: 'all 0.15s',
                                    boxShadow: newName.trim() && !creating ? '0 2px 8px rgba(51,122,255,0.3)' : 'none',
                                }}
                            >
                                {creating ? t('creativeOs.projects.creating') : t('creativeOs.projects.createProject')}
                            </button>
                        </div>
                    </div>
                    <style>{`
                        @keyframes fadeIn {
                            from { opacity: 0; }
                            to { opacity: 1; }
                        }
                        @keyframes scaleIn {
                            from { opacity: 0; transform: translate(-50%, -50%) scale(0.95); }
                            to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
                        }
                    `}</style>
                </>
            )}

            {/* Error state */}
            {error && (
                <div style={{
                    padding: '16px 20px',
                    borderRadius: '12px',
                    background: 'rgba(239,68,68,0.08)',
                    border: '1px solid rgba(239,68,68,0.15)',
                    color: '#EF4444',
                    fontSize: '14px',
                    marginBottom: '24px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '10px',
                }}>
                    <svg viewBox="0 0 24 24" style={{ width: '18px', height: '18px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', flexShrink: 0 }}>
                        <circle cx="12" cy="12" r="10" />
                        <line x1="15" y1="9" x2="9" y2="15" />
                        <line x1="9" y1="9" x2="15" y2="15" />
                    </svg>
                    {error}
                    <span style={{ fontSize: '12px', color: '#8A93B0', marginLeft: 'auto' }}>
                        Make sure Creative OS service is running on port 8001
                    </span>
                </div>
            )}

            {/* Projects Grid */}
            {(() => {
                if (projects.length === 0 && !error) {
                    return (
                        <div style={{
                            textAlign: 'center',
                            padding: '80px 20px',
                            borderRadius: '16px',
                            background: 'rgba(255,255,255,0.5)',
                            border: '1px dashed rgba(51,122,255,0.15)',
                        }}>
                            <svg viewBox="0 0 24 24" style={{ width: '48px', height: '48px', fill: 'none', stroke: '#8A93B0', strokeWidth: '1.2', margin: '0 auto 16px', display: 'block' }}>
                                <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                            </svg>
                            <p style={{ color: '#4A5578', fontSize: '15px', fontWeight: 500, margin: '0 0 12px' }}>{t('creativeOs.projects.emptyTitle')}</p>
                            <button
                                onClick={() => setShowCreate(true)}
                                style={{
                                    padding: '10px 20px',
                                    borderRadius: '10px',
                                    border: 'none',
                                    background: '#337AFF',
                                    color: 'white',
                                    fontSize: '14px',
                                    fontWeight: 600,
                                    cursor: 'pointer',
                                }}
                            >{t('creativeOs.projects.createFirst')}</button>
                        </div>
                    );
                }

                if (filtered.length === 0 && search.trim()) {
                    return (
                        <div style={{
                            textAlign: 'center',
                            padding: '60px 20px',
                            color: '#8A93B0',
                            fontSize: '15px',
                        }}>
                            {t('creativeOs.projects.noMatches').replace('{q}', search.trim())}
                        </div>
                    );
                }

                return (
                    <div style={{
                        display: 'grid',
                        gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
                        gap: '20px',
                    }}>
                        {filtered.map(project => (
                            <div
                                key={project.id}
                                style={{ position: 'relative' }}
                                onClick={e => {
                                    // If in selection mode, clicks toggle selection instead of navigating
                                    if (selectionMode) {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        toggleSelect(project.id);
                                    }
                                }}
                            >
                                {/* Selection checkbox overlay */}
                                <div
                                    onClick={e => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        toggleSelect(project.id);
                                    }}
                                    style={{
                                        position: 'absolute',
                                        top: '12px',
                                        left: '12px',
                                        zIndex: 10,
                                        width: '22px',
                                        height: '22px',
                                        borderRadius: '6px',
                                        border: selected.has(project.id)
                                            ? '2px solid #337AFF'
                                            : '2px solid rgba(255,255,255,0.6)',
                                        background: selected.has(project.id) ? '#337AFF' : 'rgba(0,0,0,0.15)',
                                        cursor: 'pointer',
                                        display: 'flex',
                                        alignItems: 'center',
                                        justifyContent: 'center',
                                        backdropFilter: 'blur(4px)',
                                        transition: 'all 0.15s',
                                        opacity: selectionMode || selected.has(project.id) ? 1 : 0,
                                        pointerEvents: 'auto',
                                    }}
                                    onMouseEnter={e => {
                                        (e.currentTarget as HTMLDivElement).style.opacity = '1';
                                    }}
                                    onMouseLeave={e => {
                                        if (!selectionMode && !selected.has(project.id)) {
                                            (e.currentTarget as HTMLDivElement).style.opacity = '0';
                                        }
                                    }}
                                >
                                    {selected.has(project.id) && (
                                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                            <polyline points="2,6 5,9 10,3" />
                                        </svg>
                                    )}
                                </div>

                                {/* Blue ring when selected */}
                                <div style={{
                                    borderRadius: '18px',
                                    outline: selected.has(project.id) ? '2.5px solid #337AFF' : 'none',
                                    outlineOffset: '2px',
                                    transition: 'outline 0.15s',
                                }}>
                                    <ProjectCard project={project} />
                                </div>
                            </div>
                        ))}
                    </div>
                );
            })()}

            {/* Global style: show checkbox on hover */}
            <style>{`
                [style*="position: relative"]:hover > div:first-child {
                    opacity: 1 !important;
                }
            `}</style>
        </div>
    );
}
