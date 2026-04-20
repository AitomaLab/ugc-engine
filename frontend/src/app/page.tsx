"use client";

import { useState, useEffect, useCallback, useRef, useMemo } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/utils";
import { useApp } from "@/providers/AppProvider";
import { useTranslation } from "@/lib/i18n";
import Link from "next/link";
import { createProject } from "@/lib/supabaseData";
import { creativeFetch, transcribeAudio, uploadAgentFile } from "@/lib/creative-os-api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Job {
  id: string;
  status: string;
  progress: number;
  created_at: string;
  final_video_url?: string;
  preview_url?: string;
  influencer_id?: string;
  campaign_name?: string;
  model_api?: string;
  error_message?: string;
  _source?: string;
  clone_name?: string;
}

interface Influencer {
  id: string;
  name: string;
  image_url?: string;
}

interface RecentImage {
  id: string;
  image_url?: string;
  result_url?: string;
  product_name?: string;
  created_at?: string;
  mode?: string;
}

// ---------------------------------------------------------------------------
// Campaign Grouping Helper
// ---------------------------------------------------------------------------

interface CampaignGroup {
  name: string;
  jobs: Job[];
  total: number;
  success: number;
  processing: number;
  pending: number;
  failed: number;
}

function groupByCampaign(jobs: Job[]): CampaignGroup[] {
  const map = new Map<string, Job[]>();
  for (const job of jobs) {
    const key = job.campaign_name || "Single Generation";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(job);
  }
  return Array.from(map.entries()).map(([name, jobs]) => ({
    name,
    jobs,
    total: jobs.length,
    success: jobs.filter((j) => j.status === "success").length,
    processing: jobs.filter((j) => j.status === "processing").length,
    pending: jobs.filter((j) => j.status === "pending").length,
    failed: jobs.filter((j) => j.status === "failed").length,
  }));
}

// ---------------------------------------------------------------------------
// Suggestion Chips
// ---------------------------------------------------------------------------

const SUGGESTION_CHIP_KEYS = [
  "creativeOs.dashboard.chipUgc",
  "creativeOs.dashboard.chipProductShots",
  "creativeOs.dashboard.chipCampaign",
  "creativeOs.dashboard.chipSpanish",
  "creativeOs.dashboard.chipClone",
];

// ---------------------------------------------------------------------------
// Relative Time Helper
// ---------------------------------------------------------------------------

function relativeTime(d: string, t: (k: string) => string, lang: 'en' | 'es'): string {
  const now = new Date();
  const date = new Date(d);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return t('creativeOs.dashboard.justNow');
  if (diffMins < 60) return t('creativeOs.dashboard.minutesAgo').replace('{n}', String(diffMins));
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return t('creativeOs.dashboard.hoursAgo').replace('{n}', String(diffHours));
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return t('creativeOs.dashboard.daysAgo').replace('{n}', String(diffDays));
  if (diffDays < 30) return t('creativeOs.dashboard.weeksAgo').replace('{n}', String(Math.floor(diffDays / 7)));
  return date.toLocaleDateString(lang === 'es' ? 'es-ES' : 'en-US', { day: 'numeric', month: 'short' });
}

interface MentionItem {
  type: 'product' | 'influencer';
  tag: string;
  name: string;
  image_url?: string;
  ref?: any;
}
function slugify(s: string): string {
  return (s || '').toLowerCase().trim().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '');
}

// ---------------------------------------------------------------------------
// Studio Page
// ---------------------------------------------------------------------------

export default function StudioPage() {
  const { t, lang } = useTranslation();
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [influencers, setInfluencers] = useState<Influencer[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [recentImages, setRecentImages] = useState<RecentImage[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [activeBottomTab, setActiveBottomTab] = useState<'projects' | 'videos' | 'images' | 'campaigns'>('projects');
  const { profile } = useApp();
  const userName = profile?.name || profile?.email?.split('@')[0] || 'Creator';

  // Composer state
  const [prompt, setPrompt] = useState('');
  const [seedanceOn, setSeedanceOn] = useState(false);
  const [plusMenuOpen, setPlusMenuOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Mention State
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionFilter, setMentionFilter] = useState('');
  const [mentionIndex, setMentionIndex] = useState(0);
  const [mentionCursorStart, setMentionCursorStart] = useState(-1);
  const [mentionsLoaded, setMentionsLoaded] = useState(false);
  const [mentionItems, setMentionItems] = useState<MentionItem[]>([]);
  const [activeRefs, setActiveRefs] = useState<Map<string, { type: string; tag: string; name: string; id?: string; image_url?: string }>>(new Map());

  const loadMentionData = async () => {
    if (mentionsLoaded) return;
    try {
      const { supabase } = await import('@/lib/supabaseClient');
      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = (await supabase.auth.getSession()).data.session?.access_token;
      const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
      const [prodRes, infRes] = await Promise.all([
         fetch(`${apiBase}/api/products`, { headers }).then(r => r.ok ? r.json() : []),
         fetch(`${apiBase}/influencers`, { headers }).then(r => r.ok ? r.json() : [])
      ]);
      const items: MentionItem[] = [];
      for (const p of (prodRes || [])) {
        const name = p.name || p.product_name || 'product';
        items.push({ type: 'product', tag: slugify(name), name, image_url: p.image_url, ref: p });
      }
      for (const inf of (infRes || [])) {
        const name = inf.name || 'model';
        items.push({ type: 'influencer', tag: slugify(name), name, image_url: inf.image_url, ref: inf });
      }
      setMentionItems(items);
      setMentionsLoaded(true);
    } catch (e) {
      console.warn(e);
    }
  };

  const filteredMentions = useMemo(() => {
    if (!mentionFilter) return mentionItems;
    return mentionItems.filter(m => m.tag.includes(mentionFilter) || m.name.toLowerCase().includes(mentionFilter));
  }, [mentionItems, mentionFilter]);

  const handlePromptChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    const cursor = e.target.selectionStart;
    setPrompt(val);

    const before = val.slice(0, cursor);
    const atMatch = before.match(/@([\w_]*)$/);
    if (atMatch) {
      const filter = atMatch[1].toLowerCase();
      setMentionFilter(filter);
      setMentionCursorStart(cursor - filter.length - 1);
      setMentionIndex(0);
      if (!mentionsLoaded) loadMentionData();
      setMentionOpen(true);
    } else {
      setMentionOpen(false);
    }
  };

  const finalizeMention = (item: MentionItem) => {
    const cursor = textareaRef.current?.selectionStart ?? prompt.length;
    const before = prompt.slice(0, mentionCursorStart);
    const after = prompt.slice(cursor);
    const tagText = `@${item.tag}`;
    const newPrompt = before + tagText + ' ' + after;
    setPrompt(newPrompt);
    // Track the ref for this mention so we can pass it to the project page
    setActiveRefs(prev => {
      const next = new Map(prev);
      next.set(item.tag, {
        type: item.type,
        tag: item.tag,
        name: item.name,
        id: item.ref?.id,
        image_url: item.image_url,
      });
      return next;
    });
    setMentionOpen(false);
    setTimeout(() => {
      const pos = before.length + tagText.length + 1;
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(pos, pos);
    }, 0);
  };

  const handleMentionKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (mentionOpen) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMentionIndex(i => (i + 1) % filteredMentions.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMentionIndex(i => (i - 1 + filteredMentions.length) % filteredMentions.length);
      } else if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        if (filteredMentions[mentionIndex]) finalizeMention(filteredMentions[mentionIndex]);
      } else if (e.key === 'Escape') {
        setMentionOpen(false);
      }
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const openReferenceDropdown = () => {
    const el = textareaRef.current;
    const cursor = el?.selectionStart ?? prompt.length;
    const before = prompt.slice(0, cursor);
    const after = prompt.slice(cursor);
    const newPrompt = before + '@' + after;
    setPrompt(newPrompt);
    setMentionFilter('');
    setMentionCursorStart(cursor);
    setMentionIndex(0);
    if (!mentionsLoaded) loadMentionData();
    setMentionOpen(true);
    setPlusMenuOpen(false);
    setTimeout(() => {
      const pos = cursor + 1;
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(pos, pos);
    }, 0);
  };

  // Attached files (upload-aware, mirrors AgentPanel's AttachedFile shape)
  interface DashboardAttachment {
    id: string;
    type: 'image' | 'video';
    name: string;
    status: 'uploading' | 'ready' | 'error';
    url?: string;
    tag?: string;
    previewUrl?: string;
    error?: string;
  }
  const [attachments, setAttachments] = useState<DashboardAttachment[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const removeAttachment = (id: string) => {
    setAttachments(prev => {
      const target = prev.find(a => a.id === id);
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl);
      return prev.filter(a => a.id !== id);
    });
  };

  // Voice recording state
  const [recording, setRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<BlobPart[]>([]);

  const fetchData = useCallback(async () => {
    try {
      const [jobsData, infData, projectsData, recentImgs] = await Promise.all([
        apiFetch<Job[]>("/jobs?limit=100&include_clones=true", { skipProjectScope: true }),
        apiFetch<Influencer[]>("/influencers"),
        creativeFetch<any[]>('/creative-os/projects/').catch(() => []),
        creativeFetch<RecentImage[]>('/creative-os/projects/recent-images?limit=20').catch(() => []),
      ]);
      setJobs(jobsData);
      setInfluencers(infData);
      setProjects(projectsData || []);
      setRecentImages(recentImgs || []);
    } catch (err) {
      console.error("Dashboard fetch error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return;
      fetchData();
    }, 30000);
    const onVisible = () => {
      if (document.visibilityState === 'visible') fetchData();
    };
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(interval);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [fetchData]);

  // Derived data
  const campaigns = groupByCampaign(jobs);
  const recentVideos = jobs
    .filter((j) => j.status === "success" && j.final_video_url)
    .slice(0, 20);

  // ── File attachment handling (uploads to creative-os, mirrors AgentPanel) ──
  const handleFilePicked = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    setUploadError(null);

    const accepted: { att: DashboardAttachment; file: File }[] = [];
    for (const file of Array.from(files)) {
      const ct = file.type || '';
      const kind: 'image' | 'video' | null = ct.startsWith('image/')
        ? 'image'
        : ct.startsWith('video/')
          ? 'video'
          : null;
      if (!kind) {
        setUploadError(`Unsupported file type: ${ct || 'unknown'}`);
        continue;
      }
      const id = (typeof crypto !== 'undefined' && 'randomUUID' in crypto)
        ? crypto.randomUUID()
        : `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      accepted.push({
        att: {
          id,
          type: kind,
          name: file.name,
          status: 'uploading',
          previewUrl: URL.createObjectURL(file),
        },
        file,
      });
    }
    e.target.value = '';
    if (accepted.length === 0) return;
    setAttachments(prev => [...prev, ...accepted.map(a => a.att)]);

    await Promise.all(accepted.map(async ({ att, file }) => {
      try {
        const result = await uploadAgentFile(file);
        const tag = `upload_${att.id.slice(0, 8).replace(/-/g, '')}`;
        setAttachments(prev => prev.map(a =>
          a.id === att.id ? { ...a, status: 'ready', url: result.url, tag } : a
        ));
      } catch (err) {
        setAttachments(prev => prev.map(a =>
          a.id === att.id
            ? { ...a, status: 'error', error: err instanceof Error ? err.message : String(err) }
            : a
        ));
      }
    }));
  };

  // Revoke object URLs on unmount
  useEffect(() => {
    return () => {
      for (const a of attachments) {
        if (a.previewUrl) URL.revokeObjectURL(a.previewUrl);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Voice recording ──
  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      audioChunksRef.current = [];

      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) audioChunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        setRecording(false);
        setTranscribing(true);
        try {
          const { text } = await transcribeAudio(blob);
          if (text) {
            setPrompt(prev => prev ? `${prev} ${text}` : text);
            textareaRef.current?.focus();
          }
        } catch (err) {
          console.error('Transcription failed:', err);
        } finally {
          setTranscribing(false);
        }
      };

      recorder.start();
      mediaRecorderRef.current = recorder;
      setRecording(true);
    } catch (err) {
      console.error('Microphone access denied:', err);
    }
  };

  const stopRecording = () => {
    mediaRecorderRef.current?.stop();
  };

  // ── Home Submit: create project + redirect ──
  const handleSubmit = async (text?: string) => {
    const finalPrompt = text || prompt;
    if (!finalPrompt.trim() || isCreating) return;
    if (attachments.some(a => a.status === 'uploading')) {
      setUploadError('Wait for uploads to finish before sending.');
      return;
    }
    setIsCreating(true);
    try {
      const nameRes = await creativeFetch<{ name: string }>('/creative-os/projects/generate-name', {
        method: 'POST',
        body: JSON.stringify({ prompt: finalPrompt }),
      });
      const projectName = nameRes.name || 'New Project';
      // Create project via core API (uses service key, correct schema)
      const newProject = await creativeFetch<{ id: string }>('/creative-os/projects/', {
        method: 'POST',
        body: JSON.stringify({ name: projectName }),
      });
      // Serialize active refs so the project page can reconstruct @mentions
      const mentionRefs = Array.from(activeRefs.values()).filter(r => finalPrompt.includes(`@${r.tag}`));
      // Uploaded file refs (always sent — user explicitly attached them)
      const uploadRefs = attachments
        .filter(a => a.status === 'ready' && a.url)
        .map(a => ({
          type: a.type,
          tag: a.tag || `upload_${a.id.slice(0, 8)}`,
          name: a.name,
          ...(a.type === 'image' ? { image_url: a.url } : { video_url: a.url }),
        }));
      const refsArray = [...mentionRefs, ...uploadRefs];
      const refsParam = refsArray.length > 0 ? `&refs=${encodeURIComponent(JSON.stringify(refsArray))}` : '';
      const seedanceParam = seedanceOn ? '&seedance=1' : '';
      router.push(`/projects/${newProject.id}?brief=${encodeURIComponent(finalPrompt)}${refsParam}${seedanceParam}`);
    } catch (err) {
      console.error("Failed to create project from home prompt:", err);
      setIsCreating(false);
    }
  };

  const canSend = prompt.trim().length > 0 && !isCreating;

  if (loading) {
    return (
      <div className="content-area">
        <div className="empty-state">
          <div className="empty-title">{t('dashboard.initStudio')}</div>
        </div>
      </div>
    );
  }

  return (
    <div style={{
      minHeight: 'calc(100vh - var(--header-h))',
      display: 'flex',
      flexDirection: 'column',
      background: 'linear-gradient(180deg, #e8eeff 0%, #dfe6ff 30%, #ede5ff 60%, #f5f0ff 85%, #ffffff 100%)',
      backgroundAttachment: 'fixed'
    }}>

      {/* ── HERO SECTION ─────────────────────────────────────────────── */}
      <div style={{
        flex: 1,
        minHeight: 'calc(100vh - var(--header-h) - 80px)', // Pushes bottom menu down so only the tab bar peeps up
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '50px 24px 48px',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Subtle gradient mesh orbs */}
        <div style={{
          position: 'absolute', top: '-10%', left: '10%',
          width: '600px', height: '600px', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(51,122,255,0.12) 0%, transparent 65%)',
          pointerEvents: 'none', filter: 'blur(40px)',
        }} />
        <div style={{
          position: 'absolute', top: '20%', right: '5%',
          width: '500px', height: '500px', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(107,78,255,0.10) 0%, transparent 65%)',
          pointerEvents: 'none', filter: 'blur(40px)',
        }} />
        <div style={{
          position: 'absolute', bottom: '-5%', left: '30%',
          width: '400px', height: '400px', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(147,120,255,0.08) 0%, transparent 65%)',
          pointerEvents: 'none', filter: 'blur(40px)',
        }} />

        {/* Greeting */}
        <h1 style={{
          fontSize: 'clamp(28px, 4vw, 40px)',
          fontWeight: 800,
          color: '#0D1B3E',
          letterSpacing: '-0.8px',
          lineHeight: 1.2,
          marginBottom: '32px',
          textAlign: 'center',
          position: 'relative',
          zIndex: 1,
        }}>
          {(() => {
            const parts = t('creativeOs.dashboard.heroGreeting').split('{name}');
            return (
              <>
                {parts[0]}
                <span style={{
                  background: 'linear-gradient(135deg, #337AFF, #6B4EFF)',
                  WebkitBackgroundClip: 'text',
                  WebkitTextFillColor: 'transparent',
                }}>
                  {userName}
                </span>
                {parts[1] ?? ''}
              </>
            );
          })()}
        </h1>

        {/* ── Composer Card ──────────────────────────────────────────── */}
        <div style={{
          width: '100%',
          maxWidth: '720px',
          position: 'relative',
          zIndex: 1,
        }}>
          {/* Hidden file input */}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/*,video/*"
            multiple
            style={{ display: 'none' }}
            onChange={handleFilePicked}
          />

          {isCreating ? (
            /* Creating State */
            <div style={{
              padding: '40px',
              textAlign: 'center',
              background: 'rgba(255,255,255,0.92)',
              backdropFilter: 'blur(24px)',
              borderRadius: '20px',
              border: '1px solid rgba(51,122,255,0.10)',
              boxShadow: '0 8px 40px rgba(51,122,255,0.10)',
            }}>
              <div style={{
                width: '36px', height: '36px', borderRadius: '50%',
                border: '3px solid rgba(51,122,255,0.15)',
                borderTopColor: '#337AFF',
                animation: 'spin 0.8s linear infinite',
                margin: '0 auto 16px',
              }} />
              <p style={{ fontSize: '15px', fontWeight: 600, color: '#0D1B3E', margin: 0 }}>
                {t('creativeOs.dashboard.creatingProjectTitle')}
              </p>
              <p style={{ fontSize: '13px', color: '#8A93B0', marginTop: '6px' }}>
                {t('creativeOs.dashboard.creatingProjectHint')}
              </p>
            </div>
          ) : (
            /* Input Card */
            <div style={{
              background: 'rgba(255,255,255,0.92)',
              backdropFilter: 'blur(24px)',
              borderRadius: '20px',
              border: '1px solid rgba(51,122,255,0.10)',
              boxShadow: '0 4px 32px rgba(51,122,255,0.08)',
            }}>
              {/* Attached file chips */}
              {attachments.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', padding: '16px 24px 0' }}>
                  {attachments.map((a) => {
                    const isError = a.status === 'error';
                    const isUploading = a.status === 'uploading';
                    return (
                      <span key={a.id} style={{
                        display: 'inline-flex', alignItems: 'center', gap: '6px',
                        padding: '4px 10px', borderRadius: '8px',
                        background: isError ? 'rgba(229,62,62,0.08)' : 'rgba(51,122,255,0.08)',
                        border: isError ? '1px solid rgba(229,62,62,0.25)' : '1px solid transparent',
                        color: isError ? '#C53030' : '#337AFF',
                        fontSize: '12px', fontWeight: 600,
                      }}>
                        {isUploading && (
                          <span style={{
                            width: '10px', height: '10px', borderRadius: '50%',
                            border: '2px solid rgba(51,122,255,0.25)',
                            borderTopColor: '#337AFF',
                            animation: 'spin 0.8s linear infinite',
                            display: 'inline-block',
                          }} />
                        )}
                        <span style={{ textTransform: 'uppercase', fontSize: '10px', letterSpacing: '0.4px', opacity: 0.7 }}>
                          {a.type}
                        </span>
                        <span>{a.name}</span>
                        {isError && <span title={a.error} style={{ opacity: 0.8 }}>failed</span>}
                        <button
                          onClick={() => removeAttachment(a.id)}
                          style={{ background: 'none', border: 'none', color: '#8A93B0', cursor: 'pointer', fontSize: '14px', lineHeight: 1, padding: 0 }}
                        >×</button>
                      </span>
                    );
                  })}
                </div>
              )}
              {uploadError && (
                <div style={{
                  padding: '8px 24px 0', fontSize: '12px', color: '#C53030',
                }}>{uploadError}</div>
              )}

              {/* Textarea */}
              {mentionOpen && (
                <div style={{
                  position: 'absolute',
                  bottom: 'calc(100% - 20px)',
                  left: '24px',
                  background: 'white',
                  border: '1px solid rgba(13,27,62,0.12)',
                  borderRadius: '12px',
                  boxShadow: '0 12px 32px rgba(13,27,62,0.16)',
                  maxHeight: '320px',
                  width: '360px',
                  overflowY: 'auto',
                  padding: '8px',
                  zIndex: 100,
                }}>
                  {filteredMentions.length === 0 ? (
                    <div style={{ padding: '8px', fontSize: '12px', color: '#8A93B0', textAlign: 'center' }}>No matches</div>
                  ) : (
                    (['product', 'influencer'] as const).map(groupType => {
                      const groupItems = filteredMentions.filter(m => m.type === groupType);
                      if (groupItems.length === 0) return null;
                      return (
                        <div key={groupType} style={{ marginBottom: '6px' }}>
                          <div style={{
                            fontSize: '10px', fontWeight: 700, color: '#8A93B0',
                            textTransform: 'uppercase', letterSpacing: '0.5px', padding: '4px 6px'
                          }}>
                            {groupType === 'product' ? 'Products' : 'Models'}
                          </div>
                          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '6px' }}>
                            {groupItems.map(item => {
                              const globalIdx = filteredMentions.indexOf(item);
                              const active = globalIdx === mentionIndex;
                              return (
                                <button
                                  key={item.tag}
                                  type="button"
                                  onMouseDown={(e) => { e.preventDefault(); finalizeMention(item); }}
                                  onMouseEnter={() => setMentionIndex(globalIdx)}
                                  title={item.name}
                                  style={{
                                    display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px',
                                    padding: '6px 4px',
                                    border: active ? '1px solid rgba(51,122,255,0.5)' : '1px solid transparent',
                                    background: active ? 'rgba(51,122,255,0.08)' : 'transparent',
                                    borderRadius: '8px', cursor: 'pointer', minWidth: 0
                                  }}
                                >
                                  <div style={{ width: '100%', aspectRatio: '1 / 1', borderRadius: '6px', background: '#F4F6FA', overflow: 'hidden', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                                    {item.image_url ? (
                                      // eslint-disable-next-line @next/next/no-img-element
                                      <img src={item.image_url} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                                    ) : <span style={{ fontSize: '14px', color: '#8A93B0' }}>{item.type === 'product' ? '📦' : '👤'}</span>}
                                  </div>
                                  <span style={{ fontSize: '10px', color: '#0D1B3E', fontWeight: 500, textOverflow: 'ellipsis', overflow: 'hidden', whiteSpace: 'nowrap', width: '100%', textAlign: 'center' }}>
                                    {item.name}
                                  </span>
                                </button>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })
                  )}
                </div>
              )}
              <textarea
                ref={textareaRef}
                value={prompt}
                onChange={handlePromptChange}
                onKeyDown={handleMentionKeyDown}
                placeholder={t('creativeOs.dashboard.textareaPlaceholder')}
                rows={2}
                style={{
                  width: '100%',
                  padding: '24px 24px 12px',
                  border: 'none',
                  outline: 'none',
                  resize: 'none',
                  fontSize: '15px',
                  fontFamily: 'inherit',
                  color: '#0D1B3E',
                  background: 'transparent',
                  lineHeight: 1.5,
                }}
              />

              {/* Toolbar */}
              <div style={{
                display: 'flex',
                alignItems: 'center',
                padding: '8px 16px 16px',
                gap: '8px',
              }}>
                {/* + Button Container */}
                <div style={{ position: 'relative' }}>
                  <button
                    onClick={() => setPlusMenuOpen(!plusMenuOpen)}
                    onBlur={() => setTimeout(() => setPlusMenuOpen(false), 150)}
                    title={t('creativeOs.dashboard.menuTitle')}
                    style={{
                      width: '34px', height: '34px',
                      borderRadius: '10px',
                      border: '1px solid rgba(13,27,62,0.10)',
                      background: 'rgba(255,255,255,0.8)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      cursor: 'pointer', color: '#5B6585',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = '#337AFF'; e.currentTarget.style.color = '#337AFF'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(13,27,62,0.10)'; e.currentTarget.style.color = '#5B6585'; }}
                  >
                    <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: 'currentColor', strokeWidth: '2.2', strokeLinecap: 'round' }}>
                      <line x1="12" y1="5" x2="12" y2="19" />
                      <line x1="5" y1="12" x2="19" y2="12" />
                    </svg>
                  </button>

                  {/* Dropdown Menu */}
                  {plusMenuOpen && (
                    <div style={{
                      position: 'absolute',
                      bottom: 'calc(100% + 8px)',
                      left: '0',
                      background: 'white',
                      borderRadius: '12px',
                      boxShadow: '0 4px 20px rgba(0,0,0,0.1)',
                      border: '1px solid rgba(13,27,62,0.08)',
                      padding: '6px',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '4px',
                      zIndex: 10,
                      minWidth: '140px'
                    }}>
                      <button
                        onClick={() => { setPlusMenuOpen(false); fileInputRef.current?.click(); }}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '8px',
                          padding: '8px 10px', borderRadius: '8px',
                          border: 'none', background: 'transparent',
                          cursor: 'pointer', color: '#0D1B3E', fontSize: '14px', fontWeight: 500,
                          textAlign: 'left'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(51,122,255,0.06)'}
                        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                      >
                         <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#337AFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48"/></svg>
                         {t('creativeOs.dashboard.menuAttach')}
                      </button>
                      <button
                        onClick={openReferenceDropdown}
                        style={{
                          display: 'flex', alignItems: 'center', gap: '8px',
                          padding: '8px 10px', borderRadius: '8px',
                          border: 'none', background: 'transparent',
                          cursor: 'pointer', color: '#0D1B3E', fontSize: '14px', fontWeight: 500,
                          textAlign: 'left'
                        }}
                        onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(51,122,255,0.06)'}
                        onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
                      >
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#337AFF" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="4"/><path d="M16 8v5a3 3 0 0 0 6 0v-1a10 10 0 1 0-3.92 7.94"/></svg>
                         {t('creativeOs.dashboard.menuReference')}
                      </button>
                    </div>
                  )}
                </div>

                {/* Seedance 2.0 Toggle */}
                <div
                  onClick={() => setSeedanceOn((v) => !v)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '7px',
                    padding: '6px 12px', borderRadius: '999px',
                    border: `1px solid ${seedanceOn ? 'rgba(51,122,255,0.3)' : 'rgba(13,27,62,0.10)'}`,
                    background: seedanceOn ? 'rgba(51,122,255,0.06)' : 'rgba(255,255,255,0.8)',
                    cursor: 'pointer', userSelect: 'none',
                    transition: 'all 0.15s',
                  }}
                >
                  <div style={{
                    width: '28px', height: '16px', borderRadius: '8px',
                    position: 'relative',
                    background: seedanceOn ? 'linear-gradient(135deg, #5B7BFF, #337AFF)' : 'rgba(138,147,176,0.25)',
                    transition: 'background 0.2s',
                    flexShrink: 0,
                  }}>
                    <div style={{
                      width: '12px', height: '12px', borderRadius: '50%',
                      background: 'white', position: 'absolute', top: '2px',
                      left: seedanceOn ? '14px' : '2px',
                      transition: 'left 0.2s',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.15)',
                    }} />
                  </div>
                  <span style={{
                    fontSize: '12px', fontWeight: 600,
                    color: seedanceOn ? '#337AFF' : '#5B6585',
                    letterSpacing: '0.1px',
                  }}>
                    Seedance 2.0
                  </span>
                </div>

                {/* Spacer */}
                <div style={{ flex: 1 }} />

                {/* Mic Button */}
                <button
                  onClick={recording ? stopRecording : startRecording}
                  disabled={transcribing}
                  title={recording ? t('creativeOs.dashboard.micStop') : transcribing ? t('creativeOs.dashboard.micTranscribing') : t('creativeOs.dashboard.micDictate')}
                  style={{
                    width: '34px', height: '34px',
                    borderRadius: '50%', border: 'none',
                    background: recording ? 'rgba(255,82,82,0.12)' : 'transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: transcribing ? 'wait' : 'pointer',
                    color: recording ? '#C53030' : transcribing ? '#8A93B0' : '#8A93B0',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { if (!recording && !transcribing) { e.currentTarget.style.color = '#337AFF'; e.currentTarget.style.background = 'rgba(51,122,255,0.06)'; } }}
                  onMouseLeave={(e) => { if (!recording && !transcribing) { e.currentTarget.style.color = '#8A93B0'; e.currentTarget.style.background = 'transparent'; } }}
                >
                  {transcribing ? (
                    <span style={{ display: 'flex', gap: '2px' }}>
                      <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'currentColor', animation: 'pulse 1s ease-in-out infinite' }} />
                      <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'currentColor', animation: 'pulse 1s ease-in-out 0.15s infinite' }} />
                      <span style={{ width: '4px', height: '4px', borderRadius: '50%', background: 'currentColor', animation: 'pulse 1s ease-in-out 0.3s infinite' }} />
                    </span>
                  ) : (
                    <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                      <rect x="9" y="3" width="6" height="12" rx="3" />
                      <path d="M5 11a7 7 0 0 0 14 0" />
                      <line x1="12" y1="18" x2="12" y2="22" />
                    </svg>
                  )}
                </button>

                {/* Send Button */}
                <button
                  onClick={() => handleSubmit()}
                  disabled={!canSend}
                  title={t('creativeOs.dashboard.sendTitle')}
                  style={{
                    width: '36px', height: '36px',
                    borderRadius: '50%', border: 'none',
                    background: canSend
                      ? 'linear-gradient(135deg, #337AFF 0%, #5B8FFF 100%)'
                      : 'rgba(13,27,62,0.12)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: canSend ? 'pointer' : 'not-allowed',
                    color: 'white',
                    transition: 'all 0.15s',
                    boxShadow: canSend ? '0 2px 8px rgba(51,122,255,0.3)' : 'none',
                  }}
                >
                  <svg viewBox="0 0 24 24" style={{ width: '15px', height: '15px', fill: 'none', stroke: 'currentColor', strokeWidth: '2.4', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                    <line x1="12" y1="19" x2="12" y2="5" />
                    <polyline points="5 12 12 5 19 12" />
                  </svg>
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Suggestion Chips */}
        {!isCreating && (
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '8px',
            justifyContent: 'center',
            marginTop: '20px',
            maxWidth: '720px',
            position: 'relative',
            zIndex: 1,
          }}>
            {SUGGESTION_CHIP_KEYS.map((key) => {
              const chip = t(key);
              return (
              <button
                key={key}
                onClick={() => handleSubmit(chip)}
                style={{
                  padding: '7px 16px',
                  borderRadius: '999px',
                  border: '1px solid rgba(51,122,255,0.14)',
                  background: 'rgba(255,255,255,0.65)',
                  backdropFilter: 'blur(8px)',
                  color: '#4A5578',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap',
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = 'rgba(51,122,255,0.07)';
                  e.currentTarget.style.borderColor = 'rgba(51,122,255,0.3)';
                  e.currentTarget.style.color = '#337AFF';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'rgba(255,255,255,0.65)';
                  e.currentTarget.style.borderColor = 'rgba(51,122,255,0.14)';
                  e.currentTarget.style.color = '#4A5578';
                }}
              >
                {chip}
              </button>
              );
            })}
          </div>
        )}
      </div>

      {/* ── BOTTOM SECTION ───────────────────────────────────────────── */}
      <div style={{
        maxWidth: '1248px', /* 1200px + 24px padding on each side */
        width: '100%',
        margin: '0 auto',
        background: 'rgba(255,255,255,0.92)',
        backdropFilter: 'blur(24px)',
        border: '1px solid rgba(51,122,255,0.10)',
        borderBottom: 'none',
        borderTopLeftRadius: '32px',
        borderTopRightRadius: '32px',
        padding: '0 24px 24px', /* Reduced bottom padding to avoid too much empty space */
        minHeight: '400px', /* Ensure it covers bottom if few projects */
        boxShadow: '0 -8px 40px rgba(51,122,255,0.06)',
      }}>
        {/* Tab Bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0',
          borderBottom: '1px solid rgba(0,0,0,0.06)',
          maxWidth: '1200px',
          margin: '0 auto',
        }}>
          {(['projects', 'videos', 'images', 'campaigns'] as const).map((tab) => {
            const labels = {
              projects: t('creativeOs.dashboard.tabProjects'),
              videos: t('creativeOs.dashboard.tabVideos'),
              images: t('creativeOs.dashboard.tabImages'),
              campaigns: t('creativeOs.dashboard.tabCampaigns'),
            };
            const counts: Record<string, number> = {
              projects: projects.length,
              videos: recentVideos.length,
              images: recentImages.length,
              campaigns: campaigns.length,
            };
            const isActive = activeBottomTab === tab;
            return (
              <button
                key={tab}
                onClick={() => setActiveBottomTab(tab)}
                style={{
                  padding: '16px 20px',
                  border: 'none',
                  background: 'transparent',
                  color: isActive ? '#337AFF' : '#8A93B0',
                  fontSize: '13.5px',
                  fontWeight: isActive ? 700 : 500,
                  cursor: 'pointer',
                  borderBottom: isActive ? '2px solid #337AFF' : '2px solid transparent',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                  marginBottom: '-1px',
                }}
              >
                {labels[tab]}
                {counts[tab] > 0 && (
                  <span style={{
                    fontSize: '11px', fontWeight: 700,
                    background: isActive ? 'rgba(51,122,255,0.10)' : 'rgba(0,0,0,0.05)',
                    color: isActive ? '#337AFF' : '#8A93B0',
                    padding: '2px 7px', borderRadius: '10px', lineHeight: 1.3,
                  }}>
                    {counts[tab]}
                  </span>
                )}
              </button>
            );
          })}

          <div style={{ flex: 1 }} />
          <Link
            href={activeBottomTab === 'projects' ? '/projects-library' : '/library'}
            style={{
              fontSize: '13px', fontWeight: 600, color: '#337AFF',
              textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '4px', padding: '16px 0',
            }}
          >
            {t('creativeOs.dashboard.browseAll')}
            <svg viewBox="0 0 24 24" style={{ width: '14px', height: '14px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
              <line x1="5" y1="12" x2="19" y2="12" />
              <polyline points="12 5 19 12 12 19" />
            </svg>
          </Link>
        </div>

        {/* Panel Content */}
        <div style={{ maxWidth: '1200px', margin: '0 auto', paddingTop: '24px' }}>

          {/* ── My Projects ─────────────────────────────────────── */}
          {activeBottomTab === 'projects' && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
              gap: '20px',
            }}>
              {projects.map((p) => {
                const videoCount = p.asset_counts?.videos || 0;
                const imageCount = p.asset_counts?.images || 0;
                const hasAssets = videoCount > 0 || imageCount > 0;
                const previewUrl = p.recent_previews?.[0]?.url;
                const previewIsVideo = !!previewUrl && /\.(mp4|webm|mov)(\?|#|$)/i.test(previewUrl);
                const fallbackGradient = `linear-gradient(135deg, hsl(${(p.name?.charCodeAt(0) || 0) * 7 % 360}, 45%, 90%), hsl(${((p.name?.charCodeAt(0) || 0) * 7 + 40) % 360}, 45%, 84%))`;
                return (
                  <Link key={p.id} href={`/projects/${p.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                    <div style={{
                      borderRadius: '16px',
                      overflow: 'hidden',
                      border: '1px solid rgba(51,122,255,0.08)',
                      background: 'white',
                      transition: 'transform 0.18s ease, box-shadow 0.18s ease',
                      cursor: 'pointer',
                    }}
                      onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(51,122,255,0.12)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
                    >
                      {/* Large thumbnail — like Lovable */}
                      <div style={{
                        height: '200px',
                        background: previewUrl && !previewIsVideo
                          ? `url(${previewUrl}) center/cover no-repeat`
                          : fallbackGradient,
                        position: 'relative',
                        overflow: 'hidden',
                      }}>
                        {previewIsVideo && previewUrl && (
                          <video
                            src={previewUrl}
                            muted
                            playsInline
                            preload="metadata"
                            style={{
                              position: 'absolute',
                              inset: 0,
                              width: '100%',
                              height: '100%',
                              objectFit: 'cover',
                              display: 'block',
                            }}
                          />
                        )}
                        {/* Status badge */}
                        {hasAssets && (
                          <span style={{
                            position: 'absolute', top: '12px', right: '12px',
                            padding: '4px 12px', borderRadius: '999px',
                            fontSize: '11px', fontWeight: 700,
                            background: 'rgba(34,197,94,0.9)',
                            color: 'white',
                          }}>
                            {videoCount > 0 && imageCount > 0 ? t('creativeOs.dashboard.badgeActive') : t('creativeOs.dashboard.badgeDone')}
                          </span>
                        )}
                      </div>

                      {/* Info row */}
                      <div style={{ padding: '16px 18px', display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{
                            fontSize: '14px', fontWeight: 700, color: '#0D1B3E',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}>
                            {p.name}
                          </div>
                          <div style={{ fontSize: '12px', color: '#8A93B0', marginTop: '2px' }}>
                            {p.updated_at
                              ? t('creativeOs.dashboard.edited').replace('{time}', relativeTime(p.updated_at, t, lang))
                              : p.created_at
                                ? t('creativeOs.dashboard.created').replace('{time}', relativeTime(p.created_at, t, lang))
                                : ''}
                            {videoCount > 0 && ` · ${videoCount === 1 ? t('creativeOs.dashboard.videoCountOne') : t('creativeOs.dashboard.videoCountMany').replace('{n}', String(videoCount))}`}
                            {imageCount > 0 && ` · ${imageCount === 1 ? t('creativeOs.dashboard.imageCountOne') : t('creativeOs.dashboard.imageCountMany').replace('{n}', String(imageCount))}`}
                          </div>
                        </div>
                      </div>
                    </div>
                  </Link>
                );
              })}

              {/* Empty state when no projects */}
              {projects.length === 0 && (
                <div style={{
                  gridColumn: '1 / -1',
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                  padding: '48px 20px', color: '#8A93B0',
                }}>
                  <div style={{
                    width: '56px', height: '56px', borderRadius: '16px',
                    background: 'rgba(51,122,255,0.06)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    marginBottom: '16px',
                  }}>
                    <svg viewBox="0 0 24 24" style={{ width: '24px', height: '24px', fill: 'none', stroke: '#8A93B0', strokeWidth: '1.5', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
                      <polyline points="14 2 14 8 20 8" />
                    </svg>
                  </div>
                  <span style={{ fontSize: '14px', fontWeight: 600 }}>{t('creativeOs.dashboard.emptyProjectsLabel')}</span>
                  <span style={{ fontSize: '13px', marginTop: '4px' }}>{t('creativeOs.dashboard.emptyProjectsHint')}</span>
                </div>
              )}
            </div>
          )}

          {/* ── Recent Videos — 9:16 portrait cards ─────────────── */}
          {activeBottomTab === 'videos' && (
            recentVideos.length === 0 ? (
              <EmptyState icon="video" label={t('creativeOs.dashboard.emptyVideosLabel')} desc={t('creativeOs.dashboard.emptyVideosHint')} />
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                gap: '16px',
              }}>
                {recentVideos.map((job) => (
                  <div
                    key={job.id}
                    onClick={() => job.final_video_url && window.open(job.final_video_url)}
                    style={{
                      borderRadius: '14px',
                      overflow: 'hidden',
                      border: '1px solid rgba(0,0,0,0.06)',
                      background: 'white',
                      cursor: 'pointer',
                      transition: 'transform 0.18s ease, box-shadow 0.18s ease',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(0,0,0,0.08)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
                  >
                    {/* 9:16 portrait thumbnail */}
                    <div style={{ aspectRatio: '9/16', position: 'relative', background: '#f0f2f5', overflow: 'hidden' }}>
                      {job.final_video_url && (
                        <video
                          src={job.final_video_url}
                          style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          muted loop playsInline
                          onMouseEnter={(e) => (e.target as HTMLVideoElement).play().catch(() => {})}
                          onMouseLeave={(e) => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0; }}
                        />
                      )}
                    </div>
                    <div style={{ padding: '10px 12px' }}>
                      <div style={{ fontSize: '12.5px', fontWeight: 600, color: '#0D1B3E', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {job.campaign_name || t('creativeOs.dashboard.cardFallbackName')}
                      </div>
                      <div style={{ fontSize: '11px', color: '#8A93B0', marginTop: '2px' }}>
                        {relativeTime(job.created_at, t, lang)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )
          )}

          {/* ── Recent Images — 9:16 portrait cards ─────────────── */}
          {activeBottomTab === 'images' && (
            recentImages.length === 0 ? (
              <EmptyState icon="image" label={t('creativeOs.dashboard.emptyImagesLabel')} desc={t('creativeOs.dashboard.emptyImagesHint')} />
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
                gap: '16px',
              }}>
                {recentImages.map((img) => {
                  const url = img.image_url || img.result_url;
                  return (
                    <div
                      key={img.id}
                      onClick={() => url && window.open(url)}
                      style={{
                        borderRadius: '14px',
                        overflow: 'hidden',
                        border: '1px solid rgba(0,0,0,0.06)',
                        background: 'white',
                        cursor: 'pointer',
                        transition: 'transform 0.18s ease, box-shadow 0.18s ease',
                      }}
                      onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(0,0,0,0.08)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
                    >
                      {/* 9:16 portrait thumbnail */}
                      <div style={{ aspectRatio: '9/16', position: 'relative', background: '#f0f2f5', overflow: 'hidden' }}>
                        {url && (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={url}
                            alt={img.product_name || 'Image'}
                            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                          />
                        )}
                      </div>
                      <div style={{ padding: '10px 12px' }}>
                        <div style={{ fontSize: '12.5px', fontWeight: 600, color: '#0D1B3E', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {img.product_name || t('creativeOs.dashboard.cardFallbackName')}
                        </div>
                        <div style={{ fontSize: '11px', color: '#8A93B0', marginTop: '2px' }}>
                          {img.created_at ? relativeTime(img.created_at, t, lang) : ''}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )
          )}

          {/* ── My Campaigns ────────────────────────────────────── */}
          {activeBottomTab === 'campaigns' && (
            campaigns.length === 0 ? (
              <EmptyState icon="campaign" label={t('creativeOs.dashboard.emptyCampaignsLabel')} desc={t('creativeOs.dashboard.emptyCampaignsHint')} />
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                gap: '16px',
              }}>
                {campaigns.map((c) => {
                  const pct = c.total > 0 ? Math.round((c.success / c.total) * 100) : 0;
                  return (
                    <div key={c.name} style={{
                      borderRadius: '14px',
                      border: '1px solid rgba(51,122,255,0.08)',
                      background: 'white',
                      padding: '18px 20px',
                      display: 'flex', flexDirection: 'column', gap: '12px',
                    }}>
                      <div style={{ fontSize: '13.5px', fontWeight: 700, color: '#0D1B3E', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {c.name}
                      </div>
                      <div>
                        <div style={{ height: '6px', background: 'rgba(51,122,255,0.08)', borderRadius: '3px', overflow: 'hidden', marginBottom: '8px' }}>
                          <div style={{ height: '100%', width: `${pct}%`, background: 'linear-gradient(90deg, #337AFF, #5B8FFF)', borderRadius: '3px', transition: 'width 0.3s ease' }} />
                        </div>
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11.5px', color: '#8A93B0' }}>
                          <span>{t('creativeOs.dashboard.campaignCompleted').replace('{done}', String(c.success)).replace('{total}', String(c.total))}</span>
                          <span>{pct}%</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )
          )}
        </div>
      </div>

      {/* Keyframe animations */}
      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
        @keyframes pulse {
          0%, 100% { opacity: 0.4; transform: scale(0.85); }
          50% { opacity: 1; transform: scale(1.15); }
        }
      `}</style>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty State Component
// ---------------------------------------------------------------------------

function EmptyState({ icon, label, desc }: { icon: string; label: string; desc: string }) {
  const iconPaths: Record<string, React.ReactNode> = {
    video: (
      <>
        <rect x="2" y="4" width="20" height="16" rx="2" />
        <path d="m15 12-5 3V9l5 3Z" />
      </>
    ),
    image: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <polyline points="21 15 16 10 5 21" />
      </>
    ),
    campaign: (
      <>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="16" y1="13" x2="8" y2="13" />
        <line x1="16" y1="17" x2="8" y2="17" />
      </>
    ),
  };
  return (
    <div style={{
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '64px 20px', color: '#8A93B0',
    }}>
      <div style={{
        width: '56px', height: '56px', borderRadius: '16px',
        background: 'rgba(51,122,255,0.06)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: '16px',
      }}>
        <svg viewBox="0 0 24 24" style={{ width: '24px', height: '24px', fill: 'none', stroke: '#8A93B0', strokeWidth: '1.5', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
          {iconPaths[icon]}
        </svg>
      </div>
      <span style={{ fontSize: '14px', fontWeight: 600 }}>{label}</span>
      <span style={{ fontSize: '13px', marginTop: '4px' }}>{desc}</span>
    </div>
  );
}
