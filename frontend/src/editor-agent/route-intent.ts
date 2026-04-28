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

const EDIT_KEYWORDS = [
	'trim',
	'shorten',
	'edit this',
	'edit the',
	'adjust',
	'change volume',
	'change the volume',
	'set volume',
	'mute',
	'unmute',
	'add captions',
	'remove captions',
	'caption this',
	'caption the video',
	'add music',
	'background music',
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
	if (containsAny(msg, EDIT_KEYWORDS)) {
		return 'editor';
	}
	return 'managed';
}
