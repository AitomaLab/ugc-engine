'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/utils';

interface Script {
  id: string;
  name: string;
  text: string;
  product_name?: string;
  category?: string;
  created_at?: string;
}

export default function ScriptsPage() {
  const [scripts, setScripts] = useState<Script[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const fetchScripts = useCallback(async () => {
    try {
      const data = await apiFetch<Script[]>('/scripts');
      setScripts(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchScripts(); }, [fetchScripts]);

  const filtered = scripts.filter(s =>
    (s.name || '').toLowerCase().includes(search.toLowerCase()) ||
    (s.text || '').toLowerCase().includes(search.toLowerCase())
  );

  const formatDate = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'numeric', day: 'numeric', year: 'numeric' });

  return (
    <div className='content-area'>
      <div className='page-header'>
        <h1>Scripts</h1>
        <p>Your library of UGC video scripts.</p>
      </div>

      <div className='asset-toolbar'>
        <div className='asset-toolbar-left'>
          <div className='search-box'>
            <svg viewBox='0 0 24 24'><circle cx='11' cy='11' r='8' /><line x1='21' y1='21' x2='16.65' y2='16.65' /></svg>
            <input type='text' placeholder='Search scripts...' value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>
        <Link href='/create' className='btn-create'>
          <svg viewBox='0 0 24 24'><line x1='12' y1='5' x2='12' y2='19' /><line x1='5' y1='12' x2='19' y2='12' /></svg>
          New Script
        </Link>
      </div>

      {loading ? (
        <div className='empty-state'><div className='empty-title'>Loading scripts...</div></div>
      ) : filtered.length === 0 ? (
        <div className='empty-state'>
          <div className='empty-icon'>
            <svg viewBox='0 0 24 24'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' /><polyline points='14 2 14 8 20 8' /></svg>
          </div>
          <div className='empty-title'>No scripts yet</div>
          <div className='empty-sub'>Scripts are automatically saved when you generate a video with AI Generate mode.</div>
        </div>
      ) : (
        <div className='scripts-list'>
          {filtered.map(script => (
            <div key={script.id} className='script-card'>
              <div className='script-icon'>
                <svg viewBox='0 0 24 24'><path d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z' /><polyline points='14 2 14 8 20 8' /></svg>
              </div>
              <div className='script-body'>
                <div className='script-name'>{script.name}</div>
                <div className='script-preview'>"{script.text?.slice(0, 120)}..."</div>
                <div className='script-meta'>
                  {script.category && <span>{script.category}</span>}
                  {script.product_name && <span>{script.product_name}</span>}
                  {script.created_at && <span>{formatDate(script.created_at)}</span>}
                </div>
              </div>
              <div className='script-actions'>
                <Link href={`/create?script_id=${script.id}`} className='script-action-btn primary' style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>Use</Link>
                <button className='script-action-btn ghost' onClick={() => window.alert('Editing functionality coming soon.')}>Edit</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
