'use client';
import { useState, useEffect, useCallback, useRef } from 'react';
import { apiFetch } from '@/lib/utils';
import { Script, Influencer, Product, ScriptJSON, ScriptScene } from '@/lib/types';

/* ── constants ─────────────────────────────────────────────── */
const METHODOLOGIES = [
  { id: 'Problem/Agitate/Solve', label: 'Problem / Agitate / Solve', desc: 'Identify pain, amplify it, then present the product as the solution.', color: '#EF4444' },
  { id: 'Hook/Benefit/CTA', label: 'Hook / Benefit / CTA', desc: 'Grab attention, deliver the key benefit, and drive action.', color: '#F59E0B' },
  { id: 'Contrarian/Shock', label: 'Contrarian / Shock', desc: 'Open with a statement that challenges conventional wisdom.', color: '#8B5CF6' },
  { id: 'Social Proof', label: 'Social Proof', desc: 'Lead with a real result or experience to build instant credibility.', color: '#22C55E' },
  { id: 'Aspiration/Dream', label: 'Aspiration / Dream', desc: 'Paint a picture of the desired outcome before revealing the product.', color: '#0EA5E9' },
  { id: 'Curiosity/Cliffhanger', label: 'Curiosity / Cliffhanger', desc: 'Open a loop the viewer must watch to close.', color: '#EC4899' },
];
const CSV_COLS = [
  { name: 'hook', desc: 'Opening line of the script', req: true },
  { name: 'category', desc: 'E-commerce, Mobile Apps, Lifestyle...', req: true },
  { name: 'methodology', desc: 'Problem/Agitate/Solve, Hook/Benefit/CTA...', req: true },
  { name: 'video_length', desc: '15 or 30 (seconds)', req: true },
  { name: 'scene_1_dialogue', desc: 'Full spoken text for scene 1', req: true },
  { name: 'scene_1_visual_cue', desc: 'Director note for scene 1', req: false },
  { name: 'scene_2_dialogue', desc: 'Full spoken text for scene 2', req: true },
  { name: 'scene_2_visual_cue', desc: 'Director note for scene 2', req: false },
  { name: 'scene_3_dialogue', desc: 'Scene 3 (30s scripts only)', req: false },
  { name: 'scene_3_visual_cue', desc: 'Director note for scene 3', req: false },
  { name: 'scene_4_dialogue', desc: 'Scene 4 / CTA (30s scripts only)', req: false },
  { name: 'scene_4_visual_cue', desc: 'Director note for scene 4', req: false },
  { name: 'influencer', desc: 'Influencer name to link script to', req: false },
];

interface CsvRow { hook:string; category:string; methodology:string; video_length:string; scenes:{dialogue:string;visual_cue:string}[]; influencer:string; status:'ok'|'warn'|'err'; statusMsg:string; }

/* ── helpers ───────────────────────────────────────────────── */
function getHook(s: Script): string { return s.script_json?.hook || s.text?.split('|||')[0]?.trim() || s.name || 'Untitled'; }
function fmtDate(d?: string) { if (!d) return ''; try { return new Date(d).toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}); } catch { return ''; } }
function getMethodColor(m?: string) { return METHODOLOGIES.find(x => x.id === m)?.color || '#8B5CF6'; }

function downloadTemplate() {
  const h = CSV_COLS.map(c => c.name).join(',');
  const ex = ['"I stopped buying skincare products until I found this."','Health & Beauty','Problem/Agitate/Solve','30','"I stopped buying skincare products until I found this."','Close-up of influencer holding product.','"I was spending so much on products that didn\'t work."','Influencer gesturing in frustration.','"Then I tried Glow Serum Pro. Three drops."','Influencer applying product.','"Link in my bio. First order ships free."','Influencer smiling, product held up.','Sofia Reyes'].join(',');
  const blob = new Blob([h+'\n'+ex], {type:'text/csv'});
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'ugc_scripts_template.csv'; a.click(); URL.revokeObjectURL(a.href);
}

function parseCsv(text: string): CsvRow[] {
  const lines = text.split('\n').filter(l => l.trim());
  if (lines.length < 2) return [];
  return lines.slice(1).map(line => {
    const cols: string[] = []; let cur = ''; let inQ = false;
    for (const ch of line) { if (ch === '"') { inQ = !inQ; } else if (ch === ',' && !inQ) { cols.push(cur.trim()); cur = ''; } else { cur += ch; } }
    cols.push(cur.trim());
    const scenes: {dialogue:string;visual_cue:string}[] = [];
    for (let i = 0; i < 4; i++) { const d = cols[4+i*2] || ''; const v = cols[5+i*2] || ''; if (d) scenes.push({dialogue:d,visual_cue:v}); }
    const hook = cols[0] || ''; const cat = cols[1] || ''; const meth = cols[2] || ''; const vl = cols[3] || '';
    let status: 'ok'|'warn'|'err' = 'ok'; let statusMsg = 'Ready';
    if (!hook || !cat || !meth || !vl || scenes.length === 0) { status = 'err'; statusMsg = 'Missing required fields'; }
    else if (scenes.some(s => !s.visual_cue)) { status = 'warn'; statusMsg = 'Missing visual cues'; }
    return { hook, category: cat, methodology: meth, video_length: vl, scenes, influencer: cols[12]||'', status, statusMsg };
  });
}

/* ── icons (inline SVG helpers) ────────────────────────────── */
const IconSearch = () => <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>;
const IconDoc = () => <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>;
const IconPlus = () => <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>;
const IconTrend = () => <svg viewBox="0 0 24 24"><polyline points="23,6 13.5,15.5 8.5,10.5 1,18"/><polyline points="17,6 23,6 23,12"/></svg>;
const IconChevDown = () => <svg viewBox="0 0 24 24"><polyline points="6,9 12,15 18,9"/></svg>;
const IconX = () => <svg viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>;
const IconTrash = () => <svg viewBox="0 0 24 24"><polyline points="3,6 5,6 21,6"/><path d="M19,6v14a2,2,0,0,1-2,2H7a2,2,0,0,1-2-2V6m3,0V4a2,2,0,0,1,2-2h4a2,2,0,0,1,2,2v2"/></svg>;
const IconDl = () => <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7,10 12,15 17,10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>;
const IconUpload = () => <svg viewBox="0 0 24 24"><polyline points="16,16 12,12 8,16"/><line x1="12" y1="12" x2="12" y2="21"/><path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/></svg>;
const IconCheck = () => <svg viewBox="0 0 24 24"><polyline points="20,6 9,17 4,12"/></svg>;
const IconSpin = () => <svg viewBox="0 0 24 24" className="spin-anim"><path d="M21 12a9 9 0 1 1-6.219-8.56"/></svg>;
const IconClock = () => <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12,6 12,12 16,14"/></svg>;
const IconUser = () => <svg viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>;

/* ================================================================
   MAIN COMPONENT
================================================================ */
export default function ScriptsPage() {
  const [scripts, setScripts] = useState<Script[]>([]);
  const [influencers, setInfluencers] = useState<Influencer[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [methFilter, setMethFilter] = useState('');
  const [lenFilter, setLenFilter] = useState('');
  const [infFilter, setInfFilter] = useState('');
  const [sortBy, setSortBy] = useState('created_at_desc');

  // UI
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalTab, setModalTab] = useState<'ai'|'manual'|'csv'>('ai');
  const [trendModalOpen, setTrendModalOpen] = useState(false);
  const [trendingDismissed, setTrendingDismissed] = useState(false);
  const [toast, setToast] = useState<{msg:string;visible:boolean}>({msg:'',visible:false});

  // Edit modal
  const [editOpen, setEditOpen] = useState(false);
  const [editId, setEditId] = useState<string|null>(null);
  const [editCat, setEditCat] = useState('');
  const [editMeth, setEditMeth] = useState('');
  const [editLen, setEditLen] = useState(15);
  const [editScenes, setEditScenes] = useState<{dialogue:string;visual_cue:string}[]>([]);
  const [editSaving, setEditSaving] = useState(false);

  // AI Generate
  const [aiProd, setAiProd] = useState('');
  const [aiInf, setAiInf] = useState('');
  const [aiLen, setAiLen] = useState(15);
  const [aiMeth, setAiMeth] = useState('Problem/Agitate/Solve');
  const [aiCtx, setAiCtx] = useState('');
  const [aiGenerating, setAiGenerating] = useState(false);
  const [aiPreview, setAiPreview] = useState<ScriptJSON | null>(null);

  // Manual
  const [manCat, setManCat] = useState('E-commerce');
  const [manMeth, setManMeth] = useState('Problem/Agitate/Solve');
  const [manLen, setManLen] = useState(15);
  const [manInf, setManInf] = useState('');
  const sceneCount = manLen === 30 ? 4 : 2;
  const [manScenes, setManScenes] = useState<{dialogue:string;visual_cue:string}[]>([{dialogue:'',visual_cue:''},{dialogue:'',visual_cue:''}]);

  // CSV
  const fileRef = useRef<HTMLInputElement>(null);
  const [csvRows, setCsvRows] = useState<CsvRow[]>([]);
  const [csvFileName, setCsvFileName] = useState('');
  const [csvImporting, setCsvImporting] = useState(false);
  const [csvDone, setCsvDone] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  // Trending
  const [trendTopic, setTrendTopic] = useState('E-commerce');
  const [trendPlatform, setTrendPlatform] = useState('All Platforms');
  const [trendSources, setTrendSources] = useState<string[]>(['tiktok','instagram']);
  const [trendPhase, setTrendPhase] = useState<'config'|'progress'>('config');
  const [trendStep, setTrendStep] = useState(0);

  /* ── data fetch ──────────────────────────────────────────── */
  const fetchScripts = useCallback(async () => {
    try {
      const p = new URLSearchParams();
      if (catFilter) p.append('category', catFilter);
      if (methFilter) p.append('methodology', methFilter);
      if (lenFilter) p.append('video_length', lenFilter);
      if (infFilter) p.append('influencer_id', infFilter);
      if (sortBy) p.append('sort_by', sortBy);
      if (search) p.append('search', search);
      const qs = p.toString();
      const data = await apiFetch<Script[]>(`/api/scripts${qs ? '?'+qs : ''}`);
      setScripts(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [catFilter, methFilter, lenFilter, infFilter, sortBy, search]);

  useEffect(() => { fetchScripts(); }, [fetchScripts]);
  useEffect(() => {
    (async () => {
      try {
        const [inf, prod] = await Promise.all([apiFetch<Influencer[]>('/influencers'), apiFetch<Product[]>('/api/products')]);
        setInfluencers(inf); setProducts(prod);
      } catch (e) { console.error(e); }
    })();
  }, []);

  // Adjust manual scenes when length changes
  useEffect(() => {
    setManScenes(prev => {
      const target = manLen === 30 ? 4 : 2;
      if (prev.length === target) return prev;
      if (prev.length < target) return [...prev, ...Array(target - prev.length).fill({dialogue:'',visual_cue:''})];
      return prev.slice(0, target);
    });
  }, [manLen]);

  /* ── handlers ────────────────────────────────────────────── */
  async function handleDelete(id: string) {
    if (!confirm('Delete this script? This cannot be undone.')) return;
    try { await apiFetch(`/api/scripts/${id}`, {method:'DELETE'}); setScripts(prev => prev.filter(s => s.id !== id)); } catch (e) { console.error(e); }
  }
  function handleUse(id: string) {
    apiFetch(`/api/scripts/${id}/use`, {method:'POST'}).catch(()=>{});
    window.location.href = `/create?script_id=${id}`;
  }
  function openEdit(script: Script) {
    setEditId(script.id);
    setEditCat(script.category || 'General');
    setEditMeth(script.methodology || 'Hook/Benefit/CTA');
    setEditLen(script.video_length || 15);
    const scenes = script.script_json?.scenes || [];
    setEditScenes(scenes.map((sc: ScriptScene) => ({ dialogue: sc.dialogue || '', visual_cue: sc.visual_cue || '' })));
    setEditOpen(true);
  }
  async function saveEdit() {
    if (!editId) return;
    setEditSaving(true);
    try {
      const updatedScenes = editScenes.map((sc, i) => ({
        scene_number: i + 1,
        scene_title: i === 0 ? 'Hook' : i === editScenes.length - 1 ? 'CTA' : `Scene ${i+1}`,
        dialogue: sc.dialogue,
        word_count: sc.dialogue.split(/\s+/).filter(Boolean).length,
        estimated_duration_sec: 7.0,
        visual_cue: sc.visual_cue,
        on_screen_text: '',
      }));
      const hook = editScenes[0]?.dialogue || '';
      const scriptJson = { hook, methodology: editMeth, target_duration_sec: editLen, scenes: updatedScenes };
      await apiFetch(`/api/scripts/${editId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: hook.slice(0, 80), category: editCat, methodology: editMeth, video_length: editLen, script_json: scriptJson }),
      });
      setEditOpen(false);
      fetchScripts();
      setToast({ msg: 'Script updated successfully!', visible: true });
      setTimeout(() => setToast(t => ({ ...t, visible: false })), 3000);
    } catch (err: unknown) { alert('Save failed: ' + (err instanceof Error ? err.message : String(err))); }
    setEditSaving(false);
  }
  async function handleAIGenerate() {
    if (!aiProd) { alert('Please select a product.'); return; }
    setAiGenerating(true); setAiPreview(null);
    try {
      const body: Record<string,unknown> = { product_id: aiProd, duration: aiLen, output_format: 'json', methodology: aiMeth };
      if (aiInf) body.influencer_id = aiInf;
      if (aiCtx) body.context = aiCtx;
      const res = await apiFetch<{script_json:ScriptJSON}>('/api/scripts/generate', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body) });
      setAiPreview(res.script_json);
    } catch (err: unknown) { alert('Generation failed: ' + (err instanceof Error ? err.message : String(err))); }
    setAiGenerating(false);
  }
  async function handleSaveAI() {
    if (!aiPreview) return;
    try {
      await apiFetch('/api/scripts', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ name: aiPreview.name||'AI Script', script_json: aiPreview, category: 'General', methodology: aiPreview.methodology||aiMeth, video_length: aiLen, source:'ai_generated', product_id: aiProd||undefined, influencer_id: aiInf||undefined }) });
      setModalOpen(false); setAiPreview(null); fetchScripts();
    } catch (err: unknown) { alert('Save failed: ' + (err instanceof Error ? err.message : String(err))); }
  }
  async function handleManualSave() {
    if (!manScenes[0]?.dialogue?.trim()) { alert('Scene 1 dialogue is required.'); return; }
    const sj: ScriptJSON = { name: manScenes[0].dialogue.slice(0,60), hook: manScenes[0].dialogue, target_duration_sec: manLen, methodology: manMeth, scenes: manScenes.map((s,i) => ({ scene_number:i+1, scene_title: i===0?'Hook':i===sceneCount-1?'CTA':`Scene ${i+1}`, dialogue:s.dialogue, word_count:s.dialogue.split(' ').filter(Boolean).length, estimated_duration_sec:7.0, visual_cue:s.visual_cue })) };
    try {
      await apiFetch('/api/scripts', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ name:sj.name, script_json:sj, category:manCat, methodology:manMeth, video_length:manLen, source:'manual', influencer_id:manInf||undefined }) });
      setModalOpen(false); setManScenes([{dialogue:'',visual_cue:''},{dialogue:'',visual_cue:''}]); fetchScripts();
    } catch (err: unknown) { alert('Save failed: ' + (err instanceof Error ? err.message : String(err))); }
  }
  function handleCsvFile(file: File) {
    if (!file.name.endsWith('.csv')) return;
    setCsvFileName(file.name); setCsvDone(false);
    const reader = new FileReader();
    reader.onload = (e) => { const rows = parseCsv(e.target?.result as string); setCsvRows(rows); };
    reader.readAsText(file);
  }
  async function handleCsvImport() {
    setCsvImporting(true);
    const items = csvRows.filter(r => r.status !== 'err').map(r => ({
      script_json: { name: r.hook.slice(0,60), hook: r.hook, target_duration_sec: parseInt(r.video_length)||15, methodology: r.methodology, scenes: r.scenes.map((s,i) => ({ scene_number:i+1, scene_title:i===0?'Hook':`Scene ${i+1}`, dialogue:s.dialogue, word_count:s.dialogue.split(' ').filter(Boolean).length, estimated_duration_sec:7.0, visual_cue:s.visual_cue })) },
      category: r.category, methodology: r.methodology, video_length: parseInt(r.video_length)||15, source: 'csv_upload',
    }));
    try { await apiFetch('/api/scripts/bulk', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(items) }); setCsvDone(true); fetchScripts(); } catch (err: unknown) { alert('Import failed: ' + (err instanceof Error ? err.message : String(err))); }
    setCsvImporting(false);
  }
  async function handleTrendingScan() {
    setTrendPhase('progress'); setTrendStep(0);
    const prevCount = scripts.length;
    try {
      // Animate progress steps while waiting
      const interval = setInterval(() => setTrendStep(s => { if (s >= 3) { clearInterval(interval); return 3; } return s+1; }), 1500);
      // Fire the scan (backend runs it async in a background thread)
      await apiFetch('/api/scripts/find-trending', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({ topic: trendTopic, sources: trendSources }) });
      // Poll every 2 seconds until new scripts appear or 30s timeout
      let elapsed = 0;
      const poller = setInterval(async () => {
        elapsed += 2000;
        try {
          const fresh = await apiFetch<Script[]>('/api/scripts?sort_by=created_at_desc');
          if (fresh.length > prevCount || elapsed >= 30000) {
            clearInterval(poller); clearInterval(interval);
            setTrendStep(4);
            const newCount = fresh.length - prevCount;
            // Small delay so user sees the final checkmark
            setTimeout(() => {
              setTrendModalOpen(false); setTrendPhase('config'); setTrendStep(0);
              setTrendingDismissed(false);
              setScripts(fresh);
              if (newCount > 0) {
                setToast({msg: `${newCount} new trending script${newCount!==1?'s':''} added to your library!`, visible: true});
                setTimeout(() => setToast(t => ({...t, visible: false})), 4000);
              }
            }, 800);
          }
        } catch { /* ignore poll errors */ }
      }, 2000);
    } catch { setTrendStep(4); }
  }

  /* ── computed ─────────────────────────────────────────────── */
  const categories = [...new Set(scripts.map(s => s.category).filter(Boolean))] as string[];
  const totalScripts = scripts.length;
  const uniqueCats = categories.length;
  const uniqueMeths = [...new Set(scripts.map(s => s.methodology).filter(Boolean))].length;
  const usedInVideos = scripts.filter(s => (s.times_used||0) > 0).length;
  const trendingCount = scripts.filter(s => s.is_trending).length;

  // Scene title helper
  const sceneTitle = (i: number, total: number) => {
    if (i === 0) return 'Hook';
    if (i === total - 1) return 'CTA';
    if (total === 4 && i === 1) return 'Problem / Agitate';
    if (total === 4 && i === 2) return 'Solution / Demo';
    return `Scene ${i+1}`;
  };

  /* ── RENDER ──────────────────────────────────────────────── */
  return (
    <div className="scripts-page-wrapper">
      {/* ═══ SIDEBAR ═══ */}
      <aside className="scripts-sidebar">
        <div className="sb-section">
          <div className="sb-label">Search</div>
          <div className="sb-search-wrap">
            <IconSearch />
            <input className="sb-search" type="text" placeholder="Search scripts..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>
        <div className="sb-section">
          <div className="sb-label">Category</div>
          <div className="filter-group">
            <button className={`fc${!catFilter?' active':''}`} onClick={() => setCatFilter('')}>
              <span className="fc-left">All Scripts</span><span className="fc-count">{totalScripts}</span>
            </button>
            {categories.map(c => (
              <button key={c} className={`fc${catFilter===c?' active':''}`} onClick={() => setCatFilter(catFilter===c?'':c)}>
                <span className="fc-left">{c}</span><span className="fc-count">{scripts.filter(s=>s.category===c).length}</span>
              </button>
            ))}
          </div>
        </div>
        <div className="sb-section">
          <div className="sb-label">Methodology</div>
          <div className="filter-group">
            <button className={`mp${!methFilter?' active':''}`} onClick={() => setMethFilter('')}>
              <div className="mp-dot" style={{background:'var(--blue)'}} /> All Methods
            </button>
            {METHODOLOGIES.map(m => (
              <button key={m.id} className={`mp${methFilter===m.id?' active':''}`} onClick={() => setMethFilter(methFilter===m.id?'':m.id)}>
                <div className="mp-dot" style={{background:m.color}} /> {m.label}
              </button>
            ))}
          </div>
        </div>
        <div className="sb-section">
          <div className="sb-label">Video Length</div>
          <div className="filter-group">
            <button className={`fc${lenFilter==='15'?' active':''}`} onClick={() => setLenFilter(lenFilter==='15'?'':'15')}>
              <span className="fc-left"><IconClock /> 15 seconds</span><span className="fc-count">{scripts.filter(s=>(s.video_length||15)===15).length}</span>
            </button>
            <button className={`fc${lenFilter==='30'?' active':''}`} onClick={() => setLenFilter(lenFilter==='30'?'':'30')}>
              <span className="fc-left"><IconClock /> 30 seconds</span><span className="fc-count">{scripts.filter(s=>s.video_length===30).length}</span>
            </button>
          </div>
        </div>
        <div className="sb-section">
          <div className="sb-label">Influencer</div>
          <div className="filter-group">
            {influencers.map(inf => (
              <button key={inf.id} className={`fc${infFilter===inf.id?' active':''}`} onClick={() => setInfFilter(infFilter===inf.id?'':inf.id)}>
                <span className="fc-left"><IconUser /> {inf.name}</span>
                <span className="fc-count">{scripts.filter(s=>s.influencer_id===inf.id).length}</span>
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* ═══ MAIN ═══ */}
      <main className="scripts-main">
        {/* Page header */}
        <div className="sp-header">
          <div><h1>Scripts</h1><p>Your library of structured UGC video scripts, organised by methodology and category.</p></div>
          <div className="sp-header-actions">
            <button className="btn-find-trending" onClick={() => { setTrendModalOpen(true); setTrendPhase('config'); }}>
              <IconTrend /> Find Trending Scripts
            </button>
            <button className="btn-new-script" onClick={() => { setModalOpen(true); setModalTab('ai'); setAiPreview(null); }}>
              <IconPlus /> New Script
            </button>
          </div>
        </div>

        {/* Stats */}
        <div className="sp-stats">
          <div className="sp-stat"><span className="sp-stat-val">{totalScripts}</span><span className="sp-stat-lbl">Total Scripts</span></div>
          <div className="sp-stat-div" />
          <div className="sp-stat"><span className="sp-stat-val">{uniqueCats}</span><span className="sp-stat-lbl">Categories</span></div>
          <div className="sp-stat-div" />
          <div className="sp-stat"><span className="sp-stat-val">{uniqueMeths}</span><span className="sp-stat-lbl">Methodologies</span></div>
          <div className="sp-stat-div" />
          <div className="sp-stat"><span className="sp-stat-val">{usedInVideos}</span><span className="sp-stat-lbl">Used in Videos</span></div>
          <div className="sp-stat-div" />
          <div className="sp-stat"><span className="sp-stat-val" style={{color:'var(--green)'}}>{trendingCount}</span><span className="sp-stat-lbl">Trending Added</span></div>
        </div>

        {/* Trending banner */}
        <div className="sp-trending-banner">
          <div className="sp-trending-left">
            <div className="sp-trending-icon"><IconTrend /></div>
            <div className="sp-trending-text">
              {trendingCount > 0 && !trendingDismissed ? (
                <><h3>{trendingCount} new trending script{trendingCount!==1?'s':''} discovered this week</h3>
                <p>AI scraped TikTok, Instagram Reels and YouTube Shorts for the latest high-performing hooks in E-commerce and Mobile Apps.</p></>
              ) : (
                <><h3>Discover trending scripts from top-performing ads</h3>
                <p>Scan TikTok, Instagram Reels, YouTube Shorts and ad intelligence blogs for high-performing hooks.</p></>
              )}
            </div>
          </div>
          <button className="btn-trending" onClick={trendingCount > 0 && !trendingDismissed ? () => {
            setTrendingDismissed(true);
            setToast({msg: `${trendingCount} trending script${trendingCount!==1?'s are':' is'} already in your library below. Look for the green "Trending" tag.`, visible: true});
            setTimeout(() => setToast(t => ({...t, visible: false})), 4000);
            window.scrollTo({top: 0, behavior: 'smooth'});
          } : () => { setTrendModalOpen(true); setTrendPhase('config'); }}>
            <IconTrend /> {trendingCount > 0 && !trendingDismissed ? 'View Trending' : 'Scan Now'}
          </button>
        </div>

        {/* Toolbar */}
        <div className="sp-toolbar">
          <div className="sp-toolbar-search">
            <IconSearch />
            <input type="text" placeholder="Search scripts by hook, product, or influencer..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="sp-sort" value={sortBy} onChange={e => setSortBy(e.target.value)}>
            <option value="created_at_desc">Newest First</option>
            <option value="times_used_desc">Most Used</option>
            <option value="name_asc">A -- Z</option>
          </select>
        </div>

        {/* Script list */}
        {loading ? (
          <div className="empty-state"><div className="empty-title">Loading scripts...</div></div>
        ) : scripts.length === 0 ? (
          <div className="empty-state">
            <div className="empty-icon"><IconDoc /></div>
            <div className="empty-title">No scripts found</div>
            <div className="empty-sub">Create your first script using AI or write one manually.</div>
            <button className="btn-primary" onClick={() => { setModalOpen(true); setModalTab('ai'); }}>Create Script</button>
          </div>
        ) : (
          <div className="sp-list">
            {scripts.map(script => {
              const isExp = expandedId === script.id;
              const hook = getHook(script);
              const scenes = script.script_json?.scenes || [];
              const prod = products.find(p => p.id === script.product_id);
              const inf = influencers.find(i => i.id === script.influencer_id);
              return (
                <div key={script.id} className={`sp-card${isExp?' expanded':''}${script.is_trending?' trending':''}`}>
                  <div className="sp-card-head" onClick={() => setExpandedId(isExp ? null : script.id)}>
                    <div className="sp-card-icon" style={{background: script.is_trending ? '#F0FDF4' : 'var(--blue-light)', color: script.is_trending ? '#16A34A' : 'var(--blue)'}}>
                      {script.is_trending ? <IconTrend /> : <IconDoc />}
                    </div>
                    <div className="sp-card-meta">
                      <div className="sp-card-hook">&ldquo;{hook}&rdquo;</div>
                      <div className="sp-card-tags">
                        {script.category && <span className="sp-tag sp-tag-cat">{script.category}</span>}
                        {script.methodology && <span className="sp-tag sp-tag-method">{script.methodology}</span>}
                        <span className="sp-tag sp-tag-len">{script.video_length || 15}s</span>
                        {inf && <span className="sp-tag sp-tag-inf">{inf.name}</span>}
                        {prod && <span className="sp-tag sp-tag-prod">{prod.name}</span>}
                        {script.is_trending && <span className="sp-tag sp-tag-trending"><IconTrend /> Trending</span>}
                      </div>
                    </div>
                    <div className="sp-card-actions" onClick={e => e.stopPropagation()}>
                      <span className="sp-card-date">{fmtDate(script.created_at)}</span>
                      <button className="btn-use" onClick={() => handleUse(script.id)}>Use</button>
                      <button className="btn-edit" onClick={() => openEdit(script)}>Edit</button>
                      <button className="btn-icon-del" onClick={() => handleDelete(script.id)}><IconTrash /></button>
                      <button className={`sp-expand${isExp?' open':''}`} onClick={() => setExpandedId(isExp ? null : script.id)}>
                        <IconChevDown />
                      </button>
                    </div>
                  </div>
                  <div className={`sp-body${isExp?' open':''}`}>
                    {scenes.length > 0 ? (
                      <>
                        <div className="sp-body-grid">
                          {scenes.map((sc: ScriptScene, i: number) => (
                            <div key={i} className="sp-scene">
                              <div className="sp-scene-head">
                                <span className="sp-scene-label">Scene {sc.scene_number} -- {sc.scene_title || sceneTitle(i, scenes.length)}</span>
                                <span className="sp-scene-badge">{i*7} -- {i*7+7}s</span>
                              </div>
                              <div className="sp-scene-text">&ldquo;{sc.dialogue}&rdquo;</div>
                              {sc.visual_cue && <div className="sp-scene-cue"><strong>Visual:</strong> {sc.visual_cue}</div>}
                            </div>
                          ))}
                        </div>
                        {script.methodology && (
                          <div className="sp-methodology">
                            <div className="sp-m-title">Methodology: {script.methodology}</div>
                            <p>{METHODOLOGIES.find(m=>m.id===script.methodology)?.desc || 'Custom methodology applied to this script.'}</p>
                          </div>
                        )}
                      </>
                    ) : script.text ? (
                      <div>{script.text.split('|||').map((part,i) => (
                        <div key={i} className="sp-scene" style={{marginBottom:'10px'}}>
                          <div className="sp-scene-label">Part {i+1}</div>
                          <div className="sp-scene-text">&ldquo;{part.trim()}&rdquo;</div>
                        </div>
                      ))}</div>
                    ) : <div style={{color:'var(--text-3)',fontSize:'13px'}}>No scene data available.</div>}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* ═══ NEW SCRIPT MODAL ═══ */}
      {modalOpen && (
        <div className="sp-modal-overlay" onClick={() => setModalOpen(false)}>
          <div className="sp-modal" onClick={e => e.stopPropagation()}>
            <div className="sp-modal-head">
              <h3>New Script</h3>
              <button className="sp-expand" onClick={() => setModalOpen(false)}><IconX /></button>
            </div>
            <div className="sp-modal-body">
              <div className="sp-tabs">
                {(['ai','manual','csv'] as const).map(t => (
                  <button key={t} className={`sp-tab${modalTab===t?' active':''}`} onClick={() => { setModalTab(t); setAiPreview(null); setCsvRows([]); setCsvDone(false); }}>
                    {t==='ai'?'AI Generate':t==='manual'?'Write Manually':'Bulk Upload (CSV)'}
                  </button>
                ))}
              </div>

              {/* ── AI TAB ── */}
              {modalTab === 'ai' && (
                <div>
                  <div className="ai-panel">
                    <div className="ai-panel-head">
                      <div className="ai-panel-ico"><IconDoc /></div>
                      <div><h4>AI Script Generator</h4><p>Configure your script and let AI generate a human-sounding, methodology-driven script in seconds.</p></div>
                    </div>
                    <div className="ai-config">
                      <div><label className="sp-form-label">Product<span className="req">*</span></label><select className="sp-input" value={aiProd} onChange={e=>setAiProd(e.target.value)}><option value="">Select a product...</option>{products.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}</select></div>
                      <div><label className="sp-form-label">Influencer<span className="req">*</span></label><select className="sp-input" value={aiInf} onChange={e=>setAiInf(e.target.value)}><option value="">Select an influencer...</option>{influencers.map(i=><option key={i.id} value={i.id}>{i.name}</option>)}</select></div>
                      <div><label className="sp-form-label">Video Length<span className="req">*</span></label><select className="sp-input" value={aiLen} onChange={e=>setAiLen(Number(e.target.value))}><option value={15}>15 seconds</option><option value={30}>30 seconds</option></select></div>
                    </div>
                    <div><label className="sp-form-label">Script Methodology<span className="req">*</span></label>
                      <div className="method-sel">
                        {METHODOLOGIES.map(m=>(
                          <button key={m.id} className={`method-card${aiMeth===m.id?' selected':''}`} onClick={()=>setAiMeth(m.id)}>
                            <div className="mc-name">{m.label}</div><div className="mc-desc">{m.desc}</div>
                          </button>
                        ))}
                      </div>
                    </div>
                    <div className="sp-form-group">
                      <label className="sp-form-label">Additional Context (optional)</label>
                      <textarea className="sp-input" placeholder="Any specific angles, key benefits, or talking points you want the script to include..." value={aiCtx} onChange={e=>setAiCtx(e.target.value)} />
                    </div>
                    <button className="btn-gen-ai" disabled={aiGenerating} onClick={handleAIGenerate}>
                      {aiGenerating ? <><IconSpin /> Generating...</> : <><IconClock /> Generate Script</>}
                    </button>
                  </div>
                  {aiPreview && (
                    <div className="sp-preview">
                      <div className="sp-preview-head"><h4>Generated Script Preview</h4><button className="btn-secondary" style={{fontSize:'12px',padding:'6px 12px'}} onClick={handleAIGenerate}>Regenerate</button></div>
                      {aiPreview.scenes?.map((sc,i) => (
                        <div key={i} className="sp-prev-scene">
                          <div className="sp-prev-label">Scene {sc.scene_number} -- {sc.scene_title} ({i*7} -- {i*7+7}s)</div>
                          <div className="sp-prev-text">&ldquo;{sc.dialogue}&rdquo;</div>
                          {sc.visual_cue && <div className="sp-prev-cue">Visual: {sc.visual_cue}</div>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* ── MANUAL TAB ── */}
              {modalTab === 'manual' && (
                <div>
                  <div className="sp-form-row">
                    <div><label className="sp-form-label">Category<span className="req">*</span></label><select className="sp-input" value={manCat} onChange={e=>setManCat(e.target.value)}><option>E-commerce</option><option>Mobile Apps</option><option>Lifestyle</option><option>Health &amp; Beauty</option><option>Travel</option></select></div>
                    <div><label className="sp-form-label">Methodology<span className="req">*</span></label><select className="sp-input" value={manMeth} onChange={e=>setManMeth(e.target.value)}>{METHODOLOGIES.map(m=><option key={m.id} value={m.id}>{m.label}</option>)}</select></div>
                  </div>
                  <div className="sp-form-row">
                    <div><label className="sp-form-label">Video Length</label><select className="sp-input" value={manLen} onChange={e=>setManLen(Number(e.target.value))}><option value={15}>15 seconds (2 scenes)</option><option value={30}>30 seconds (4 scenes)</option></select></div>
                    <div><label className="sp-form-label">Linked Influencer</label><select className="sp-input" value={manInf} onChange={e=>setManInf(e.target.value)}><option value="">None</option>{influencers.map(i=><option key={i.id} value={i.id}>{i.name}</option>)}</select></div>
                  </div>
                  {manScenes.map((sc,i) => (
                    <div key={i}>
                      <div className="sp-form-group">
                        <label className="sp-form-label">Scene {i+1} -- {sceneTitle(i,sceneCount)} Dialogue<span className="req">*</span></label>
                        <textarea className="sp-input" placeholder={`Write the ${i===0?'opening hook line':'script for scene '+(i+1)} (~17 words for ~7s)...`} value={sc.dialogue} onChange={e => { const n=[...manScenes]; n[i]={...n[i],dialogue:e.target.value}; setManScenes(n); }} />
                      </div>
                      <div className="sp-form-group">
                        <label className="sp-form-label">Scene {i+1} -- Visual Cue</label>
                        <input type="text" className="sp-input" placeholder="Describe what the influencer is doing in this scene..." value={sc.visual_cue} onChange={e => { const n=[...manScenes]; n[i]={...n[i],visual_cue:e.target.value}; setManScenes(n); }} />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* ── CSV TAB ── */}
              {modalTab === 'csv' && (
                <div>
                  <div className="csv-banner">
                    <div className="csv-banner-left">
                      <div className="csv-banner-icon"><IconDoc /></div>
                      <div><h4>Download the CSV template</h4><p>Fill in one row per script. Required columns are marked below. Save as .csv and upload when ready.</p></div>
                    </div>
                    <button className="btn-dl-tmpl" onClick={downloadTemplate}><IconDl /> Download Template</button>
                  </div>
                  <div style={{marginBottom:'8px'}}><span className="sb-label">CSV Columns</span></div>
                  <div className="csv-cols">
                    {CSV_COLS.map(c => (
                      <div key={c.name} className="csv-col">
                        <div className="cn">{c.name}</div><div className="cd">{c.desc}</div>
                        <div className={c.req?'cr':'co'}>{c.req?'Required':'Optional'}</div>
                      </div>
                    ))}
                  </div>
                  <div className={`drop-zone${dragOver?' dragover':''}`}
                    onDragOver={e=>{e.preventDefault();setDragOver(true);}} onDragLeave={()=>setDragOver(false)}
                    onDrop={e=>{e.preventDefault();setDragOver(false);const f=e.dataTransfer.files[0];if(f)handleCsvFile(f);}}
                    onClick={()=>fileRef.current?.click()}>
                    <input ref={fileRef} type="file" accept=".csv" style={{display:'none'}} onChange={e=>{const f=e.target.files?.[0];if(f)handleCsvFile(f);}} />
                    <div className="drop-zone-icon"><IconUpload /></div>
                    <h4>Drop your CSV file here</h4>
                    <p>or click to browse your computer</p>
                    <div style={{fontSize:'11px',color:'var(--text-3)',marginTop:'10px'}}>Accepts .csv files only -- max 500 rows per upload</div>
                  </div>
                  {csvRows.length > 0 && (
                    <div style={{marginTop:'20px'}}>
                      <div style={{display:'flex',justifyContent:'space-between',marginBottom:'12px'}}>
                        <h4 style={{fontSize:'13px',fontWeight:700}}>Upload Preview</h4>
                        <span style={{fontSize:'12px',color:'var(--text-2)'}}>{csvFileName} -- {csvRows.length} rows detected</span>
                      </div>
                      <div className={`csv-status-bar ${csvRows.some(r=>r.status==='err')?'warn':'ok'}`}>
                        <IconCheck /> {csvRows.filter(r=>r.status!=='err').length} scripts ready to import{csvRows.some(r=>r.status==='warn')?' -- some rows have warnings':''}
                      </div>
                      <div className="csv-tbl-wrap">
                        <table className="csv-tbl">
                          <thead><tr><th>Row</th><th>Hook</th><th>Category</th><th>Methodology</th><th>Length</th><th>Scenes</th><th>Status</th></tr></thead>
                          <tbody>
                            {csvRows.map((r,i) => (
                              <tr key={i}>
                                <td style={{color:'var(--text-3)',fontWeight:600}}>{i+1}</td>
                                <td className="td-hook">&ldquo;{r.hook.slice(0,55)}&rdquo;</td>
                                <td>{r.category}</td><td>{r.methodology}</td><td>{r.video_length}s</td>
                                <td>{r.scenes.length} scene{r.scenes.length!==1?'s':''}</td>
                                <td><span className={`row-badge ${r.status}`}>{r.statusMsg}</span></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginTop:'14px'}}>
                        <span style={{fontSize:'12px',color:'var(--text-2)'}}>Scripts with warnings will still be imported. You can edit them after upload.</span>
                        <button className="btn-import" disabled={csvImporting||csvDone} onClick={handleCsvImport}>
                          {csvDone ? <><IconCheck /> Imported</> : csvImporting ? <><IconSpin /> Importing...</> : <><IconUpload /> Import {csvRows.filter(r=>r.status!=='err').length} Scripts</>}
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
            {modalTab !== 'csv' && (
              <div className="sp-modal-foot">
                <button className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
                {modalTab === 'ai' && aiPreview && <button className="btn-primary" onClick={handleSaveAI}>Save Script</button>}
                {modalTab === 'manual' && <button className="btn-primary" onClick={handleManualSave}>Save Script</button>}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══ TRENDING MODAL ═══ */}
      {trendModalOpen && (
        <div className="sp-modal-overlay" onClick={() => { setTrendModalOpen(false); setTrendPhase('config'); }}>
          <div className="sp-modal" style={{maxWidth:'620px'}} onClick={e => e.stopPropagation()}>
            <div className="sp-modal-head">
              <h3>Find Trending Scripts</h3>
              <button className="sp-expand" onClick={() => { setTrendModalOpen(false); setTrendPhase('config'); }}><IconX /></button>
            </div>
            <div className="sp-modal-body">
              {trendPhase === 'config' ? (
                <div>
                  <div className="sp-form-row" style={{marginBottom:'16px'}}>
                    <div><label className="sp-form-label">Category<span className="req">*</span></label><select className="sp-input" value={trendTopic} onChange={e=>setTrendTopic(e.target.value)}><option>E-commerce</option><option>Mobile Apps</option><option>Lifestyle</option><option>Health &amp; Beauty</option><option>Travel</option></select></div>
                    <div><label className="sp-form-label">Platform Focus</label><select className="sp-input" value={trendPlatform} onChange={e=>setTrendPlatform(e.target.value)}><option>All Platforms</option><option>TikTok</option><option>Instagram Reels</option><option>YouTube Shorts</option></select></div>
                  </div>
                  <label className="sp-form-label" style={{marginBottom:'10px'}}>Sources to Scan</label>
                  <div className="trend-src-grid">
                    {[{id:'tiktok',name:'TikTok Ads Library',desc:'Top-performing UGC ads',bg:'#FFF0F0',color:'#EF4444'},{id:'instagram',name:'Instagram Reels',desc:'Viral creator scripts',bg:'#FFF0F9',color:'#C026D3'},{id:'youtube',name:'YouTube Shorts',desc:'High-retention hooks',bg:'#FFF0F0',color:'#EF4444'},{id:'blogs',name:'Ad Intelligence Blogs',desc:'Motion, Foreplay, AdSpy',bg:'var(--blue-light)',color:'var(--blue)'}].map(src=>(
                      <button key={src.id} className={`trend-src${trendSources.includes(src.id)?' selected':''}`} onClick={()=>setTrendSources(prev=>prev.includes(src.id)?prev.filter(s=>s!==src.id):[...prev,src.id])}>
                        <div className="trend-src-icon" style={{background:src.bg,color:src.color}}><IconSearch /></div>
                        <div><div className="ts-name">{src.name}</div><div className="ts-desc">{src.desc}</div></div>
                      </button>
                    ))}
                  </div>
                  <button className="btn-gen-ai" onClick={handleTrendingScan}><IconTrend /> Scan for Trending Scripts</button>
                </div>
              ) : (
                <div className="prog-steps">
                  {['Scanning ad libraries','Analysing script patterns','Structuring into library format','Saving to your Scripts library'].map((step,i) => (
                    <div key={i} className="prog-step">
                      <div className={`step-dot ${trendStep>i?'done':trendStep===i?'active':'pending'}`}>
                        {trendStep>i ? <IconCheck /> : trendStep===i ? <IconSpin /> : <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/></svg>}
                      </div>
                      <div><div className="st-title">{step}</div><div className="st-sub">{trendStep>i?'Complete':trendStep===i?'In progress...':'Waiting...'}</div></div>
                    </div>
                  ))}
                </div>
              )}
            </div>
            <div className="sp-modal-foot"><button className="btn-secondary" onClick={() => { setTrendModalOpen(false); setTrendPhase('config'); }}>Cancel</button></div>
          </div>
        </div>
      )}

      {/* ═══ EDIT MODAL ═══ */}
      {editOpen && (
        <div className="sp-modal-overlay" onClick={() => setEditOpen(false)}>
          <div className="sp-modal" onClick={e => e.stopPropagation()} style={{maxWidth:'620px'}}>
            <div className="sp-modal-head">
              <h3>Edit Script</h3>
              <button className="sp-expand" onClick={() => setEditOpen(false)}><IconX /></button>
            </div>
            <div className="sp-modal-body" style={{maxHeight:'65vh',overflowY:'auto'}}>
              <div className="sp-form-row" style={{marginBottom:'16px'}}>
                <div>
                  <label className="sp-form-label">Category</label>
                  <select className="sp-input" value={editCat} onChange={e => setEditCat(e.target.value)}>
                    <option>General</option><option>E-commerce</option><option>Mobile Apps</option><option>Lifestyle</option><option>Health &amp; Beauty</option><option>Travel</option><option>Shopping</option>
                  </select>
                </div>
                <div>
                  <label className="sp-form-label">Methodology</label>
                  <select className="sp-input" value={editMeth} onChange={e => setEditMeth(e.target.value)}>
                    {METHODOLOGIES.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
                  </select>
                </div>
              </div>
              <div style={{marginBottom:'20px'}}>
                <label className="sp-form-label">Video Length</label>
                <div style={{display:'flex',gap:'10px',marginTop:'4px'}}>
                  <label style={{display:'flex',alignItems:'center',gap:'4px',fontSize:'13px',cursor:'pointer'}}>
                    <input type="radio" name="editLen" checked={editLen===15} onChange={() => setEditLen(15)} /> 15s
                  </label>
                  <label style={{display:'flex',alignItems:'center',gap:'4px',fontSize:'13px',cursor:'pointer'}}>
                    <input type="radio" name="editLen" checked={editLen===30} onChange={() => setEditLen(30)} /> 30s
                  </label>
                </div>
              </div>
              <label className="sp-form-label" style={{marginBottom:'12px',display:'block'}}>Scenes</label>
              {editScenes.map((sc, i) => (
                <div key={i} style={{background:'var(--bg-2)',borderRadius:'var(--radius-sm)',padding:'14px',marginBottom:'12px',border:'1px solid var(--border)'}}>
                  <div style={{fontSize:'11px',fontWeight:700,textTransform:'uppercase',color:'var(--text-3)',marginBottom:'8px'}}>
                    Scene {i+1} — {i===0?'Hook':i===editScenes.length-1?'CTA':`Scene ${i+1}`}
                  </div>
                  <label className="sp-form-label" style={{fontSize:'12px'}}>Dialogue</label>
                  <textarea className="sp-input" rows={3} value={sc.dialogue}
                    onChange={e => { const copy=[...editScenes]; copy[i]={...copy[i],dialogue:e.target.value}; setEditScenes(copy); }}
                    style={{width:'100%',resize:'vertical',marginBottom:'8px',fontFamily:'inherit'}} />
                  <label className="sp-form-label" style={{fontSize:'12px'}}>Visual Cue</label>
                  <input className="sp-input" type="text" value={sc.visual_cue}
                    onChange={e => { const copy=[...editScenes]; copy[i]={...copy[i],visual_cue:e.target.value}; setEditScenes(copy); }}
                    style={{width:'100%'}} />
                </div>
              ))}
            </div>
            <div className="sp-modal-foot">
              <button className="btn-secondary" onClick={() => setEditOpen(false)}>Cancel</button>
              <button className="btn-primary" onClick={saveEdit} disabled={editSaving}>
                {editSaving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ═══ TOAST ═══ */}
      {toast.visible && (
        <div className="sp-toast">
          <div className="sp-toast-icon"><IconCheck /></div>
          <span>{toast.msg}</span>
          <button className="sp-toast-close" onClick={() => setToast(t => ({...t, visible: false}))}><IconX /></button>
        </div>
      )}
    </div>
  );
}
