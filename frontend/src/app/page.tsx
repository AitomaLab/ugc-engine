"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { apiFetch } from "@/lib/utils";
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

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="flex flex-col items-center gap-3">
          <div className="w-6 h-6 rounded-full border-2 border-[#337AFF]/20 border-t-[#337AFF] animate-spin" />
          <span className="text-[#94A3B8] text-sm">Initializing Studio...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-10 animate-reveal">
      {/* ============ HERO WELCOME ============ */}
      <header className="mb-8">
        <h2 className="text-3xl font-bold tracking-tight text-[#1A1A1F]">
          {welcome.title.split("Creator")[0]}
          <span className="gradient-text">Creator</span>
        </h2>
        <p className="text-[#4A5568] mt-2 text-sm leading-relaxed max-w-xl">
          {welcome.subtitle}
        </p>
      </header>

      {/* ============ CAMPAIGN TRACKER ============ */}
      {campaigns.length > 0 && (
        <section>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-[#1A1A1F]">
              Campaign Tracker
            </h3>
            <Link
              href="/activity"
              className="text-xs text-[#337AFF] hover:text-[#337AFF]/80 transition-colors font-medium"
            >
              View All Activity →
            </Link>
          </div>

          <div className="space-y-3">
            {campaigns.slice(0, 5).map((campaign) => {
              const pct =
                campaign.total > 0
                  ? Math.round((campaign.success / campaign.total) * 100)
                  : 0;
              const isExpanded = expandedCampaign === campaign.name;

              return (
                <div key={campaign.name} className="glass rounded-2xl overflow-hidden shadow-card">
                  <button
                    onClick={() =>
                      setExpandedCampaign(isExpanded ? null : campaign.name)
                    }
                    className="w-full p-5 text-left hover:bg-[#337AFF]/3 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <p className="font-semibold text-sm text-[#1A1A1F]">
                          {campaign.name}
                        </p>
                        <p className="text-xs text-[#94A3B8] mt-0.5">
                          {campaign.success} of {campaign.total} videos complete
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {campaign.success > 0 && (
                          <span className="badge badge-success">
                            {campaign.success}
                          </span>
                        )}
                        {campaign.processing > 0 && (
                          <span className="badge badge-processing">
                            {campaign.processing}
                          </span>
                        )}
                        {campaign.pending > 0 && (
                          <span className="badge badge-pending">
                            {campaign.pending}
                          </span>
                        )}
                        {campaign.failed > 0 && (
                          <span className="badge badge-failed">
                            {campaign.failed}
                          </span>
                        )}
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          className={`text-[#94A3B8] transition-transform ${isExpanded ? "rotate-180" : ""}`}
                        >
                          <path d="M6 9l6 6 6-6" />
                        </svg>
                      </div>
                    </div>
                    <div className="progress-bar">
                      <div
                        className="progress-bar-fill bg-blue-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </button>

                  {isExpanded && (
                    <div className="border-t border-[#E8ECF4] bg-[#F0F4FF]/50">
                      {campaign.jobs.map((job) => (
                        <div
                          key={job.id}
                          className="flex items-center justify-between px-5 py-3 border-b border-[#E8ECF4] last:border-0"
                        >
                          <div className="flex items-center gap-3">
                            <span className="text-xs text-[#94A3B8] font-mono">
                              {job.id.substring(0, 8)}
                            </span>
                            <span className="text-xs text-[#4A5568]">
                              {influencerMap.get(job.influencer_id || "")?.name ?? "—"}
                            </span>
                          </div>
                          <div className="flex items-center gap-3">
                            <span
                              className={`badge badge-${job.status === "success" ? "success" : job.status === "failed" ? "failed" : job.status === "processing" ? "processing" : "pending"}`}
                            >
                              {job.status}
                            </span>
                            {job.final_video_url && (
                              <a
                                href={job.final_video_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-[#337AFF] hover:text-[#337AFF]/70 font-medium"
                              >
                                Preview
                              </a>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ============ FRESH FROM THE ENGINE ============ */}
      {recentVideos.length > 0 && (
        <section>
          <h3 className="text-lg font-semibold text-[#1A1A1F] mb-4">
            Fresh from the Engine
          </h3>
          <div
            ref={carouselRef}
            className="flex gap-4 overflow-x-auto pb-4 snap-x snap-mandatory"
            style={{ scrollbarWidth: "thin" }}
          >
            {recentVideos.map((video) => (
              <div
                key={video.id}
                className="video-card flex-shrink-0 w-48 snap-start cursor-pointer group"
              >
                <div className="relative aspect-[9/16] bg-[#1A1A1F] overflow-hidden rounded-t-2xl">
                  {video.final_video_url ? (
                    <video
                      src={video.final_video_url}
                      muted
                      loop
                      playsInline
                      preload="metadata"
                      className="w-full h-full object-cover"
                      onMouseEnter={(e) =>
                        (e.target as HTMLVideoElement).play().catch(() => { })
                      }
                      onMouseLeave={(e) => {
                        const v = e.target as HTMLVideoElement;
                        v.pause();
                        v.currentTime = 0;
                      }}
                    />
                  ) : (
                    <div className="w-full h-full flex items-center justify-center text-[#94A3B8]">
                      <svg
                        width="32"
                        height="32"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="1.5"
                      >
                        <polygon points="5 3 19 12 5 21 5 3" />
                      </svg>
                    </div>
                  )}
                  {/* Duration badge */}
                  <div className="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] px-2 py-0.5 rounded-md font-medium">
                    15s
                  </div>
                </div>
                <div className="p-3">
                  <p className="text-xs font-medium text-[#1A1A1F] truncate">
                    {influencerMap.get(video.influencer_id || "")?.name ?? "Video"}
                  </p>
                  <p className="text-[10px] text-[#94A3B8] mt-0.5">
                    {new Date(video.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ============ QUICK ACTIONS ============ */}
      <section>
        <h3 className="text-lg font-semibold text-[#1A1A1F] mb-4">
          Quick Actions
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {!hasInfluencers && (
            <Link href="/library" className="glass rounded-2xl p-5 block shadow-card hover:shadow-card-hover hover:-tranreveal-0.5 transition-all duration-300">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style={{ background: 'linear-gradient(135deg, rgba(51,122,255,0.12), rgba(107,95,228,0.12))' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#337AFF" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
              </div>
              <p className="font-semibold text-sm text-[#1A1A1F]">
                Create Your First Influencer
              </p>
              <p className="text-xs text-[#94A3B8] mt-1">
                Add an AI influencer profile to start generating
              </p>
            </Link>
          )}
          {hasInfluencers && !hasScripts && (
            <Link href="/library" className="glass rounded-2xl p-5 block shadow-card hover:shadow-card-hover hover:-tranreveal-0.5 transition-all duration-300">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style={{ background: 'linear-gradient(135deg, rgba(51,122,255,0.12), rgba(107,95,228,0.12))' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#337AFF" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
              </div>
              <p className="font-semibold text-sm text-[#1A1A1F]">
                Build Your Script Library
              </p>
              <p className="text-xs text-[#94A3B8] mt-1">
                Add scripts for your videos to use
              </p>
            </Link>
          )}
          {hasInfluencers && hasScripts && !hasClips && (
            <Link href="/library" className="glass rounded-2xl p-5 block shadow-card hover:shadow-card-hover hover:-tranreveal-0.5 transition-all duration-300">
              <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style={{ background: 'linear-gradient(135deg, rgba(51,122,255,0.12), rgba(107,95,228,0.12))' }}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#337AFF" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="2" width="20" height="20" rx="2.18" ry="2.18"/><line x1="7" y1="2" x2="7" y2="22"/><line x1="17" y1="2" x2="17" y2="22"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="2" y1="7" x2="7" y2="7"/><line x1="2" y1="17" x2="7" y2="17"/><line x1="17" y1="7" x2="22" y2="7"/><line x1="17" y1="17" x2="22" y2="17"/></svg>
              </div>
              <p className="font-semibold text-sm text-[#1A1A1F]">
                Upload App Clips
              </p>
              <p className="text-xs text-[#94A3B8] mt-1">
                Add app footage for seamless integration
              </p>
            </Link>
          )}
          {hasInfluencers && hasScripts && (
            <>
              <Link href="/create" className="glass rounded-2xl p-5 block shadow-card hover:shadow-card-hover hover:-tranreveal-0.5 transition-all duration-300">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style={{ background: 'linear-gradient(135deg, rgba(51,122,255,0.12), rgba(107,95,228,0.12))' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#337AFF" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/></svg>
                </div>
                <p className="font-semibold text-sm text-[#1A1A1F]">
                  {activeCampaigns.length > 0
                    ? "Create Another Campaign"
                    : "Launch Your First Campaign"}
                </p>
                <p className="text-xs text-[#94A3B8] mt-1">
                  Generate single or bulk UGC videos
                </p>
              </Link>
              <Link href="/library" className="glass rounded-2xl p-5 block shadow-card hover:shadow-card-hover hover:-tranreveal-0.5 transition-all duration-300">
                <div className="w-10 h-10 rounded-xl flex items-center justify-center mb-3" style={{ background: 'linear-gradient(135deg, rgba(51,122,255,0.12), rgba(107,95,228,0.12))' }}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#337AFF" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5A2.5 2.5 0 016.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z"/></svg>
                </div>
                <p className="font-semibold text-sm text-[#1A1A1F]">
                  Browse Library
                </p>
                <p className="text-xs text-[#94A3B8] mt-1">
                  View your videos, scripts, and assets
                </p>
              </Link>
            </>
          )}
        </div>
      </section>

      {/* ============ SYSTEM HEALTH ============ */}
      <section>
        <h3 className="text-lg font-semibold text-[#1A1A1F] mb-4">
          System Health
        </h3>
        <div className="glass rounded-2xl p-6 shadow-card">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[#94A3B8] font-semibold mb-2">
                API Status
              </p>
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-[#10B981] animate-pulse" />
                <span className="text-sm text-[#10B981] font-medium">
                  Operational
                </span>
              </div>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[#94A3B8] font-semibold mb-2">
                Queue
              </p>
              <p className="text-sm text-[#1A1A1F] font-medium">
                {stats?.pending ?? 0} pending ·{" "}
                {stats?.processing ?? 0} processing
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[#94A3B8] font-semibold mb-2">
                Total Videos
              </p>
              <p className="text-sm text-[#1A1A1F] font-medium">
                {stats?.success ?? 0}{" "}
                <span className="text-[#94A3B8]">completed</span>
              </p>
            </div>
            <div>
              <p className="text-[10px] uppercase tracking-wider text-[#94A3B8] font-semibold mb-2">
                Success Rate
              </p>
              <p className="text-sm text-[#1A1A1F] font-medium">
                {stats && stats.total_jobs > 0
                  ? `${Math.round((stats.success / stats.total_jobs) * 100)}%`
                  : "—"}
              </p>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
