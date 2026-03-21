"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "@/lib/utils";
import { useApp } from "@/providers/AppProvider";
import Link from "next/link";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Stats {
  total_jobs: number;
  pending: number;
  processing: number;
  success: number;
  failed: number;
  influencers: number;
  scripts: number;
  app_clips: number;
  projects?: number;
}

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
// Studio Page
// ---------------------------------------------------------------------------

export default function StudioPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [influencers, setInfluencers] = useState<Influencer[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedCampaign, setExpandedCampaign] = useState<string | null>(null);
  const carouselRef = useRef<HTMLDivElement>(null);
  const { profile } = useApp();
  const userName = profile?.name || profile?.email?.split('@')[0] || 'Creator';

  const fetchData = useCallback(async () => {
    try {
      const [statsData, jobsData, infData] = await Promise.all([
        apiFetch<Stats>("/stats"),
        apiFetch<Job[]>("/jobs?limit=100"),
        apiFetch<Influencer[]>("/influencers"),
      ]);
      setStats(statsData);
      setJobs(jobsData);
      setInfluencers(infData);
    } catch (err) {
      console.error("Studio fetch error:", err);
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
    .slice(0, 5);

  const activeCampaigns = campaigns.filter(
    (c) => c.processing > 0 || c.pending > 0
  );
  const hasInfluencers = (stats?.influencers ?? 0) > 0;
  const hasScripts = (stats?.scripts ?? 0) > 0;
  const hasClips = (stats?.app_clips ?? 0) > 0;

  // Influencer name lookup
  const influencerMap = new Map(influencers.map((i) => [i.id, i]));

  // ---------------------------------------------------------------------------
  // Welcome Message
  // ---------------------------------------------------------------------------

  function getWelcome(): { title: string; subtitle: string } {
    if (activeCampaigns.length > 0) {
      const c = activeCampaigns[0];
      const pct = c.total > 0 ? Math.round((c.success / c.total) * 100) : 0;
      return {
        title: `Welcome back, Creator`,
        subtitle: `Your "${c.name}" campaign is ${pct}% complete — ${c.processing + c.pending} videos still in the pipeline.`,
      };
    }
    if (recentVideos.length > 0) {
      return {
        title: "Welcome back, Creator",
        subtitle: `You have ${recentVideos.length} freshly baked videos. Your pipeline is ready for more.`,
      };
    }
    return {
      title: "Welcome, Creator",
      subtitle: "Your production pipeline is ready. What will you create today?",
    };
  }

  const welcome = getWelcome();
  const successRate = stats && stats.total_jobs > 0
    ? Math.round((stats.success / stats.total_jobs) * 100)
    : 0;

  const formatDate = (d: string) => new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

  if (loading) {
    return (
      <div className="content-area">
        <div className="empty-state">
          <div className="empty-title">Initializing Studio...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="content-area">
      <div className="page-header">
        <h1 style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          Good morning, <span style={{ color: 'var(--blue)' }}>{userName}</span>
        </h1>
        <p>{welcome.subtitle}</p>
      </div>

      {/* Stats Row */}
      <div className="stats-row">
        <div className="stat-card">
          <div className="stat-label">Total Videos</div>
          <div className="stat-value">{stats?.total_jobs ?? 0}</div>
          <div className="stat-sub">All time</div>
          {(stats?.total_jobs ?? 0) > 0 && <div className="stat-badge up">+{stats!.total_jobs} generated</div>}
        </div>
        <div className="stat-card">
          <div className="stat-label">Active Campaigns</div>
          <div className="stat-value">{stats?.processing ?? 0}</div>
          <div className="stat-sub">Currently generating</div>
          {(stats?.pending ?? 0) > 0 && <div className="stat-badge blue">{stats!.pending} in queue</div>}
        </div>
        <div className="stat-card">
          <div className="stat-label">Success Rate</div>
          <div className="stat-value">{successRate}%</div>
          <div className="stat-sub">Last 30 days</div>
          <div className="stat-badge up">{stats?.success ?? 0} completed</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">AI Influencers</div>
          <div className="stat-value">{stats?.influencers ?? 0}</div>
          <div className="stat-sub">Active profiles</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Scripts</div>
          <div className="stat-value">{stats?.scripts ?? 0}</div>
          <div className="stat-sub">In library</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Projects</div>
          <div className="stat-value">{stats?.projects ?? 0}</div>
          <div className="stat-sub">Active</div>
        </div>
      </div>

      {/* Campaign Tracker */}
      {campaigns.length > 0 ? (
        <div className="tracker-card">
          <div className="section-title">
            Campaign Tracker
            <Link href="/activity">View all</Link>
          </div>
          <div className="tracker-scroll">
            {campaigns.slice(0, 8).map(campaign => {
              const pct = campaign.total > 0 ? Math.round((campaign.success / campaign.total) * 100) : 0;
              const statusClass = campaign.processing > 0 ? 'active' : campaign.pending > 0 ? 'pending' : campaign.failed > 0 ? 'failed' : 'done';
              const statusLabel = campaign.processing > 0 ? 'Processing' : campaign.pending > 0 ? 'Queued' : campaign.failed > 0 ? 'Failed' : 'Complete';
              return (
                <div key={campaign.name} className="campaign-row">
                  <div className="campaign-thumb" style={{ background: 'var(--blue-light)' }}>
                    <svg viewBox="0 0 24 24"><polygon points="23 7 16 12 23 17 23 7" /><rect x="1" y="5" width="15" height="14" rx="2" /></svg>
                  </div>
                  <div className="campaign-info">
                    <div className="campaign-name">{campaign.name}</div>
                    <div className="campaign-meta">{campaign.total} videos · {campaign.success} completed</div>
                  </div>
                  <div className="campaign-progress">
                    <div className="prog-bar">
                      <div className="prog-fill" style={{ width: `${pct}%` }} />
                    </div>
                    <div className="prog-label">{campaign.success}/{campaign.total} done</div>
                  </div>
                  <div className={`status-pill ${statusClass}`}>{statusLabel}</div>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <div className="tracker-card">
          <div className="section-title">Campaign Tracker</div>
          <div className="empty-state" style={{ padding: '32px 20px' }}>
            <div className="empty-icon">
              <svg viewBox="0 0 24 24"><polygon points="23 7 16 12 23 17 23 7" /><rect x="1" y="5" width="15" height="14" rx="2" /></svg>
            </div>
            <div className="empty-title">No campaigns yet</div>
            <div className="empty-sub">Launch your first video campaign to track progress here.</div>
            <Link href="/create" style={{ display: 'inline-block', marginTop: '12px', padding: '8px 20px', background: 'var(--blue)', color: 'white', borderRadius: '8px', fontSize: '13px', fontWeight: 600, textDecoration: 'none' }}>
              + Create Your First Video
            </Link>
          </div>
        </div>
      )}

      {/* Recent Videos */}
      {recentVideos.length > 0 ? (
        <>
          <div className="section-title">
            Recent Videos
            <Link href="/library">View all</Link>
          </div>
          <div className="video-grid">
            {recentVideos.map((job, i) => (
              <div key={job.id} className="video-card" onClick={() => job.final_video_url && window.open(job.final_video_url)}>
                <div className={`video-thumb grad-${(i % 5) + 1}`}>
                  {job.final_video_url && (
                    <video
                      src={job.final_video_url}
                      style={{ width: '100%', height: '100%', objectFit: 'cover', position: 'absolute', top: 0, left: 0 }}
                      muted loop playsInline
                      onMouseEnter={(e) => (e.target as HTMLVideoElement).play().catch(() => { })}
                      onMouseLeave={(e) => { const v = e.target as HTMLVideoElement; v.pause(); v.currentTime = 0; }}
                    />
                  )}
                  <div className="play-overlay">
                    <div className="play-btn">
                      <svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21" /></svg>
                    </div>
                  </div>
                </div>
                <div className="video-info">
                  <div className="video-name">{influencerMap.get(job.influencer_id ?? '')?.name ?? 'Unknown'} — {job.campaign_name ?? 'Single'}</div>
                  <div className="video-date">{formatDate(job.created_at ?? '')}</div>
                </div>
              </div>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="section-title">Recent Videos</div>
          <div className="empty-state" style={{ padding: '32px 20px', background: 'white', borderRadius: '12px', border: '1px solid var(--border)' }}>
            <div className="empty-icon">
              <svg viewBox="0 0 24 24"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18" /><line x1="7" y1="2" x2="7" y2="22" /><line x1="17" y1="2" x2="17" y2="22" /><line x1="2" y1="12" x2="22" y2="12" /><line x1="2" y1="7" x2="7" y2="7" /><line x1="2" y1="17" x2="7" y2="17" /><line x1="17" y1="7" x2="22" y2="7" /><line x1="17" y1="17" x2="22" y2="17" /></svg>
            </div>
            <div className="empty-title">No videos yet</div>
            <div className="empty-sub">Your generated videos will appear here. Create your first one!</div>
            <Link href="/create" style={{ display: 'inline-block', marginTop: '12px', padding: '8px 20px', background: 'var(--blue)', color: 'white', borderRadius: '8px', fontSize: '13px', fontWeight: 600, textDecoration: 'none' }}>
              + Create Your First Video
            </Link>
          </div>
        </>
      )}
    </div>
  );
}

