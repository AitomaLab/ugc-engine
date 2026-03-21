'use client';

import { useState } from 'react';
import { useApp } from '@/providers/AppProvider';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export default function ProfilePage() {
  const { profile, getAuthHeaders } = useApp();
  const [name, setName] = useState(profile?.name || '');
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // Sync state when profile loads
  if (profile?.name && !name && !saving) {
    setName(profile.name);
  }

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    try {
      await fetch(`${API_URL}/api/profile`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({ name }),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) {
      console.error('Failed to update profile:', e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="content-area">
      <div className="page-header">
        <h1>Profile</h1>
        <p>Manage your personal information</p>
      </div>

      <div style={{ maxWidth: '600px' }}>
        <div className="settings-card">
          <div className="settings-section">
            <h3>Personal Information</h3>

            <div className="field-group">
              <label>Email</label>
              <input type="email" value={profile?.email || ''} disabled className="field-input disabled" />
              <span className="field-hint">Email cannot be changed</span>
            </div>

            <div className="field-group">
              <label>Display Name</label>
              <input
                type="text"
                value={name}
                onChange={e => setName(e.target.value)}
                placeholder="Your name"
                className="field-input"
              />
            </div>

            <div className="field-group">
              <label>User ID</label>
              <input type="text" value={profile?.id || ''} disabled className="field-input disabled mono" />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '1rem' }}>
              <button onClick={handleSave} disabled={saving} className="btn-primary">
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
              {saved && <span style={{ color: '#22c55e', fontSize: '0.85rem' }}>✓ Saved successfully</span>}
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .settings-card {
          background: white;
          border-radius: 12px;
          border: 1px solid #e5e7eb;
          padding: 1.5rem;
        }
        .settings-section h3 {
          font-size: 1rem;
          font-weight: 600;
          color: #1a1a2e;
          margin-bottom: 1.25rem;
        }
        .field-group {
          margin-bottom: 1rem;
        }
        .field-group label {
          display: block;
          font-size: 0.8rem;
          font-weight: 500;
          color: #6b7280;
          margin-bottom: 0.35rem;
        }
        .field-input {
          width: 100%;
          padding: 0.6rem 0.85rem;
          border: 1px solid #d1d5db;
          border-radius: 8px;
          font-size: 0.9rem;
          outline: none;
          transition: border-color 0.2s;
          box-sizing: border-box;
        }
        .field-input:focus {
          border-color: #6366f1;
          box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
        }
        .field-input.disabled {
          background: #f9fafb;
          color: #9ca3af;
          cursor: not-allowed;
        }
        .field-input.mono {
          font-family: monospace;
          font-size: 0.8rem;
        }
        .field-hint {
          font-size: 0.75rem;
          color: #9ca3af;
          margin-top: 0.2rem;
          display: block;
        }
        .btn-primary {
          padding: 0.6rem 1.25rem;
          background: #6366f1;
          color: white;
          border: none;
          border-radius: 8px;
          font-size: 0.9rem;
          font-weight: 600;
          cursor: pointer;
          transition: background 0.2s;
        }
        .btn-primary:hover:not(:disabled) { background: #4f46e5; }
        .btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }
      `}</style>
    </div>
  );
}
