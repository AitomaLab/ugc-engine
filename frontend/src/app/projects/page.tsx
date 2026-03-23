'use client';

import { useState, useEffect } from 'react';
import { useApp } from '@/providers/AppProvider';
import { createProject, updateProject } from '@/lib/supabaseData';
import { Project } from '@/lib/saas-types';

/* ── ProjectModal (Create / Edit) ────────────────────────── */
function ProjectModal({ isOpen, onClose, onSaved, project }: {
  isOpen: boolean; onClose: () => void; onSaved: () => void; project?: Project | null;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setName(project?.name || '');
      setDescription(project?.description || '');
      setError(null);
    }
  }, [isOpen, project]);

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
      if (project) {
        await updateProject(project.id, { name: name.trim(), description: description.trim() || undefined });
      } else {
        await createProject({ name: name.trim(), description: description.trim() || undefined });
      }
      onSaved();
      onClose();
    } catch (e: any) {
      setError(e.message || 'Failed to save project.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" style={{ maxWidth: '440px' }} onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>{project ? 'Edit Project' : 'New Project'}</h3>
          <button className="modal-close" onClick={onClose}>
            <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" /></svg>
          </button>
        </div>
        <div className="modal-body">
          <div style={{ marginBottom: '16px' }}>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>Project Name <span style={{ color: 'var(--red)' }}>*</span></label>
            <input className="input-field" autoFocus value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Summer Campaign" onKeyDown={e => { if (e.key === 'Enter') handleSave(); }} />
          </div>
          <div>
            <label style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-2)', display: 'block', marginBottom: '6px' }}>Description (optional)</label>
            <textarea className="input-field" value={description} onChange={e => setDescription(e.target.value)} placeholder="Brief description..." rows={3} style={{ resize: 'vertical' }} />
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
            {saving ? 'Saving...' : project ? 'Save Changes' : 'Create Project'}
          </button>
        </div>
      </div>
    </div>
  );
}

/* ── Projects Page ───────────────────────────────────────── */
export default function ProjectsPage() {
  const { projects, activeProject, setActiveProject, refreshProjects } = useApp();
  const [modalOpen, setModalOpen] = useState(false);
  const [editProject, setEditProject] = useState<Project | null>(null);

  return (
    <div className="content-area">
      <div className="page-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <h1>My Projects</h1>
          <p>Organize your assets into separate projects</p>
        </div>
        <button className="btn-create" onClick={() => { setEditProject(null); setModalOpen(true); }}>
          <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" /></svg>
          + New Project
        </button>
      </div>

      <div style={{ display: 'grid', gap: '12px' }}>
        {projects.length === 0 ? (
          <div className='empty-state'>
            <div className='empty-icon'>
              <svg viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" /></svg>
            </div>
            <div className='empty-title'>No projects yet</div>
            <div className='empty-sub'>Create your first project to organize your assets.</div>
            <button className='btn-primary' onClick={() => { setEditProject(null); setModalOpen(true); }}>Create Project</button>
          </div>
        ) : (
          projects.map(project => {
            const isActive = project.id === activeProject?.id;
            return (
              <div key={project.id} style={{
                background: 'white', border: isActive ? '2px solid var(--blue)' : '1.5px solid var(--border)',
                borderRadius: '12px', padding: '16px 20px', display: 'flex', alignItems: 'center', gap: '16px',
                cursor: 'pointer', transition: 'all 0.2s',
              }} onClick={() => setActiveProject(project.id)}>
                <div style={{
                  width: '40px', height: '40px', borderRadius: '10px',
                  background: isActive ? 'var(--blue-light)' : '#f9fafb',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                }}>
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke={isActive ? 'var(--blue)' : '#9ca3af'} strokeWidth="2">
                    <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
                  </svg>
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-1)' }}>
                    {project.name}
                    {project.is_default && <span style={{ fontSize: '10px', background: '#e5e7eb', borderRadius: '4px', padding: '1px 6px', marginLeft: '8px', color: '#6b7280', fontWeight: 500 }}>Default</span>}
                  </div>
                  {project.description && <div style={{ fontSize: '12px', color: 'var(--text-3)', marginTop: '2px' }}>{project.description}</div>}
                  <div style={{ fontSize: '11px', color: 'var(--text-3)', marginTop: '2px' }}>
                    Created {new Date(project.created_at || Date.now()).toLocaleDateString()}
                  </div>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); setEditProject(project); setModalOpen(true); }}
                  style={{
                    width: '32px', height: '32px', borderRadius: '8px', border: '1px solid var(--border)',
                    background: 'white', display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer', flexShrink: 0, transition: 'all 0.15s',
                  }}
                  title="Edit project"
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--text-3)" strokeWidth="2">
                    <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
                  </svg>
                </button>
                {isActive && (
                  <div style={{ padding: '4px 10px', background: 'var(--blue-light)', color: 'var(--blue)', borderRadius: '6px', fontSize: '11px', fontWeight: 600 }}>
                    Active
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      <ProjectModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSaved={() => refreshProjects()}
        project={editProject}
      />
    </div>
  );
}
