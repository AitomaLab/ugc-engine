'use client';

import { useState, useRef, useEffect } from 'react';
import { useApp } from '@/providers/AppProvider';
import { apiFetch } from '@/lib/utils';

export function ProjectSwitcher() {
  const { projects, activeProject, setActiveProject, refreshProjects } = useApp();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const ref = useRef<HTMLDivElement>(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
        setCreating(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      await apiFetch('/api/projects', {
        method: 'POST',
        body: JSON.stringify({ name: newName.trim() }),
      });
      setNewName('');
      setCreating(false);
      refreshProjects();
    } catch (e) {
      console.error('Failed to create project:', e);
    }
  };

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
              {p.name}
              {p.is_default && <span className="ps-badge">Default</span>}
            </button>
          ))}
          <div className="ps-divider" />
          {creating ? (
            <div className="ps-create-form">
              <input
                autoFocus
                value={newName}
                onChange={e => setNewName(e.target.value)}
                placeholder="Project name"
                onKeyDown={e => { if (e.key === 'Enter') handleCreate(); if (e.key === 'Escape') setCreating(false); }}
              />
              <button onClick={handleCreate}>Create</button>
            </div>
          ) : (
            <button className="ps-item ps-new" onClick={() => setCreating(true)}>
              + New Project
            </button>
          )}
        </div>
      )}

      <style jsx>{`
        .project-switcher { position: relative; }
        .ps-trigger {
          display: flex; align-items: center; gap: 6px;
          padding: 6px 12px; border-radius: 8px;
          border: 1px solid #e5e7eb; background: white;
          font-size: 0.85rem; font-weight: 500; color: #374151;
          cursor: pointer; transition: all 0.15s;
        }
        .ps-trigger:hover { border-color: #6366f1; background: #fafafe; }
        .ps-trigger svg { opacity: 0.5; }
        .ps-dropdown {
          position: absolute; top: calc(100% + 6px); left: 0;
          background: white; border: 1px solid #e5e7eb; border-radius: 10px;
          box-shadow: 0 8px 24px rgba(0,0,0,0.12);
          min-width: 220px; z-index: 50; padding: 6px;
        }
        .ps-label { font-size: 0.7rem; font-weight: 600; color: #9ca3af; text-transform: uppercase; padding: 6px 10px 4px; letter-spacing: 0.05em; }
        .ps-item {
          display: flex; align-items: center; gap: 8px; width: 100%;
          padding: 8px 10px; border: none; background: none; border-radius: 6px;
          font-size: 0.85rem; color: #374151; cursor: pointer; text-align: left;
          transition: background 0.1s;
        }
        .ps-item:hover { background: #f3f4f6; }
        .ps-item.active { background: #eef2ff; color: #4f46e5; font-weight: 600; }
        .ps-badge { font-size: 0.65rem; background: #e5e7eb; border-radius: 4px; padding: 1px 5px; color: #6b7280; margin-left: auto; }
        .ps-new { color: #6366f1; font-weight: 500; }
        .ps-divider { height: 1px; background: #f3f4f6; margin: 4px 0; }
        .ps-create-form { display: flex; gap: 4px; padding: 4px; }
        .ps-create-form input {
          flex: 1; padding: 5px 8px; border: 1px solid #d1d5db; border-radius: 6px;
          font-size: 0.8rem; outline: none;
        }
        .ps-create-form input:focus { border-color: #6366f1; }
        .ps-create-form button {
          padding: 5px 10px; background: #6366f1; color: white; border: none;
          border-radius: 6px; font-size: 0.8rem; cursor: pointer; font-weight: 500;
        }
      `}</style>
    </div>
  );
}
