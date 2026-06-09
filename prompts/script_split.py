"""Shared script splitting utilities for multi-scene UGC videos."""


def is_script_imbalanced(parts, num_scenes, max_words=23, ratio_threshold=1.3):
    """Return True when scene word counts are too uneven for equal 8s pacing."""
    if not parts or num_scenes <= 1:
        return False
    counts = [len(p.split()) for p in parts if p.strip()]
    if not counts:
        return False
    if any(c > max_words for c in counts):
        return True
    min_c, max_c = min(counts), max(counts)
    if min_c == 0:
        return max_c > 0
    return (max_c / min_c) > ratio_threshold


def split_items_proportionally(items, num_veo_scenes, ctx):
    """Split a list of words (or sentences) into N scenes by WORD COUNT,
    snapping to sentence boundaries when one is nearby.

    Previous behavior split by ITEM COUNT proportional to scene durations,
    which produced massively uneven scenes when the input was sentences of
    very different lengths (a 6-word sentence + a 29-word sentence both
    counted as "1 item"). The result was a 6-word scene with 7 seconds of
    Veo-invented filler hallucinations and a 29-word scene that had to
    rush at >3.5 words/sec and degraded badly.

    New algorithm:
      1. Flatten everything to a word list (joining sentences with the
         original punctuation preserved).
      2. Compute target words per scene = total_words / num_scenes,
         weighted by per-scene duration (Veo = equal 8s, Seedance varies).
      3. Walk the word list; once we've collected ~target words for the
         current scene, snap forward/back to the nearest sentence-ending
         punctuation (.!?) within ±20% of target. If no boundary is
         within tolerance, break mid-sentence rather than ship a wildly
         imbalanced split.
    """
    ai_durations = []
    model_api = ctx.get("model_api", "")

    if "seedance" in model_api.lower():
        import config
        product_type = ctx.get("product_type", "digital")
        video_length = ctx.get("video_length", "30s")
        s_cfg = config.get_seedance_durations(video_length, product_type)
        for sc in s_cfg["scenes"]:
            if sc.get("has_video_input") is not None:
                ai_durations.append(sc["duration"])
        ai_durations = ai_durations[:num_veo_scenes]
    else:
        ai_durations = [8] * num_veo_scenes
    while len(ai_durations) < num_veo_scenes:
        ai_durations.append(8)

    total_ai_dur = sum(ai_durations) or 1

    full_text = " ".join(items).strip()
    if not full_text:
        return [""] * num_veo_scenes
    words = full_text.split()
    total_words = len(words)
    if total_words == 0:
        return [""] * num_veo_scenes

    if total_words < num_veo_scenes * 3:
        parts = []
        chunk = max(1, total_words // num_veo_scenes)
        for i in range(num_veo_scenes):
            start = i * chunk
            end = start + chunk if i < num_veo_scenes - 1 else total_words
            parts.append(" ".join(words[start:end]))
        return parts

    targets = [int(round(total_words * (d / total_ai_dur))) for d in ai_durations]
    while sum(targets) < total_words:
        targets[targets.index(min(targets))] += 1
    while sum(targets) > total_words:
        targets[targets.index(max(targets))] -= 1

    parts = []
    cursor = 0
    for i in range(num_veo_scenes):
        if i == num_veo_scenes - 1:
            parts.append(" ".join(words[cursor:]))
            break
        target = targets[i]
        boundary = cursor + target
        tolerance = max(2, int(target * 0.2))
        best = None
        for offset in range(-tolerance, tolerance + 1):
            candidate = cursor + target + offset
            if candidate <= cursor or candidate >= total_words:
                continue
            tail = words[candidate - 1].rstrip('"\')]')
            if tail and tail[-1] in ".!?":
                if best is None or abs(offset) < abs(best - cursor - target):
                    best = candidate
        if best is not None:
            boundary = best
        parts.append(" ".join(words[cursor:boundary]))
        cursor = boundary
    return parts
