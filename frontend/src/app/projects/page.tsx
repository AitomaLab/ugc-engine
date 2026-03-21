'use client';

import { useState } from 'react';
import { useApp } from '@/providers/AppProvider';
import { apiFetch } from '@/lib/utils';
import Link from 'next/link';

export default function ProjectsPage() {
  const { projects, activeProject, setActiveProject, refreshProjects } = useApp();
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState('');
  const [saving, setSaving] = useState(false);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setSaving(true);
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
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="content-area">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>My Projects</h1>
          <p>Organize your assets into separate projects</p>
        </div>
        <button onClick={() => setCreating(true)} style={{ padding: '8px 18px', background: '#6366f1', color: 'white', border: 'none', borderRadius: '8px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
          + New Project
        </button>
      </div>

      {/* Create form */}
      {creating && (
        <div style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '16px', marginBottom: '16px', display: 'flex', gap: '10px', alignItems: 'center' }}>
          <input
            autoFocus
            value={newName}
            onChange={e => setNewName(e.target.value)}
            placeholder="Project name..."
            onKeyDown={e => { if (e.key === 'Enter') handleCreate(); if (e.key === 'Escape') setCreating(false); }}
            style={{ flex: 1, padding: '8px 12px', border: '1px solid #d1d5db', borderRadius: '8px', fontSize: '14px', outline: 'none' }}
          />
          <button onClick={handleCreate} disabled={saving} style={{ padding: '8px 16px', background: '#6366f1', color: 'white', border: 'none', borderRadius: '8px', fontSize: '13px', fontWeight: 600, cursor: 'pointer' }}>
            {saving ? 'Creating...' : 'Create'}
          </button>
          <button onClick={() => setCreating(false)} style={{ padding: '8px 12px', background: 'white', color: '#6b7280', border: '1px solid #e5e7eb', borderRadius: '8px', fontSize: '13px', cursor: 'pointer' }}>
            Cancel
          </button>
        </div>
      )}

      {/* Project list */}
      <div style={{ display: 'grid', gap: '12px' }}>
        {projects.length === 0 ? (
          <div style={{ background: 'white', border: '1px solid #e5e7eb', borderRadius: '12px', padding: '40px', textAlign: 'center' }}>
            <div style={{ fontSize: '32px', marginBottom: '8px' }}>📁</div>
            <div style={{ fontSize: '16px', fontWeight: 600, color: '#1a1a2e', marginBottom: '4px' }}>No projects yet</div>
            <div style={{ fontSize: '13px', color: '#6b7280' }}>Create your first project to organize your assets.</div>
          </div>
        ) : (
          projects.map(project => {
            const isActive = project.id === activeProject?.id;
            return (
              <div key={project.id} style={{ background: 'white', border: isActive ? '2px solid #6366f1' : '1px solid #e5e7eb', borderRadius: '12px', padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '16px', cursor: 'pointer', transition: 'all 0.2s' }} onClick={() => setActiveProject(project.id)}>
                <div style={{ width: '40px', height: '40px', borderRadius: '10px', background: isActive ? '#eef2ff' : '#f9fafb', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke={isActive ? '#6366f1' : '#9ca3af'} strokeWidth="2">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  </svg>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '14px', color: '#1a1a2e' }}>
                    {project.name}
                    {project.is_default && <span style={{ fontSize: '10px', background: '#e5e7eb', borderRadius: '4px', padding: '1px 6px', marginLeft: '8px', color: '#6b7280', fontWeight: 500 }}>Default</span>}
                  </div>
                  <div style={{ fontSize: '12px', color: '#9ca3af', marginTop: '2px' }}>
                    Created {new Date(project.created_at || Date.now()).toLocaleDateString()}
                  </div>
                </div>
                {isActive && (
                  <div style={{ padding: '4px 10px', background: '#eef2ff', color: '#6366f1', borderRadius: '6px', fontSize: '11px', fontWeight: 600 }}>
                    Active
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
