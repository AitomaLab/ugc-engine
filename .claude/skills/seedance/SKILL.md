---
name: seedance-app-promo
description: Generate glossy liquid-glass motion-graphics promo clips of an app or website using ByteDance Seedance 2.0 via Kie.ai. Covers image-to-video, reference-to-video (multi-screenshot), text-to-video, liquid-glass prompting, App Store screenshot scraping, and the full pipeline from screenshot to finished promo clip. Invoke ONLY when the user explicitly asks for an app promo, marketing motion-graphics clip, liquid-glass video, landing-page hero video, or similar app/brand promotional content. Do NOT use for UGC, product-pipeline, or product-ad work — this repo has a dedicated Seedance director for those at services/creative-os/prompts/seedance_director.txt. Triggers: seedance skill, app promo, liquid glass, motion graphics promo.
---

# Seedance — App Promo Motion Graphics Skill (Kie.ai)

Generate cinematic motion-graphics promo videos using ByteDance's Seedance 2.0 model via **Kie.ai**. Turn app screenshots into glossy liquid-glass promo videos, controlled from Claude Code.

This skill is **isolated from the ugc-engine product pipeline**. It exists for making marketing promos of the Aitoma Studio app itself (landing-page hero clips, launch announcements, etc.). It does NOT share code, prompts, or configuration with the product's Seedance pipeline (`services/creative-os/`). Use the product pipeline for anything user-facing in the SaaS; use this skill only when the user explicitly asks for an app-promo motion-graphics clip.

## What This Skill Does

- Generate **image-to-video** animations from a single image (with optional end-frame control for A→B transitions)
- Generate **reference-to-video** motion graphics from multiple app screenshots
- Generate **text-to-video** motion graphics from pure prompts
- Scrape **App Store screenshots** automatically for any iOS app
- Upload reference images to get public URLs via Kie.ai's file upload
- Apply proven **liquid glass prompting patterns** that produce Apple-keynote-quality output

## Setup

### Credentials (already present)

This skill uses `KIE_API_KEY` from the repo's `.env.saas`. No new key needed.

```bash
# Load the env if running curl from the shell:
set -a; source .env.saas; set +a
```

If `KIE_API_KEY` is missing, stop and tell the user before proceeding.

---

## Kie.ai API shape (reference)

All Seedance calls follow Kie.ai's standard task pattern:

- **Base URL**: `https://api.kie.ai/api/v1`
- **Auth header**: `Authorization: Bearer $KIE_API_KEY`
- **Submit**: `POST /jobs/createTask` with body `{"model": "<model-id>", "input": {...}}`
- **Poll**: `GET /jobs/recordInfo?taskId=<id>` every 5 seconds
- **Success**: `data.state == "success"`, video URL at `data.resultJson.resultUrls[0]`
- **Fail**: `data.state == "fail"`, reason at `data.failMsg`

### Model IDs to try (in this order)

Kie.ai's exact model-id string for Seedance 2.0 is not confirmed in this repo (production Seedance here runs via WaveSpeed). Probe in order and use the first one that Kie accepts:

1. `seedance-2.0`
2. `bytedance/seedance-2.0`
3. `seedance-2.0-fast` (cheaper, for tests)
4. `bytedance/seedance-v2`

If all four return "unknown model," **STOP**. Do not silently fall back to a different provider. Tell the user "Kie.ai does not appear to host Seedance 2.0 — we can either (a) switch this skill to WaveSpeed (which this repo already uses for Seedance) or (b) use Kie's own closest video model." Ask which path they want before continuing.

---

## Input parameters (Kie.ai `input` body)

Exact field names may vary slightly by Kie.ai's Seedance endpoint. Start with these; adjust to whatever Kie's rejection message asks for.

| Param | Required | Options | Default |
|-------|----------|---------|---------|
| `prompt` | Yes | string | — |
| `image_urls` | Reference-to-video | array of public URLs, up to 9 | — |
| `image_url` | Image-to-video | single public URL | — |
| `end_image_url` | Optional (i2v) | single public URL for final frame | — |
| `resolution` | No | `"480p"`, `"720p"` | `"720p"` |
| `duration` | No | `"auto"` or seconds `"4"`–`"15"` | `"auto"` |
| `aspect_ratio` | No | `"auto"`, `"21:9"`, `"16:9"`, `"4:3"`, `"1:1"`, `"3:4"`, `"9:16"` | `"auto"` |
| `generate_audio` | No | boolean | `false` (default here — content policy friendlier for abstract visuals) |
| `seed` | No | integer | random |

- Reference images: `@Image1`, `@Image2`, ... `@Image9`
- Total files across modalities: ≤12
- Max resolution: **720p** — no 1080p

### Cost reference

Kie.ai Seedance 2.0 is expected to be similar to WaveSpeed/Fal pricing. Confirm by checking Kie's dashboard before batching. Rough ranges:

| Duration (720p) | Expected cost |
|-----------------|---------------|
| 4s | ~$1.00–$1.50 |
| 10s | ~$2.50–$3.50 |
| 15s | ~$4.00–$5.00 |

**Always show the user an estimated cost before generating.** If the user says "make a promo," reply with the estimated cost first and wait for confirmation.

---

## Sweet spot (proven ratios)

| Refs | Duration | Use case |
|------|----------|----------|
| 1 ref | 4s | Quick single-screenshot test |
| 3 refs | 4–6s | Fast promo test |
| **5 refs** | **10s** | **Production promo (best results)** |
| 3 refs | 4s 480p | Cheapest possible test |

**Golden rule: 1 reference image per 2 seconds of video.**

- Fewer refs → model focuses better on each
- More refs (6–7+) → blends too loosely, loses clarity
- Always describe each image's role in the prompt

---

## Prompting guide

### Rule 1: Logo references first (CRITICAL)

**NEVER describe logos or brand elements in the prompt text.** Seedance mangles text rendering.

Before writing any prompt:
1. Ask for or find the app/brand logo image
2. Save it locally
3. Upload it via Kie's file endpoint
4. Pass it as one of the `@Image` references

If there is no logo available: **STOP and ask.** Don't proceed without it.

Recommended: generate the motion graphics with **no text/logos in the video at all**, then overlay logo in post (Premiere/After Effects).

### Rule 2: Liquid-glass prompt template

```
Design a motion-graphics style ad using glossy liquid glass design
language. Pure black background. @Image1 is [describe what it shows].
@Image2 is [describe]. @Image3 is [describe]. The [element] from
Image 1 becomes translucent glass [describe transformation].
[Element] from Image 2 [describe]. [Continue for each image].
Multiple camera angles: close-up on glass reflections, pull back
to reveal the full scene. No text, no logos, no words. Style: liquid
glass morphism, Apple Vision Pro aesthetic, premium 3D depth,
self-luminous forms on absolute black, [accent color] accent lighting.
```

Key rules:
- Describe each `@Image` by number and what it contains
- Describe how each element transforms into glass
- End with a style line including the brand's accent color
- `"Multiple camera angles"` keeps it dynamic
- `"No text, no logos, no words"` prevents garbled text
- Keep under ~200 words — the model ignores long prompts

### Rule 3: Device framing

**Floating desktop screens (best results):**
```
Show the desktop screens floating in 3D space on a pure black
background, tilted at slight angles like a MacBook product shot.
The UI elements on screen become translucent glass with reflections
and refractions.
```

**iPad:**
```
An iPad Pro floating in empty black space, tilted at a cinematic
angle like an Apple product shot. The iPad has visible black bezels
and a physical frame — only the screen content has the glass effect.
```

**MacBook:**
```
A MacBook Pro floating in empty black space, open at a cinematic
angle. The MacBook screen displays the dashboard. Light catches
the aluminium edges.
```

Floating in black void produces better results than placing devices in environments.

### Rule 4: Audio

- `generate_audio: true` adds ambient SFX and music
- May trigger content-policy violations on abstract visuals — retry with `generate_audio: false` if it fails
- Default to **audio off** for first passes

### Rule 5: Negative guidance

- `"No text, no logos, no words"` — prevents garbled text
- `"No cuts"` — one continuous shot
- `"No camera shake"` — keeps it stable
- `"Pure visual motion only"` — reinforces no text

---

## The full pipeline

### Step 1: Get screenshots

**Option A — Screenshot a website (Playwright):**

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("https://example.com", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(2000)
    page.screenshot(path="screenshot.png")
    browser.close()
```

**Option B — Scrape App Store screenshots:**

```python
import json, urllib.request

search_url = "https://itunes.apple.com/search?term=APP_NAME&entity=software&limit=3"
data = json.loads(urllib.request.urlopen(search_url).read())
app_url = data["results"][0]["trackViewUrl"]
# Then fetch app_url with Playwright and pull <source srcset> entries with "mzstatic.com".
# Swap /460x996bb.webp → /1290x2796bb.jpg for full-res.
```

**Option C — Manual** — drop local PNGs/JPGs in a folder.

### Step 2: Upload for a public URL (Kie.ai)

Seedance needs publicly reachable URLs. Kie.ai offers a file-upload endpoint reusing your `KIE_API_KEY`:

```bash
curl -s -X POST "https://kieai.redpandaai.co/api/file-stream-upload" \
  -H "Authorization: Bearer $KIE_API_KEY" \
  -F "file=@/path/to/screenshot.png" \
  -F "uploadPath=generations" \
  -F "fileName=my-screenshot.png"
```

Response contains `downloadUrl`. Files **expire after 3 days** — re-upload if you come back later.

If Kie's upload endpoint rejects or is unavailable, a no-account fallback:

```bash
# Litterbox — 1-hour expiry, no auth
curl -s -F "reqtype=fileupload" -F "time=1h" \
  -F "fileToUpload=@/path/to/screenshot.png" \
  https://litterbox.catbox.moe/resources/internals/api.php
```

Returns a direct URL. Use only for immediate generation since it expires fast.

### Step 3: Submit the Seedance job (Kie.ai)

Always use a temp JSON file to avoid shell escaping issues:

```bash
cat > /tmp/seedance_body.json << 'ENDJSON'
{
  "model": "seedance-2.0",
  "input": {
    "prompt": "Design a motion-graphics style ad using glossy liquid glass design language. Pure black background. @Image1 is [describe]. @Image2 is [describe]. @Image3 is [describe]. The elements become translucent glass with reflections and refractions. Multiple camera angles. No text, no logos, no words. Style: liquid glass morphism, Apple Vision Pro aesthetic, premium 3D depth, self-luminous forms on absolute black.",
    "image_urls": [
      "https://your-upload-url/screenshot1.png",
      "https://your-upload-url/screenshot2.png",
      "https://your-upload-url/screenshot3.png"
    ],
    "resolution": "720p",
    "duration": "4",
    "aspect_ratio": "16:9",
    "generate_audio": false
  }
}
ENDJSON

SUBMIT=$(curl -s -X POST "https://api.kie.ai/api/v1/jobs/createTask" \
  -H "Authorization: Bearer $KIE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/seedance_body.json)

echo "$SUBMIT"
TASK_ID=$(echo "$SUBMIT" | python -c "import sys,json; print(json.load(sys.stdin)['data']['taskId'])")
echo "Task: $TASK_ID"
```

If submit returns an error about `model`, try the next id from the "Model IDs to try" list above. If all four fail, STOP and ask the user how to proceed (see the stop rule above).

### Step 4: Poll for result

```bash
while true; do
  POLL=$(curl -s "https://api.kie.ai/api/v1/jobs/recordInfo?taskId=$TASK_ID" \
    -H "Authorization: Bearer $KIE_API_KEY")
  STATE=$(echo "$POLL" | python -c "import sys,json; print(json.load(sys.stdin)['data'].get('state','processing'))")
  echo "[$(date +%H:%M:%S)] state=$STATE"
  if [ "$STATE" = "success" ]; then
    VIDEO_URL=$(echo "$POLL" | python -c "import sys,json; d=json.load(sys.stdin)['data']; r=d.get('resultJson'); import json as _j; r = _j.loads(r) if isinstance(r,str) else (r or {}); print(r.get('resultUrls',[None])[0] or '')")
    echo "URL: $VIDEO_URL"
    break
  elif [ "$STATE" = "fail" ]; then
    echo "FAIL: $POLL"
    exit 1
  fi
  sleep 5
done
```

### Step 5: Download the video

Kie.ai result URLs may expire — download immediately:

```bash
curl -sL -o "output_video.mp4" "$VIDEO_URL"
```

### Step 6: Post-production (recommended)

Overlay the logo and any text in your editor. The motion graphics are the visual base — branding goes on top in post.

---

## Text-to-video (no references)

For projects with no screenshots (GitHub repos, docs, abstract concepts), drop `image_urls` and use a timestamped prompt:

```
Ultra-sleek motion design sequence. Pure black background throughout.
Glossy liquid glass design language.

0-1s [FORM]: A translucent glass [object] materializes at center,
light refracting through it.

1-2s [CONNECT]: Glass connections form between elements, each a thin
glass tube filling with luminous light.

2-3s [REVEAL]: The structure rotates revealing depth and glass
reflections.

3-4s [GLOW]: A pulse of warm light passes through the entire glass
structure.

Style: liquid glass morphism, premium 3D depth, self-luminous forms
on absolute black.
```

Submit same way — just omit `image_urls` from the input.

---

## Image-to-video (single image)

Animate one still image into motion. Supports optional `end_image_url` for A→B transitions (light→dark mode, empty→populated dashboard, before→after).

```bash
cat > /tmp/seedance_i2v.json << 'ENDJSON'
{
  "model": "seedance-2.0",
  "input": {
    "prompt": "The dashboard interface comes alive — UI elements gently float and shift, glass reflections ripple across panels, accent lighting pulses through the layout. Smooth cinematic camera drift. No text, no logos.",
    "image_url": "https://your-upload-url/screenshot.png",
    "resolution": "720p",
    "duration": "4",
    "aspect_ratio": "16:9",
    "generate_audio": false
  }
}
ENDJSON

curl -s -X POST "https://api.kie.ai/api/v1/jobs/createTask" \
  -H "Authorization: Bearer $KIE_API_KEY" \
  -H "Content-Type: application/json" \
  -d @/tmp/seedance_i2v.json
```

### When to pick which mode

| Scenario | Mode |
|----------|------|
| Animate a single screenshot/photo | image-to-video |
| Transition between two states (light/dark, before/after) | image-to-video with `end_image_url` |
| Lip-sync a character/avatar | image-to-video with `generate_audio: true` |
| Blend 3–5 screenshots into a promo reel | reference-to-video |
| Glass morphism from multiple UI views | reference-to-video |

### Image-to-video prompting tips

- Describe the **motion**, not the image — the model sees the image already
- `"Cinematic camera drift"` works well for subtle product shots
- `"Elements gently float and shift"` for UI animation
- Same negative guidance: `"No text, no logos, no words"`

---

## Prompt patterns library

### Floating desktop screens (best for SaaS/apps)

```
Design a motion-graphics style ad based on these images, using
multiple camera angles — close-ups that highlight the glass
reflections, various tap and click interaction animations, and a
focus on this glossy glass UI design language. @Image1 is [describe].
@Image2 is [describe]. @Image3 is [describe]. Show the desktop
screens floating in 3D space on a pure black background, tilted at
slight angles like a MacBook product shot. The UI elements on screen
become translucent glass with reflections and refractions. No text,
no logos, no words. Style: liquid glass morphism, Apple product ad,
premium desktop app showcase, self-luminous forms on absolute black,
[color] accent lighting.
```

### iPad product reveal

Key detail: explicitly call out "real solid device" so the iPad frame stays solid while only the screen gets the glass effect.

```
Design a motion-graphics style ad using glossy liquid glass design
language. Pure black background, nothing else. A realistic iPad Pro
with visible black bezels and physical frame floating in empty black
space, tilted at a cinematic angle like an Apple product shot. The
iPad is a real solid device with clear borders and edges, not made
of glass. Only the screen content has the glass effect. The iPad
screen displays @Image1 and @Image2. The UI elements on the screen
are translucent glass with reflections and refractions. Light catches
the physical edges of the iPad frame. The device slowly rotates.
No text, no logos, no words. Style: Apple keynote product reveal,
real device with glass UI on screen, premium 3D depth, floating in
absolute black void, [color] accent lighting.
```

### Abstract glass network

No device frame — pure abstract glass.

```
Design a motion-graphics style ad using glossy liquid glass design
language. Pure black background. @Image1 is [describe]. @Image2 is
[describe]. @Image3 is [describe]. Each element becomes translucent
glass catching and refracting light. Multiple camera angles:
close-up on glass reflections, pull back to reveal the full scene.
Style: liquid glass morphism, Apple Vision Pro aesthetic, premium
3D depth, self-luminous forms on absolute black, [color] accent
lighting.
```

### Abstract motion identity

```
Ultra-sleek motion design sequence. Pure black background throughout.
White-on-black minimal aesthetic. No cuts — one single continuous
unbroken visual evolution. Locked-off static center frame, no camera
movement. All motion occurs within the subject. Self-luminous white
forms on absolute black, no grain, no shadows.

0-2s [ORIGIN]: [Starting visual]
2-4s [TRANSFORM]: [Transformation]
4-6s [REVEAL]: [Reveal]
6-8s [CLOSE]: [Closing visual]

Style: [brand] motion identity, mathematical precision.
Mood: calm, inevitable, intelligent, premium.
```

---

## Batch generation workflow

### Step 1: Assess each project
- Do screenshots exist? Website or App Store → reference-to-video. GitHub/docs only → text-to-video.
- What's the visual anchor? Dark UI = strong liquid-glass match. Colorful icons = glass tiles. Geometric layout = glass honeycomb.
- What aspect ratio? Phone app → 9:16. Desktop/SaaS → 16:9.

### Step 2: Test batch (cheap)
Run everything at the cheapest tier available (try `seedance-2.0-fast` if Kie hosts it; otherwise `seedance-2.0` at 480p/4s).

### Step 3: Review & promote winners
Re-generate the working ones at 720p / 8–10s.

### Step 4: Post-production
Overlay logos and text in your editor.

---

## Cost estimation checklist (show to user before generating)

Before every generation, tell the user:

1. Tier (Fast vs Pro if both are on Kie)
2. Resolution (480p vs 720p)
3. Duration (4–15s)
4. Reference count
5. Audio on/off
6. **Estimated cost** (from the table above)

Wait for user confirmation ("yes", "go", "generate") before submitting. Do not auto-proceed.

---

## Gotchas

1. **Text rendering is bad** — never ask Seedance to render text. Overlay in post.
2. **Audio content policy** — abstract visuals may trigger false positives. Default `generate_audio: false`, turn on only when needed.
3. **People's faces in screenshots** — may trigger "likenesses of real people" policy. Crop faces out.
4. **Shell escaping breaks JSON** — always use temp JSON files with `cat > /tmp/file.json`, never inline JSON in curl.
5. **Kie upload URLs expire after 3 days** — re-upload if coming back later.
6. **Max resolution: 720p** — upscale in post if you need higher.
7. **7+ reference images** — quality degrades. Stick to ≤5.
8. **Unknown model** — if Kie rejects all four probe ids, STOP and surface the issue to the user instead of silently switching providers.

---

## Isolation reminder

This skill is fully isolated from the ugc-engine product pipeline:

- Do NOT import from `services/`, `ugc_backend/`, `ugc_worker/`, or `kie_ai/`.
- Do NOT modify `services/creative-os/prompts/seedance_director.txt` — that serves a different purpose (product-accurate UGC/cinematic with `@Image1` label binding), and its rules intentionally conflict with this skill's "never describe logos" rule.
- Do NOT route product user traffic through this skill.
- Only fire when the user explicitly asks for an app-promo / motion-graphics promo clip.

---

## Credits

Upstream skill by [RoboNuggets](https://robonuggets.com) (originally targets Fal AI). This fork swaps the provider to Kie.ai so it reuses `KIE_API_KEY`. Seedance 2.0 is by ByteDance.
