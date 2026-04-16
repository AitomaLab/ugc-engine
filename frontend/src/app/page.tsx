"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/utils";
import { useApp } from "@/providers/AppProvider";
import { useTranslation } from "@/lib/i18n";
import Link from "next/link";
import { createProject } from "@/lib/supabaseData";
import { creativeFetch } from "@/lib/creative-os-api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Job {
  id: string;
  status: string;
  progress: number;
  created_at: string;
  final_video_url?: string;
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

const SUGGESTION_CHIPS = [
  "Create a UGC ad for my product",
  "Generate product shots",
  "Build a 5-video campaign",
  "Make a Spanish-language ad",
  "Create an AI clone video",
];

// ---------------------------------------------------------------------------
// Studio Page
// ---------------------------------------------------------------------------

export default function StudioPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [influencers, setInfluencers] = useState<Influencer[]>([]);
  const [projects, setProjects] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [activeBottomTab, setActiveBottomTab] = useState<'projects' | 'videos' | 'images' | 'campaigns'>('projects');
  const { profile } = useApp();
  const userName = profile?.name || profile?.email?.split('@')[0] || 'Creator';

  // Composer state
  const [prompt, setPrompt] = useState('');
  const [seedanceOn, setSeedanceOn] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const fetchData = useCallback(async () => {
    try {
      const [jobsData, infData, projectsData] = await Promise.all([
        apiFetch<Job[]>("/jobs?limit=100&include_clones=true"),
        apiFetch<Influencer[]>("/influencers"),
        creativeFetch<any[]>('/creative-os/projects/').catch(() => []),
      ]);
      setJobs(jobsData);
      setInfluencers(infData);
      setProjects(projectsData || []);
    } catch (err) {
      console.error("Dashboard fetch error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // Derived data
  const campaigns = groupByCampaign(jobs);
  const recentVideos = jobs
    .filter((j) => j.status === "success" && j.final_video_url)
    .slice(0, 10);

  const formatDate = (d: string) => {
    const now = new Date();
    const date = new Date(d);
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString('en-US', { day: 'numeric', month: 'short', year: diffDays > 365 ? 'numeric' : undefined });
  };

  // ── Home Submit: create project + redirect ──
  const handleSubmit = async (text?: string) => {
    const finalPrompt = text || prompt;
    if (!finalPrompt.trim() || isCreating) return;
    setIsCreating(true);
    try {
      const nameRes = await creativeFetch<{ name: string }>('/creative-os/projects/generate-name', {
        method: 'POST',
        body: JSON.stringify({ prompt: finalPrompt }),
      });
      const projectName = nameRes.name || 'New Project';
      const newProject = await createProject({ name: projectName, description: finalPrompt });
      router.push(`/projects/${newProject.id}?brief=${encodeURIComponent(finalPrompt)}`);
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
    <div style={{ minHeight: 'calc(100vh - var(--header-h))' }}>

      {/* ── HERO SECTION ─────────────────────────────────────────────── */}
      <div style={{
        minHeight: 'min(65vh, 520px)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 24px 48px',
        background: 'linear-gradient(180deg, #e8eeff 0%, #dfe6ff 30%, #ede5ff 60%, #f5f0ff 85%, #ffffff 100%)',
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
          What will you create today,{' '}
          <span style={{
            background: 'linear-gradient(135deg, #337AFF, #6B4EFF)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
          }}>
            {userName}
          </span>
          ?
        </h1>

        {/* ── Composer Card ──────────────────────────────────────────── */}
        <div style={{
          width: '100%',
          maxWidth: '720px',
          position: 'relative',
          zIndex: 1,
        }}>
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
                Creating your project…
              </p>
              <p style={{ fontSize: '13px', color: '#8A93B0', marginTop: '6px' }}>
                Generating name and setting up workspace
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
              overflow: 'hidden',
            }}>
              {/* Textarea */}
              <textarea
                ref={textareaRef}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleSubmit();
                  }
                }}
                placeholder="Tell the Creative Director what to make next..."
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
                {/* + Button */}
                <button
                  title="Add attachment"
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
                  title="Voice input"
                  style={{
                    width: '34px', height: '34px',
                    borderRadius: '50%', border: 'none',
                    background: 'transparent',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    cursor: 'pointer', color: '#8A93B0',
                    transition: 'all 0.15s',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.color = '#337AFF'; e.currentTarget.style.background = 'rgba(51,122,255,0.06)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.color = '#8A93B0'; e.currentTarget.style.background = 'transparent'; }}
                >
                  <svg viewBox="0 0 24 24" style={{ width: '16px', height: '16px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round', strokeLinejoin: 'round' }}>
                    <rect x="9" y="3" width="6" height="12" rx="3" />
                    <path d="M5 11a7 7 0 0 0 14 0" />
                    <line x1="12" y1="18" x2="12" y2="22" />
                  </svg>
                </button>

                {/* Send Button */}
                <button
                  onClick={() => handleSubmit()}
                  disabled={!canSend}
                  title="Send"
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
            {SUGGESTION_CHIPS.map((chip) => (
              <button
                key={chip}
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
            ))}
          </div>
        )}
      </div>

      {/* ── BOTTOM SECTION (in-flow, not fixed) ──────────────────────── */}
      <div style={{
        background: '#ffffff',
        borderTop: '1px solid rgba(51,122,255,0.08)',
        padding: '0 40px 48px',
      }}>
        {/* Tab Bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0',
          padding: '0',
          borderBottom: '1px solid rgba(0,0,0,0.06)',
          maxWidth: '1200px',
          margin: '0 auto',
        }}>
          {(['projects', 'videos', 'images', 'campaigns'] as const).map((tab) => {
            const labels = {
              projects: 'My Projects',
              videos: 'Recent Videos',
              images: 'Recent Images',
              campaigns: 'My Campaigns',
            };
            const counts: Record<string, number> = {
              projects: projects.length,
              videos: recentVideos.length,
              images: 0,
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
                    fontSize: '11px',
                    fontWeight: 700,
                    background: isActive ? 'rgba(51,122,255,0.10)' : 'rgba(0,0,0,0.05)',
                    color: isActive ? '#337AFF' : '#8A93B0',
                    padding: '2px 7px',
                    borderRadius: '10px',
                    lineHeight: 1.3,
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
              fontSize: '13px',
              fontWeight: 600,
              color: '#337AFF',
              textDecoration: 'none',
              display: 'flex', alignItems: 'center', gap: '4px',
              padding: '16px 0',
            }}
          >
            Browse all
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
              gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
              gap: '16px',
            }}>
              {projects.map((p) => {
                const videoCount = p.asset_counts?.videos || 0;
                const imageCount = p.asset_counts?.images || 0;
                const hasAssets = videoCount > 0 || imageCount > 0;
                const previewUrl = p.recent_previews?.[0]?.url;
                return (
                  <Link key={p.id} href={`/projects/${p.id}`} style={{ textDecoration: 'none', color: 'inherit' }}>
                    <div style={{
                      borderRadius: '14px',
                      overflow: 'hidden',
                      border: '1px solid rgba(51,122,255,0.10)',
                      background: 'white',
                      transition: 'transform 0.18s ease, box-shadow 0.18s ease',
                      cursor: 'pointer',
                    }}
                      onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-3px)'; e.currentTarget.style.boxShadow = '0 12px 32px rgba(51,122,255,0.12)'; }}
                      onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = 'none'; }}
                    >
                      {/* Thumbnail */}
                      <div style={{
                        height: '140px',
                        background: previewUrl
                          ? `url(${previewUrl}) center/cover no-repeat`
                          : `linear-gradient(135deg, hsl(${(p.name?.charCodeAt(0) || 0) * 7 % 360}, 55%, 88%), hsl(${((p.name?.charCodeAt(0) || 0) * 7 + 40) % 360}, 55%, 82%))`,
                        position: 'relative',
                      }}>
                        {/* Status badge */}
                        {hasAssets && (
                          <span style={{
                            position: 'absolute', top: '10px', right: '10px',
                            padding: '3px 10px', borderRadius: '999px',
                            fontSize: '10px', fontWeight: 700, letterSpacing: '0.3px',
                            background: videoCount > 0 ? 'rgba(34,197,94,0.9)' : 'rgba(51,122,255,0.9)',
                            color: 'white',
                          }}>
                            {videoCount > 0 ? (imageCount > 0 ? 'Active' : 'Done') : 'Active'}
                          </span>
                        )}
                      </div>

                      {/* Info */}
                      <div style={{ padding: '14px 16px' }}>
                        <div style={{
                          fontSize: '13.5px', fontWeight: 700, color: '#0D1B3E',
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          marginBottom: '4px',
                        }}>
                          {p.name}
                        </div>
                        <div style={{ fontSize: '11.5px', color: '#8A93B0' }}>
                          {p.updated_at ? `Edited ${formatDate(p.updated_at)}` : p.created_at ? `Created ${formatDate(p.created_at)}` : ''}
                          {videoCount > 0 && ` · ${videoCount} video${videoCount !== 1 ? 's' : ''}`}
                          {imageCount > 0 && ` · ${imageCount} image${imageCount !== 1 ? 's' : ''}`}
                        </div>
                      </div>
                    </div>
                  </Link>
                );
              })}

              {/* New project card */}
              <div
                onClick={() => textareaRef.current?.focus()}
                style={{
                  borderRadius: '14px',
                  border: '2px dashed rgba(51,122,255,0.18)',
                  background: 'rgba(51,122,255,0.02)',
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                  minHeight: '200px',
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  gap: '8px',
                }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = 'rgba(51,122,255,0.35)'; e.currentTarget.style.background = 'rgba(51,122,255,0.04)'; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = 'rgba(51,122,255,0.18)'; e.currentTarget.style.background = 'rgba(51,122,255,0.02)'; }}
              >
                <div style={{
                  width: '40px', height: '40px', borderRadius: '12px',
                  background: 'rgba(51,122,255,0.06)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: '#337AFF',
                }}>
                  <svg viewBox="0 0 24 24" style={{ width: '20px', height: '20px', fill: 'none', stroke: 'currentColor', strokeWidth: '2', strokeLinecap: 'round' }}>
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                </div>
                <span style={{ fontSize: '13px', fontWeight: 600, color: '#8A93B0' }}>
                  New project via prompt
                </span>
              </div>

              {/* Empty state when no projects */}
              {projects.length === 0 && (
                <div style={{
                  gridColumn: '1 / -1',
                  display: 'flex', flexDirection: 'column',
                  alignItems: 'center', justifyContent: 'center',
                  padding: '48px 20px',
                  color: '#8A93B0',
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
                  <span style={{ fontSize: '14px', fontWeight: 600 }}>No projects yet</span>
                  <span style={{ fontSize: '13px', marginTop: '4px' }}>Start by typing a prompt above</span>
                </div>
              )}
            </div>
          )}

          {/* ── Recent Videos ───────────────────────────────────── */}
          {activeBottomTab === 'videos' && (
            recentVideos.length === 0 ? (
              <EmptyState icon="video" label="No videos yet" desc="Ask the agent to generate one" />
            ) : (
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
                gap: '16px',
              }}>
                {recentVideos.map((job, i) => (
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
                    <div style={{
                      height: '140px',
                      background: `linear-gradient(135deg, hsl(${(i * 47) % 360}, 55%, 88%), hsl(${(i * 47 + 40) % 360}, 55%, 80%))`,
                      position: 'relative',
                    }}>
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
                    <div style={{ padding: '12px 14px' }}>
                      <div style={{ fontSize: '12.5px', fontWeight: 600, color: '#0D1B3E', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {job.campaign_name || 'Video'}
                      </div>
                      <div style={{ fontSize: '11px', color: '#8A93B0', marginTop: '2px' }}>
                        {formatDate(job.created_at)}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )
          )}

          {/* ── Recent Images ───────────────────────────────────── */}
          {activeBottomTab === 'images' && (
            <EmptyState icon="image" label="No images yet" desc="Recent images will appear here after generation" />
          )}

          {/* ── My Campaigns ────────────────────────────────────── */}
          {activeBottomTab === 'campaigns' && (
            campaigns.length === 0 ? (
              <EmptyState icon="campaign" label="No campaigns yet" desc="Campaigns group related videos together" />
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
                          <span>{c.success}/{c.total} completed</span>
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
