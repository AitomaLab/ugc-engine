"use client";

import { useState, useEffect } from "react";
import { getApiUrl, formatDate } from "@/lib/utils";

interface Job {
    id: string;
    status: string;
    progress: number;
    created_at: string;
    final_video_url?: string;
    error_message?: string;
}

const API_URL = getApiUrl();

export default function HistoryPage() {
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        async function fetchJobs() {
            try {
                const listResp = await fetch(`${API_URL}/jobs`);
                if (listResp.ok) setJobs(await listResp.json());
            } catch (err) {
                console.error("Failed to fetch jobs", err);
            } finally {
                setLoading(false);
            }
        }

        fetchJobs();
        const interval = setInterval(fetchJobs, 5000); // Polling every 5s
        return () => clearInterval(interval);
    }, []);

    if (loading && jobs.length === 0) return <div className="text-center py-20 opacity-50 italic">Retrieving archive...</div>;

    return (
        <div className="space-y-10">
            <header>
                <h2 className="text-3xl font-bold">Production <span className="gradient-text">Archive</span></h2>
                <p className="text-slate-400 mt-1">Track and manage your video generation history.</p>
            </header>

            <div className="glass-panel rounded-3xl border-slate-800 overflow-hidden">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-slate-900/50 border-b border-slate-800">
                            <th className="p-6 text-xs uppercase font-bold text-slate-500 tracking-tighter">Project</th>
                            <th className="p-6 text-xs uppercase font-bold text-slate-500 tracking-tighter">Status</th>
                            <th className="p-6 text-xs uppercase font-bold text-slate-500 tracking-tighter">Progress</th>
                            <th className="p-6 text-xs uppercase font-bold text-slate-500 tracking-tighter">Created</th>
                            <th className="p-6 text-xs uppercase font-bold text-slate-500 tracking-tighter">Action</th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-900">
                        {jobs.length === 0 ? (
                            <tr>
                                <td colSpan={5} className="p-20 text-center text-slate-600 italic">No production jobs found.</td>
                            </tr>
                        ) : (
                            jobs.map((job) => (
                                <tr key={job.id} className="hover:bg-slate-800/20 transition-colors">
                                    <td className="p-6">
                                        <p className="font-bold text-slate-200">{job.id.substring(0, 8)}...</p>
                                        <p className="text-xs text-slate-500 font-mono">{formatDate(job.created_at)}</p>
                                    </td>
                                    <td className="p-6">
                                        <span className={`px-3 py-1 rounded-full text-xs font-bold uppercase ${job.status === 'success' ? 'bg-green-500/10 text-green-400 border border-green-500/20' :
                                            job.status === 'failed' ? 'bg-red-500/10 text-red-400 border border-red-500/20' :
                                                'bg-blue-500/10 text-blue-400 border border-blue-500/20 animate-pulse'
                                            }`}>
                                            {job.status}
                                        </span>
                                    </td>
                                    <td className="p-6">
                                        <div className="w-40 bg-slate-800 h-2 rounded-full overflow-hidden">
                                            <div
                                                className={`h-full transition-all duration-500 ${job.status === 'success' ? 'bg-green-500' : 'bg-blue-500'}`}
                                                style={{ width: `${job.status === 'success' ? 100 : (job.status === 'failed' ? 100 : job.progress)}%` }}
                                            ></div>
                                        </div>
                                    </td>
                                    <td className="p-6 text-slate-400 text-sm">
                                        {new Date(job.created_at).toLocaleDateString()}
                                    </td>
                                    <td className="p-6">
                                        {job.final_video_url ? (
                                            <a
                                                href={job.final_video_url}
                                                target="_blank"
                                                className="text-blue-400 hover:text-white font-bold text-sm underline decoration-blue-500/50 underline-offset-4"
                                            >
                                                Preview Video
                                            </a>
                                        ) : (
                                            <span className="text-slate-600 text-sm italic">Processing...</span>
                                        )}
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
