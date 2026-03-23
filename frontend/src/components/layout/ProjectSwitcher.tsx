'use client';

import { useState, useRef, useEffect } from 'react';
import { useApp } from '@/providers/AppProvider';
import { createProject } from '@/lib/supabaseData';

/* ── Create Project Modal ──────────────────────────────── */
function CreateProjectModal({ isOpen, onClose, onSaved }: { isOpen: boolean; onClose: () => void; onSaved: () => void }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) { setName(''); setDescription(''); setError(null); }
  }, [isOpen]);

  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    if (isOpen) window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleSave = async () => {
    if (!name.trim()) { setError('Project name is required.'); return; }
    setSaving(true);
    setError(null);
    try {
      await createProject({ name: name.trim(), description: description.trim() || undefined });
      onSaved();
      onClose();
    } catch (e: any) {
      setError(e.message || 'Failed to create project.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" style={{ maxWidth: '440px' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>New Project</h3>
          <button className="modal-close" onClick={onClose}>
            <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>
        <div className="modal-body">
          <div style={{ marginBottom: '16px' }}>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>Project Name <span style={{ color: 'var(--red)' }}>*</span></label>
            <input
              className="input-field"
              autoFocus
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="e.g. Summer Campaign"
              onKeyDown={e => { if (e.key === 'Enter') handleSave(); }}
            />
          </div>
          <div>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>Description (optional)</label>
            <textarea
              className="input-field"
              value={description}
              onChange={e => setDescription(e.target.value)}
              placeholder="Brief description of this project..."
              rows={3}
              style={{ resize: 'vertical' }}
            />
          </div>
          {error && (
            <div style={{ background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.3)', borderRadius: '8px', padding: '8px 12px', marginTop: '12px', fontSize: '12px', color: 'var(--red)' }}>
              {error}
            </div>
          )}
        </div>
        <div className="modal-footer">
          <button className="btn-secondary" onClick={onClose}>Cancel</button>
          <button className="btn-primary" onClick={handleSave} disabled={saving} style={{ opacity: saving ? 0.6 : 1 }}>
            {saving ? 'Creating...' : 'Create Project'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Project Switcher ──────────────────────────────────── */
export function ProjectSwitcher() {
  const { projects, activeProject, setActiveProject, refreshProjects } = useApp();
  const [open, setOpen] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const displayName = activeProject?.name || 'My First Project';

  return (
    <div className="project-switcher" ref={ref}>
      <button className="ps-trigger" onClick={() => setOpen(!open)}>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
          <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
        </svg>
        <span>{displayName}</span>
        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className="ps-dropdown">
          <div className="ps-label">Projects</div>
          {projects.map(p => (
            <button
              key={p.id}
              className={`ps-item ${p.id === activeProject?.id ? 'active' : ''}`}
              onClick={() => { setActiveProject(p.id); setOpen(false); }}
            >
              <div className="ps-item-icon">
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <span style={{ flex: 1 }}>{p.name}</span>
              {p.is_default && <span className="ps-badge">Default</span>}
              {p.id === activeProject?.id && (
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--blue)" strokeWidth="2.5" style={{ flexShrink: 0 }}>
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              )}
            </button>
          ))}
          <div className="ps-divider" />
          <button className="ps-item ps-new" onClick={() => { setOpen(false); setModalOpen(true); }}>
            + New Project
          </button>
        </div>
      )}

      <CreateProjectModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={() => refreshProjects()}
      />

      <style jsx>{`
        .project-switcher { position: relative; }
        .ps-trigger {
          display: flex; align-items: center; gap: 6px;
          padding: 6px 12px; border-radius: 8px;
          border: 1px solid var(--border); background: white;
          font-size: 0.85rem; font-weight: 500; color: var(--text-1);
          cursor: pointer; transition: all 0.15s;
        }
        .ps-trigger:hover { border-color: var(--blue); background: var(--blue-light); }
        .ps-trigger svg { opacity: 0.5; }
        .ps-dropdown {
          position: absolute; top: calc(100% + 6px); left: 0;
          background: white; border: 1px solid var(--border); border-radius: 12px;
          box-shadow: 0 12px 36px rgba(51,122,255,0.18);
          min-width: 240px; z-index: 50; padding: 6px;
          animation: cssFadeIn 0.15s ease;
        }
        .ps-label { font-size: 0.7rem; font-weight: 600; color: var(--text-3); text-transform: uppercase; padding: 6px 10px 4px; letter-spacing: 0.05em; }
        .ps-item {
          display: flex; align-items: center; gap: 8px; width: 100%;
          padding: 8px 10px; border: none; background: none; border-radius: 8px;
          font-size: 0.85rem; color: var(--text-1); cursor: pointer; text-align: left;
          transition: background 0.1s;
        }
        .ps-item:hover { background: var(--blue-light); }
        .ps-item.active { background: var(--blue-light); color: var(--blue); font-weight: 600; }
        .ps-item-icon {
          width: 32px; height: 32px; border-radius: 8px;
          background: var(--blue-light); display: flex; align-items: center; justify-content: center; flex-shrink: 0;
        }
        .ps-item.active .ps-item-icon { background: rgba(51,122,255,0.15); }
        .ps-item-icon svg { opacity: 0.6; }
        .ps-item.active .ps-item-icon svg { stroke: var(--blue); opacity: 1; }
        .ps-badge { font-size: 0.65rem; background: var(--blue-light); border-radius: 4px; padding: 1px 5px; color: var(--text-3); margin-left: auto; }
        .ps-new { color: var(--blue); font-weight: 500; }
        .ps-divider { height: 1px; background: var(--border-soft); margin: 4px 0; }
        @keyframes cssFadeIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}
