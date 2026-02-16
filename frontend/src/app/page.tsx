"use client";

import { useState, useEffect } from "react";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Home() {
  const [metrics, setMetrics] = useState({
    videos_generated: 0,
    credits_spent: 0,
    status: "Offline"
  });

  useEffect(() => {
    async function fetchMetrics() {
      try {
        const resp = await fetch(`${API_URL}/metrics`);
        if (resp.ok) {
          setMetrics(await resp.json());
        }
      } catch (err) {
        console.error("Failed to fetch metrics", err);
      }
    }
    fetchMetrics();
    const interval = setInterval(fetchMetrics, 30000); // Update every 30s
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="space-y-12">
      {/* Header Section */}
      <section>
        <h2 className="text-4xl font-extrabold tracking-tight">
          Welcome back, <span className="gradient-text">Creator</span>
        </h2>
        <p className="text-slate-400 mt-2 text-lg">Your UGC production pipeline is standing by.</p>
      </section>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-panel p-6 rounded-2xl border-slate-800 glow-hover transition-all">
          <div className="flex items-center justify-between mb-4">
            <span className="text-blue-400 text-2xl">📹</span>
            <span className="text-xs font-bold text-slate-500 uppercase tracking-tighter">Usage</span>
          </div>
          <p className="text-3xl font-bold">{metrics.videos_generated}</p>
          <p className="text-sm text-slate-400 mt-1">Videos generated this month</p>
        </div>

        <div className="glass-panel p-6 rounded-2xl border-slate-800 glow-hover transition-all">
          <div className="flex items-center justify-between mb-4">
            <span className="text-purple-400 text-2xl">💎</span>
            <span className="text-xs font-bold text-slate-500 uppercase tracking-tighter">Budget</span>
          </div>
          <p className="text-3xl font-bold">${metrics.credits_spent}</p>
          <p className="text-sm text-slate-400 mt-1">Total API credits spent ($)</p>
        </div>

        <div className="glass-panel p-6 rounded-2xl border-slate-800 glow-hover transition-all border-blue-500/20 bg-blue-500/5">
          <div className="flex items-center justify-between mb-4">
            <span className="text-green-400 text-2xl">⚡</span>
            <span className="text-xs font-bold text-slate-500 uppercase tracking-tighter">Status</span>
          </div>
          <p className="text-3xl font-bold">{metrics.status}</p>
          <p className="text-sm text-slate-400 mt-1">Kie.ai & ElevenLabs healthy</p>
        </div>
      </div>

      {/* Quick Actions */}
      <section className="space-y-6">
        <h3 className="text-xl font-bold text-slate-100 flex items-center space-x-2">
          <span>🚀</span>
          <span>Quick Actions</span>
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          <a href="/generate" className="group glass-panel p-1 rounded-2xl border-slate-800 overflow-hidden glow-hover transition-all">
            <div className="bg-slate-900/50 p-8 rounded-[15px] h-full">
              <div className="text-4xl mb-6 transform group-hover:scale-110 transition-transform duration-300">🎭</div>
              <h4 className="text-2xl font-bold mb-2">Start Production</h4>
              <p className="text-slate-400 leading-relaxed">Combine influencers with app clips and generate ultra-realistic lip-synced videos in minutes.</p>
              <div className="mt-8 flex items-center text-blue-400 font-bold group-hover:translate-x-2 transition-transform">
                Generate Now <span className="ml-2">→</span>
              </div>
            </div>
          </a>

          <a href="/history" className="group glass-panel p-1 rounded-2xl border-slate-800 overflow-hidden glow-hover transition-all">
            <div className="bg-slate-900/50 p-8 rounded-[15px] h-full">
              <div className="text-4xl mb-6 transform group-hover:scale-110 transition-transform duration-300">📁</div>
              <h4 className="text-2xl font-bold mb-2">View History</h4>
              <p className="text-slate-400 leading-relaxed">Browse, preview and download your previously generated videos and assets.</p>
              <div className="mt-8 flex items-center text-slate-400 font-bold group-hover:translate-x-2 transition-transform">
                Open Gallery <span className="ml-2">→</span>
              </div>
            </div>
          </a>
        </div>
      </section>

      {/* Infrastructure Note */}
      <footer className="pt-12 border-t border-slate-900">
        <div className="glass-panel p-6 rounded-xl flex items-center space-x-6 text-sm text-slate-500">
          <div className="flex-1">
            <p className="font-bold text-slate-300 mb-1">Architecture Note</p>
            <p>Your generation engine is running in distributed mode. Heavy tasks (Kie.ai, FFmpeg) are offloaded to background workers to ensure UI responsiveness.</p>
          </div>
          <div className="flex space-x-4">
            <span className="px-2 py-1 rounded bg-slate-800 font-mono text-xs border border-slate-700">Next.js 15</span>
            <span className="px-2 py-1 rounded bg-slate-800 font-mono text-xs border border-slate-700">FastAPI</span>
            <span className="px-2 py-1 rounded bg-slate-800 font-mono text-xs border border-slate-700">Celery</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
