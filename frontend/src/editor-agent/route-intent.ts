export type EditorAgentRoute = 'managed' | 'editor';

const GENERATION_KEYWORDS = [
	'generate',
	'create a',
	'create new',
	'create an',
	'combine',
	'new video',
	'new clip',
	'new ad',
	'ugc ad',
	'produce',
	'write a script',
	'make a video',
	'make me a',
	// Re-generation intents — these require a fresh render via the managed
	// agent (create_ugc_video / extend_video / generate_video), NOT a
	// timeline-ops edit. Without this, "redo / regenerate" got routed to the
	// editor-AI module and confused users with a 503.
	'redo',
	're-do',
	'regenerate',
	're-generate',
	'remake',
	're-make',
	'rerun',
	're-run',
	'do it again',
	'try again',
];

// Generative / pixel-level edits that ONLY the managed agent's edit_video
// (Gemini Omni) tool can do — adding or removing objects/accessories, changing
// the background or scene, inserting a person, camera-angle / mood / VFX edits,
// etc. These must NEVER route to the deterministic timeline editor (which can
// only trim / caption / re-time / re-position existing footage). Checked BEFORE
// EDIT_KEYWORDS so a phrase like "edit the video by adding a hat" stays managed.
// Phrases carry leading spaces where a bare token would false-match (e.g. " hat"
// avoids matching "what" / "that" / "chat").
const GENERATIVE_EDIT_KEYWORDS = [
	'add a ', 'add an ', 'add some ', 'adding ',
	'remove the ', 'remove a ', 'remove an ', 'erase ', 'get rid of',
	'change the background', 'change background', 'replace the background', 'background to ',
	'change the scene', 'change scene', 'change the setting', 'different scene',
	'put me in', 'put him in', 'put her in', 'put them in', 'insert ',
	'make him wear', 'make her wear', 'make them wear', 'wear a ', 'wearing ',
	' hat', 'sunglasses', 'change the clothes', 'change his outfit', 'change her outfit',
	'camera angle', 'change the angle', 'different angle', 'zoom into', 'zoom in on',
	'vfx', 'visual effect', 'transform ', 'make it look like', 'turn it into',
	'change the mood', 'change the lighting', 'color grade', 'recolor',
	'replace the', 'swap the', 'put a ',
];

const EDIT_KEYWORDS = [
	'trim',
	'shorten',
	'change volume',
	'change the volume',
	'set volume',
	'mute',
	'unmute',
	// "add captions" / "subtitles" / "caption this" intentionally NOT in this
	// list. Post-delivery captions belong to the managed agent's caption_video
	// (Whisper transcription + burn + re-render) and list_caption_styles tools,
	// not the Remotion editor-AI module (which only proposes AI_EDIT_OPS for
	// manual apply and requires ANTHROPIC_API_KEY on the frontend). See
	// AgentPanel handleRun for the auto video-ref injection on caption intents.
	// "add music" / "background music" intentionally NOT in this list. The
	// managed agent's combine_videos(music_prompt=...) tool is the working,
	// production path for adding a soundtrack to a finished video (Suno V4
	// generation + ffmpeg mix), and is what the original video-generation
	// pipeline uses. Routing music intents to the editor-AI module instead
	// produced an AI_EDIT_OPS marker that only the in-editor side panel can
	// apply, and the editor's /api/editor/music endpoint hangs on the same
	// 8-minute synchronous Suno poll. See AgentPanel handleRun for the auto
	// video-ref injection that gives the managed agent the right context.
	'add text',
	'change text',
	'set text',
	'slower',
	'faster',
	'speed up',
	'slow down',
	'fade in',
	'fade out',
	'opacity',
	'resize',
	'reposition',
	'move the',
	'delete this',
	'remove this clip',
	'remove the clip',
	'crop',
	'rotate',
];

const containsAny = (text: string, list: string[]): boolean => {
	const lower = text.toLowerCase();
	return list.some((kw) => lower.includes(kw));
};

export function classifyEditorAgentRoute(
	latestUserMessage: string | null | undefined,
	jobId: string | null | undefined,
): EditorAgentRoute {
	if (!jobId) {
		return 'managed';
	}
	const msg = (latestUserMessage || '').trim();
	if (!msg) {
		return 'managed';
	}
	if (containsAny(msg, GENERATION_KEYWORDS)) {
		return 'managed';
	}
	// Generative pixel edits (add a hat, change the background, insert a person…)
	// belong to the managed agent's edit_video tool, never the timeline editor —
	// even when the prompt also starts with "edit the video…".
	if (containsAny(msg, GENERATIVE_EDIT_KEYWORDS)) {
		return 'managed';
	}
	if (containsAny(msg, EDIT_KEYWORDS)) {
		return 'editor';
	}
	return 'managed';
}
