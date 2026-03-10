'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/utils';

interface Clip {
  id: string;
  name: string;
  aspect_ratio?: string;
  duration?: number;
  created_at?: string;
  thumbnail_url?: string;
  video_url?: string;
  campaign_name?: string;
}

export default function AppClipsPage() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const fetchClips = useCallback(async () => {
    try {
      const data = await apiFetch<Clip[]>('/app-clips');
      setClips(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchClips(); }, [fetchClips]);

  const filtered = clips.filter(c =>
    (c.name || '').toLowerCase().includes(search.toLowerCase())
  );

  const formatDate = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'numeric', day: 'numeric', year: 'numeric' });

  return (
    <div className='content-area'>
      <div className='page-header'>
        <h1>App Clips</h1>
        <p>Short-form clips optimised for app store previews and ads.</p>
      </div>

      <div className='asset-toolbar'>
        <div className='asset-toolbar-left'>
          <div className='search-box'>
            <svg viewBox='0 0 24 24'><circle cx='11' cy='11' r='8' /><line x1='21' y1='21' x2='16.65' y2='16.65' /></svg>
            <input type='text' placeholder='Search app clips...' value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>
        <Link href='/create' className='btn-create'>
          <svg viewBox='0 0 24 24'><line x1='12' y1='5' x2='12' y2='19' /><line x1='5' y1='12' x2='19' y2='12' /></svg>
          New App Clip
        </Link>
      </div>

      {loading ? (
        <div className='empty-state'><div className='empty-title'>Loading clips...</div></div>
      ) : filtered.length === 0 ? (
        <div className='empty-state'>
          <div className='empty-icon'>
            <svg viewBox='0 0 24 24'><rect x='5' y='2' width='14' height='20' rx='2' /><line x1='12' y1='18' x2='12.01' y2='18' /></svg>
          </div>
          <div className='empty-title'>No app clips yet</div>
          <div className='empty-sub'>App clips are short-form versions of your videos optimised for app store previews.</div>
          <Link href='/create' className='btn-primary'>Create Clip</Link>
        </div>
      ) : (
        <div className='video-grid'>
          {filtered.map((clip, i) => (
            <div key={clip.id} className='video-card'>
              <div className={`video-thumb grad-${(i % 5) + 1}`} style={clip.thumbnail_url ? { backgroundImage: `url(${clip.thumbnail_url})` } : {}}>
                {clip.video_url && (
                  <video src={clip.video_url} style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0 }} muted loop playsInline />
                )}
                <span className='status-pill done absolute top-2 right-2 px-2 py-0.5 rounded-full text-[10px] font-bold bg-[var(--blue)] text-white z-10'>{clip.duration ? `${clip.duration}s` : 'Clip'}</span>
              </div>
              <div className='video-info'>
                <div className='video-name'>{clip.name || clip.campaign_name || 'Untitled Clip'}</div>
                <div className='video-date'>{clip.created_at ? formatDate(clip.created_at) : ''}  {clip.aspect_ratio || '9:16'}</div>
              </div>
              <div className='video-info flex p-2 border-t border-[var(--border-soft)]'>
                <button className='flex-1 py-1.5 bg-[var(--blue-light)] text-[var(--blue)] rounded text-xs font-semibold' onClick={() => window.open(clip.video_url || '')}>Download</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
