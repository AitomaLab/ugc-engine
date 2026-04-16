"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/utils";
import { useApp } from "@/providers/AppProvider";
import { useTranslation } from "@/lib/i18n";
import Link from "next/link";
import { createProject } from "@/lib/supabaseData";
import { creativeFetch } from "@/lib/creative-os-api";
import { AgentPanel } from "@/components/studio/AgentPanel";

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
// Empty Panel State
// ---------------------------------------------------------------------------

function EmptyPanelState({ label }: { label: string }) {
  return (
    <div style={{ padding: '0 8px', color: '#8A93B0', fontSize: '12px', fontStyle: 'italic' }}>
      {label}
    </div>
  );
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

  // Ref for the embedded AgentPanel to trigger suggestion chip text
  const agentBriefRef = useRef<string>('');

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

  // Influencer name lookup
  const influencerMap = new Map(influencers.map((i) => [i.id, i]));

  const formatDate = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  // ── Home Submit: create project + redirect ──
  const handleHomeSubmit = async (prompt: string) => {
    if (!prompt.trim() || isCreating) return;
    setIsCreating(true);
    try {
      const nameRes = await creativeFetch<{ name: string }>('/creative-os/projects/generate-name', {
        method: 'POST',
        body: JSON.stringify({ prompt }),
      });
      const projectName = nameRes.name || 'New Project';
      const newProject = await createProject({ name: projectName, description: prompt });
      router.push(`/projects/${newProject.id}?brief=${encodeURIComponent(prompt)}`);
    } catch (err) {
      console.error("Failed to create project from home prompt:", err);
      setIsCreating(false);
    }
  };

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
    <div style={{ position: 'relative', minHeight: 'calc(100vh - var(--header-h))' }}>

      {/* ── HERO SECTION ─────────────────────────────────────────────── */}
      <div style={{
        minHeight: 'calc(100vh - var(--header-h) - 120px)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '60px 20px 160px',
        background: 'linear-gradient(160deg, #f0f4ff 0%, #e8eeff 40%, #f5f8ff 70%, #eef2ff 100%)',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Decorative gradient orbs */}
        <div style={{
          position: 'absolute', top: '10%', left: '5%',
          width: '400px', height: '400px', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(51,122,255,0.08) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />
        <div style={{
          position: 'absolute', bottom: '15%', right: '8%',
          width: '300px', height: '300px', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(107,78,255,0.07) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        {/* Greeting */}
        <div style={{ textAlign: 'center', marginBottom: '40px', position: 'relative', zIndex: 1 }}>
          <h1 style={{
            fontSize: '42px',
            fontWeight: 800,
            color: '#0D1B3E',
            letterSpacing: '-1px',
            lineHeight: 1.15,
            marginBottom: '12px',
          }}>
            Got an idea,{' '}
            <span style={{
              background: 'linear-gradient(135deg, #337AFF, #6B4EFF)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}>
              {userName}
            </span>
            ?
          </h1>
          <p style={{ fontSize: '17px', color: '#4A5578', fontWeight: 400 }}>
            Tell the Creative Director what to make next
          </p>
        </div>

        {/* Embedded Creative Agent */}
        <div style={{
          width: '100%',
          maxWidth: '760px',
          position: 'relative',
          zIndex: 1,
        }}>
          {isCreating ? (
            <div style={{
              padding: '40px',
              textAlign: 'center',
              background: 'rgba(255,255,255,0.85)',
              backdropFilter: 'blur(20px)',
              borderRadius: '20px',
              border: '1px solid rgba(51,122,255,0.14)',
              boxShadow: '0 8px 40px rgba(51,122,255,0.12)',
            }}>
              <div style={{
                width: '40px', height: '40px', borderRadius: '50%',
                border: '3px solid rgba(51,122,255,0.2)',
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
            <AgentPanel
              projectId="home-dashboard"
              embedded={true}
              onSubmitOverride={handleHomeSubmit}
            />
          )}
        </div>

        {/* Suggestion Chips */}
        {!isCreating && (
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: '8px',
            justifyContent: 'center',
            marginTop: '24px',
            maxWidth: '760px',
            position: 'relative',
            zIndex: 1,
          }}>
            {SUGGESTION_CHIPS.map((chip) => (
              <button
                key={chip}
                onClick={() => handleHomeSubmit(chip)}
                style={{
                  padding: '8px 16px',
                  borderRadius: '999px',
                  border: '1px solid rgba(51,122,255,0.18)',
                  background: 'rgba(255,255,255,0.8)',
                  backdropFilter: 'blur(8px)',
                  color: '#4A5578',
                  fontSize: '13px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease',
                  whiteSpace: 'nowrap',
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(51,122,255,0.08)';
                  (e.currentTarget as HTMLElement).style.borderColor = '#337AFF';
                  (e.currentTarget as HTMLElement).style.color = '#337AFF';
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLElement).style.background = 'rgba(255,255,255,0.8)';
                  (e.currentTarget as HTMLElement).style.borderColor = 'rgba(51,122,255,0.18)';
                  (e.currentTarget as HTMLElement).style.color = '#4A5578';
                }}
              >
                {chip}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── STICKY BOTTOM PANEL ──────────────────────────────────────── */}
      <div style={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        background: 'rgba(255, 255, 255, 0.92)',
        backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)',
        borderTop: '1px solid rgba(51,122,255,0.1)',
        zIndex: 500,
        boxShadow: '0 -4px 24px rgba(13,27,62,0.06)',
      }}>
        {/* Tab Bar */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          padding: '10px 24px 0',
          borderBottom: '1px solid rgba(0,0,0,0.05)',
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
            return (
              <button
                key={tab}
                onClick={() => setActiveBottomTab(tab)}
                style={{
                  padding: '7px 14px',
                  borderRadius: '8px 8px 0 0',
                  border: 'none',
                  background: activeBottomTab === tab ? 'white' : 'transparent',
                  color: activeBottomTab === tab ? '#337AFF' : '#8A93B0',
                  fontSize: '12px',
                  fontWeight: activeBottomTab === tab ? 700 : 500,
                  cursor: 'pointer',
                  borderBottom: activeBottomTab === tab ? '2px solid #337AFF' : '2px solid transparent',
                  transition: 'all 0.15s ease',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                {labels[tab]}
                {counts[tab] > 0 && (
                  <span style={{
                    fontSize: '10px',
                    fontWeight: 700,
                    background: activeBottomTab === tab ? 'rgba(51,122,255,0.12)' : 'rgba(0,0,0,0.06)',
                    color: activeBottomTab === tab ? '#337AFF' : '#8A93B0',
                    padding: '1px 6px',
                    borderRadius: '10px',
                  }}>
                    {counts[tab]}
                  </span>
                )}
              </button>
            );
          })}

          {/* Browse all link */}
          <div style={{ flex: 1 }} />
          <Link
            href={activeBottomTab === 'projects' ? '/projects-library' : activeBottomTab === 'videos' ? '/library' : '/library'}
            style={{
              fontSize: '12px',
              fontWeight: 600,
              color: '#337AFF',
              textDecoration: 'none',
              padding: '7px 0',
            }}
          >
            Browse all →
          </Link>
        </div>

        {/* Panel Content */}
        <div style={{
          padding: '12px 24px',
          display: 'flex',
          gap: '12px',
          overflowX: 'auto',
          height: '110px',
          alignItems: 'center',
        }}>
          {/* My Projects Tab */}
          {activeBottomTab === 'projects' && (
            projects.length === 0 ? (
              <EmptyPanelState label="No projects yet. Start by typing a prompt above." />
            ) : (
              projects.slice(0, 10).map((p) => (
                <Link key={p.id} href={`/projects/${p.id}`} style={{
                  flexShrink: 0,
                  display: 'flex',
                  flexDirection: 'column',
                  justifyContent: 'flex-end',
                  width: '140px',
                  height: '80px',
                  borderRadius: '10px',
                  background: 'linear-gradient(135deg, #EBF1FF 0%, #E0EAFF 100%)',
                  border: '1px solid rgba(51,122,255,0.12)',
                  padding: '10px',
                  textDecoration: 'none',
                  overflow: 'hidden',
                  position: 'relative',
                  transition: 'transform 0.15s ease, box-shadow 0.15s ease',
                }}
                  onMouseEnter={(e) => { (e.currentTarget as HTMLElement).style.transform = 'translateY(-2px)'; (e.currentTarget as HTMLElement).style.boxShadow = '0 8px 20px rgba(51,122,255,0.15)'; }}
                  onMouseLeave={(e) => { (e.currentTarget as HTMLElement).style.transform = 'translateY(0)'; (e.currentTarget as HTMLElement).style.boxShadow = 'none'; }}
                >
                  {p.recent_previews?.[0]?.url && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={p.recent_previews[0].url} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: 0.5 }} />
                  )}
                  <span style={{ position: 'relative', fontSize: '11px', fontWeight: 700, color: '#0D1B3E', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.name}
                  </span>
                </Link>
              ))
            )
          )}

          {/* Recent Videos Tab */}
          {activeBottomTab === 'videos' && (
            recentVideos.length === 0 ? (
              <EmptyPanelState label="No videos yet. Ask the agent to generate one." />
            ) : (
              recentVideos.slice(0, 10).map((job, i) => (
                <div
                  key={job.id}
                  onClick={() => job.final_video_url && window.open(job.final_video_url)}
                  style={{
                    flexShrink: 0,
                    width: '140px',
                    height: '80px',
                    borderRadius: '10px',
                    background: `linear-gradient(135deg, hsl(${(i * 47) % 360}, 60%, 85%), hsl(${(i * 47 + 40) % 360}, 60%, 75%))`,
                    overflow: 'hidden',
                    cursor: 'pointer',
                    position: 'relative',
                    border: '1px solid rgba(0,0,0,0.06)',
                  }}
                >
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
              ))
            )
          )}

          {/* Recent Images Tab */}
          {activeBottomTab === 'images' && (
            <EmptyPanelState label="Recent images will appear here after generation." />
          )}

          {/* My Campaigns Tab */}
          {activeBottomTab === 'campaigns' && (
            campaigns.length === 0 ? (
              <EmptyPanelState label="No campaigns yet." />
            ) : (
              campaigns.slice(0, 10).map((c) => {
                const pct = c.total > 0 ? Math.round((c.success / c.total) * 100) : 0;
                return (
                  <div key={c.name} style={{
                    flexShrink: 0,
                    width: '180px',
                    height: '80px',
                    borderRadius: '10px',
                    background: 'white',
                    border: '1px solid rgba(51,122,255,0.1)',
                    padding: '10px 12px',
                    display: 'flex',
                    flexDirection: 'column',
                    justifyContent: 'space-between',
                  }}>
                    <span style={{ fontSize: '11px', fontWeight: 700, color: '#0D1B3E', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.name}</span>
                    <div>
                      <div style={{ height: '4px', background: 'rgba(51,122,255,0.12)', borderRadius: '2px', overflow: 'hidden', marginBottom: '4px' }}>
                        <div style={{ height: '100%', width: `${pct}%`, background: '#337AFF', borderRadius: '2px' }} />
                      </div>
                      <span style={{ fontSize: '10px', color: '#8A93B0' }}>{c.success}/{c.total} done</span>
                    </div>
                  </div>
                );
              })
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
