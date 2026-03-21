'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/utils';
import { Influencer } from '@/lib/types';
import { InfluencerModal } from '@/app/library/InfluencerModal';
import Select from '@/components/ui/Select';
import { useProgressiveList } from '@/hooks/useProgressiveList';

export default function InfluencersPage() {
  const [influencers, setInfluencers] = useState<Influencer[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [genderFilter, setGenderFilter] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Influencer | null>(null);

  const fetchInfluencers = useCallback(async () => {
    try {
      const data = await apiFetch<Influencer[]>('/influencers');
      setInfluencers(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchInfluencers(); }, [fetchInfluencers]);

  // Re-fetch when user switches projects
  useEffect(() => {
    const handler = () => { setLoading(true); fetchInfluencers(); };
    window.addEventListener('projectChanged', handler);
    return () => window.removeEventListener('projectChanged', handler);
  }, [fetchInfluencers]);

  async function handleDelete(id: string) {
    if (!confirm('Delete this influencer? This cannot be undone.')) return;
    try {
      await apiFetch(`/influencers/${id}`, { method: 'DELETE' });
      setInfluencers(prev => prev.filter(i => i.id !== id));
    } catch (err) { console.error('Delete error:', err); }
  }

  const filtered = influencers.filter(inf =>
    inf.name.toLowerCase().includes(search.toLowerCase()) &&
    (genderFilter === '' || inf.gender === genderFilter)
  );

  const { visibleItems: visibleInfluencers, sentinelRef, hasMore } = useProgressiveList(filtered, 16);

  return (
    <div className='content-area'>
      <div className='page-header'>
        <h1>AI Influencers</h1>
        <p>Your roster of AI-powered influencer profiles.</p>
      </div>

      <div className='asset-toolbar'>
        <div className='asset-toolbar-left'>
          <div className='search-box'>
            <svg viewBox='0 0 24 24'><circle cx='11' cy='11' r='8' /><line x1='21' y1='21' x2='16.65' y2='16.65' /></svg>
            <input type='text' placeholder='Search influencers...' value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <Select
            className='filter-select'
            value={genderFilter}
            onChange={setGenderFilter}
            options={[
              { value: '', label: 'All Types' },
              { value: 'Female', label: 'Female' },
              { value: 'Male', label: 'Male' }
            ]}
          />
        </div>
        <button className='btn-create' onClick={() => { setEditTarget(null); setModalOpen(true); }}>
          <svg viewBox='0 0 24 24'><line x1='12' y1='5' x2='12' y2='19' /><line x1='5' y1='12' x2='19' y2='12' /></svg>
          New Influencer
        </button>
      </div>

      {loading ? (
        <div className='empty-state'><div className='empty-title'>Loading influencers...</div></div>
      ) : filtered.length === 0 ? (
        <div className='empty-state'>
          <div className='empty-icon'><svg viewBox='0 0 24 24'><circle cx='12' cy='8' r='4' /><path d='M4 20c0-4 3.6-7 8-7s8 3 8 7' /></svg></div>
          <div className='empty-title'>No influencers found</div>
          <div className='empty-sub'>Add your first AI influencer to get started.</div>
          <button className='btn-primary' onClick={() => { setEditTarget(null); setModalOpen(true); }}>Add Influencer</button>
        </div>
      ) : (
        <>
        <div className='influencers-grid'>
          {visibleInfluencers.map(inf => (
            <div key={inf.id} className='icard' style={{ cursor: 'default' }}>
              <div className='icard-thumb' style={inf.image_url ? { backgroundImage: `url(${inf.image_url})`, position: 'relative' } : { background: 'linear-gradient(160deg,#1a1a2e,#0f3460)', position: 'relative' }}>
                <span className='icard-name'>{inf.name}</span>
                <button className="card-delete-btn" onClick={(e) => { e.stopPropagation(); handleDelete(inf.id); }} title="Delete influencer">
                  <svg viewBox="0 0 24 24"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
                </button>
              </div>
              <div className='icard-info' style={{ paddingBottom: '0' }}>
                <div className='icard-tags'>
                  {inf.gender && <span className='icard-tag'>{inf.gender}</span>}
                  {inf.style && <span className='icard-tag'>{inf.style}</span>}
                </div>
              </div>
              <div style={{ display: 'flex', borderTop: '1px solid var(--border-soft)', marginTop: '12px' }}>
                <Link href={`/create?influencer_id=${inf.id}`} style={{ flex: 1, padding: '12px', textAlign: 'center', fontSize: '13px', fontWeight: 600, color: 'var(--blue)', textDecoration: 'none', borderRight: '1px solid var(--border-soft)', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }} className='hover:bg-[rgba(51,122,255,0.05)] transition-colors'>
                  <svg viewBox='0 0 24 24' style={{ width: '14px', height: '14px', fill: 'currentColor' }}><polygon points='5,3 19,12 5,21' /></svg>
                  Use Video
                </Link>
                <button onClick={() => { setEditTarget(inf); setModalOpen(true); }} style={{ flex: 1, padding: '12px', textAlign: 'center', fontSize: '13px', fontWeight: 600, color: 'var(--text-2)', textDecoration: 'none', border: 'none', background: 'transparent', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '6px' }} className='hover:bg-[rgba(0,0,0,0.02)] transition-colors'>
                  <svg viewBox='0 0 24 24' style={{ width: '14px', height: '14px', stroke: 'currentColor', fill: 'none', strokeWidth: '2' }}><path d='M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z' /></svg>
                  Edit
                </button>
              </div>
            </div>
          ))}
        </div>
        {hasMore && <div ref={sentinelRef} style={{ height: '1px', marginTop: '8px' }} />}
        </>
      )}

      <InfluencerModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        initialData={editTarget}
        onSave={() => { fetchInfluencers(); setModalOpen(false); }}
      />
    </div>
  );
}
