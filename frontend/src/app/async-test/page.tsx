'use client';

/**
 * Dev-only test page for the async-agent tracer (Layer 1).
 *
 * Navigate to /async-test while logged in. Uses the active project from
 * AppProvider (same source the rest of the app reads). Mounts AsyncAgentPanel
 * which talks to /creative-os/async-agent/dispatch-image.
 *
 * The existing /agent/* sync flow at /projects/[id] is unchanged. This page
 * exists ONLY for tracer validation and is not linked from the main UI.
 */
import { useEffect, useState } from 'react';
import { useApp } from '@/providers/AppProvider';
import { AsyncAgentPanel } from '@/components/studio/AsyncAgentPanel';
import { asyncAgentHealth } from '@/lib/async-agent-api';

export default function AsyncTestPage() {
	const { activeProject, projects } = useApp();
	const [healthOk, setHealthOk] = useState<boolean | null>(null);

	useEffect(() => {
		asyncAgentHealth().then(setHealthOk);
	}, []);

	const projectId = activeProject?.id || projects?.[0]?.id || '';

	if (!projectId) {
		return (
			<div className="p-6 text-zinc-300">
				<h1 className="mb-2 text-lg font-semibold">Async Agent — tracer</h1>
				<p>No active project found. Create or select a project first.</p>
			</div>
		);
	}

	if (healthOk === false) {
		return (
			<div className="p-6 text-zinc-300">
				<h1 className="mb-2 text-lg font-semibold">Async Agent — tracer</h1>
				<p className="text-red-400">
					/creative-os/async-agent/health is unreachable. Make sure the creative-os
					service is running on port 8001 and that migration 030_add_async_agent_jobs.sql
					has been applied.
				</p>
			</div>
		);
	}

	return (
		<div className="h-full bg-zinc-900 text-zinc-100">
			<AsyncAgentPanel projectId={projectId} />
		</div>
	);
}
