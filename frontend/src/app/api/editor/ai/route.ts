import Anthropic from '@anthropic-ai/sdk';
import { NextRequest, NextResponse } from 'next/server';

const MODEL =
  process.env.ANTHROPIC_MODEL || 'claude-sonnet-4-20250514';

const SYSTEM = `You are a concise assistant for a Remotion-based video editor. You receive a JSON snapshot of the timeline including fps, composition size, duration, tracks, and items (with ids, type, timing, fades, volume and text previews when available). Never invent item IDs — only use ids from CURRENT_TIMELINE_JSON.

The app does not re-encode media files; it edits timeline metadata only. Prefer frame-accurate edits and use fps from JSON for conversions.

When proposing edits the user can apply in one click, end your message with a line containing exactly:
AI_EDIT_OPS
Then a single valid JSON array (nothing after it). Example:
[{"op":"set_opacity","itemId":"…","opacity":0.85}]

Allowed ops (combine multiple objects in order when needed):
- set_opacity: itemId, opacity (0–1). Any clip.
- set_playback_rate: itemId, playbackRate (> 0). Types video, gif, or audio only.
- set_volume_db: itemId, decibelAdjustment (-60 to 20). Types video or audio only.
- delete_items: itemIds (string array, 1–40 ids). Removes clips from the timeline.
- set_timeline_span: itemId, optional from (start frame, integer ≥ 0), optional durationInFrames (integer ≥ 1). At least one of from or durationInFrames required.
- set_fade: itemId, optional fadeInDurationInSeconds, optional fadeOutDurationInSeconds. For video, gif, image, text.
- set_audio_fade: itemId, optional audioFadeInDurationInSeconds, optional audioFadeOutDurationInSeconds. For video or audio.
- set_text_content: itemId, text. For text items only.
- set_position_size: itemId, optional left, top, width, height (canvas pixels).
- set_media_start: itemId, mediaStartInSeconds. Sets the source start offset for video/gif/audio.
- add_text: text (string), optional from (frame), optional durationInFrames. Creates centered text on the canvas; default from/duration chosen if omitted.
- add_music: optional mood, optional duration (seconds), optional volume (0..1), optional position ("background").
- add_captions: optional language (BCP-47, default "en"), optional style ("default" | "bold" | "minimal"), optional position ("bottom" | "top" | "center"), optional highlight_words (boolean).

For requests like trim/shorten/extend/move:
- Use set_timeline_span.
- To trim from source start, use set_media_start as well.

Rules:
- Preserve user intent but keep edits minimal.
- Use only ids that exist in CURRENT_TIMELINE_JSON.
- If user request is ambiguous, ask one short clarification question and do not emit AI_EDIT_OPS.
- If you are not proposing runnable edits, do not include AI_EDIT_OPS or JSON.
- Never claim edits are already applied/completed/done unless you include AI_EDIT_OPS with executable operations.
- In this UI, edits are only applied after user approval. Your job is to propose executable operations, not to claim successful application.
- For any direct edit request (trim/move/opacity/music/captions/text/position/speed), prefer returning AI_EDIT_OPS over plain prose.

You can also add background music and captions to the user's video.
When the user asks for music, use the add_music tool.
When the user asks for captions, subtitles, or text from speech, use the add_captions tool.
Always confirm what you plan to add after user approval and offer to adjust parameters like mood, language, or style if needed.`;

type ChatTurn = { role: 'user' | 'assistant'; content: string };

const AI_EDIT_OPS_MARKER = 'AI_EDIT_OPS';

function extractTextFromMessage(
  content: Anthropic.Message['content'],
): string {
  if (typeof content === 'string') {
    return content;
  }
  return content
    .filter((b): b is Anthropic.TextBlock => b.type === 'text')
    .map((b) => b.text)
    .join('');
}

function hasExecutableOps(text: string): boolean {
  const match = text.match(
    /(?:^|\n)\s*AI_EDIT_OPS\s*:?\s*\n([\s\S]*)$/m,
  );
  if (!match) {
    return false;
  }
  let jsonText = match[1].trim();
  const fencedMatch = jsonText.match(/^```(?:json)?\s*([\s\S]*?)\s*```$/i);
  if (fencedMatch) {
    jsonText = fencedMatch[1].trim();
  }
  try {
    const parsed = JSON.parse(jsonText);
    return Array.isArray(parsed) && parsed.length > 0;
  } catch {
    return false;
  }
}

function isLikelyEditIntent(input: string): boolean {
  const text = input.toLowerCase();
  return /\b(add|apply|change|edit|update|modify|move|trim|cut|split|delete|remove|replace|speed|slow|faster|opacity|fade|volume|music|soundtrack|captions?|subtitles?|text|position|resize|crop)\b/.test(
    text,
  );
}

export async function POST(request: NextRequest) {
  const apiKey = process.env.ANTHROPIC_API_KEY?.trim();
  if (!apiKey) {
    return NextResponse.json(
      {
        error:
          'ANTHROPIC_API_KEY is not set. Add it to frontend/.env.local and restart the dev server.',
      },
      { status: 503 },
    );
  }

  let body: {
    messages?: ChatTurn[];
    timelineContext?: string;
  };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'Invalid JSON body' }, { status: 400 });
  }

  const messages = body.messages;
  const timelineContext =
    typeof body.timelineContext === 'string' ? body.timelineContext : '';

  if (!Array.isArray(messages) || messages.length === 0) {
    return NextResponse.json(
      { error: 'messages must be a non-empty array' },
      { status: 400 },
    );
  }

  for (const m of messages) {
    if (
      !m ||
      (m.role !== 'user' && m.role !== 'assistant') ||
      typeof m.content !== 'string'
    ) {
      return NextResponse.json(
        { error: 'Each message needs role user|assistant and string content' },
        { status: 400 },
      );
    }
  }

  const anthropic = new Anthropic({ apiKey });

  const systemWithTimeline = `${SYSTEM}

CURRENT_TIMELINE_JSON:
${timelineContext || '{}'}`;

  try {
    const response = await anthropic.messages.create({
      model: MODEL,
      max_tokens: 4096,
      system: systemWithTimeline,
      messages: messages.map((m) => ({
        role: m.role,
        content: m.content,
      })),
    });

    let text = extractTextFromMessage(response.content);
    const latestUserMessage = [...messages]
      .reverse()
      .find((m) => m.role === 'user')?.content;

    if (
      latestUserMessage &&
      isLikelyEditIntent(latestUserMessage) &&
      !hasExecutableOps(text)
    ) {
      const repair = await anthropic.messages.create({
        model: MODEL,
        max_tokens: 4096,
        system: systemWithTimeline,
        messages: [
          ...messages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
          {role: 'assistant', content: text},
          {
            role: 'user',
            content:
              `Return executable timeline steps only. Do not claim completion. ` +
              `Respond with an optional short explanation, then a line with exactly ${AI_EDIT_OPS_MARKER}, then one valid JSON array using only allowed ops and existing item IDs.`,
          },
        ],
      });
      const repairedText = extractTextFromMessage(repair.content);
      if (hasExecutableOps(repairedText)) {
        text = repairedText;
      }
    }

    return NextResponse.json({ text });
  } catch (err) {
    const message =
      err instanceof Error ? err.message : 'Anthropic request failed';
    return NextResponse.json({ error: message }, { status: 502 });
  }
}
