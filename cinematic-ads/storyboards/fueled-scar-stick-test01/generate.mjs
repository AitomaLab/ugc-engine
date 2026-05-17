// generate.mjs — Step 3: GPT Image 2 storyboard sheet for FUELED. Scar Stick
// Direction A — Soft Morning Ritual (model-led, hands + skin focus, blur-face)
//
// Run:  node generate.mjs
// Reads FAL_KEY from /Users/MD/ugc-engine/.env
// Output: out/gpt2_fueled_scar_stick_{timestamp}.png

import fs from 'node:fs';
import path from 'node:path';

// --- env -------------------------------------------------------------------
const ENV_PATH = '/Users/MD/ugc-engine/.env';
const envText = fs.existsSync(ENV_PATH) ? fs.readFileSync(ENV_PATH, 'utf8') : '';
const FAL_KEY = (envText.match(/^FAL_KEY=(.+)$/m) || [])[1]?.trim() || process.env.FAL_KEY;
if (!FAL_KEY) { console.error('FAL_KEY missing'); process.exit(1); }

// --- product ---------------------------------------------------------------
const BRAND = 'FUELED.';
const PRODUCT = 'Scar Solutions Silicone Scar Stick';
const SLUG = 'fueled_scar_stick';
const TAGLINE = 'Made for the after.';
const DOMAIN = 'tryfueled.com';
const LOCAL_REF = '/Users/MD/ugc-engine/References/inputs/fuled.png';

// --- upload local ref to Fal storage --------------------------------------
async function uploadToFal(filePath) {
    const buf = fs.readFileSync(filePath);
    const fileName = path.basename(filePath);
    const init = await fetch('https://rest.alpha.fal.ai/storage/upload/initiate', {
        method: 'POST',
        headers: { Authorization: `Key ${FAL_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_type: 'image/png', file_name: fileName }),
    });
    if (!init.ok) throw new Error(`upload/initiate failed: ${init.status} ${await init.text()}`);
    const { upload_url, file_url } = await init.json();
    const put = await fetch(upload_url, {
        method: 'PUT',
        headers: { 'Content-Type': 'image/png' },
        body: buf,
    });
    if (!put.ok) throw new Error(`upload PUT failed: ${put.status} ${await put.text()}`);
    return file_url;
}

console.log(`[${SLUG}] Uploading product ref to Fal storage...`);
const refUrl = await uploadToFal(LOCAL_REF);
console.log(`[${SLUG}] Ref URL: ${refUrl}`);

// --- storyboard prompt -----------------------------------------------------
const PROMPT = `A single image: a 6-panel cinematic ad storyboard sheet, 3 columns by 2 rows, on an off-white paper background with a thin black border. Each panel is a cinematic film still in 16:9 landscape orientation. Above the grid, a bold mono header reads:

STORYBOARD: SOFT MORNING RITUAL — 15s SPOT — BRAND: ${BRAND}     PRODUCT: ${PRODUCT}

Each panel has a small "01"–"06" number top-left AND a clean monospace timestamp badge top-right (e.g. [0:00–0:02.5]). Beneath each panel sits a 3-line monospace caption block:
  SCENE: <label>
  ACTION: <one short camera/motion sentence>
  SOUND: <music or SFX cue>

CRITICAL — PRODUCT FIDELITY: match the silhouette, materials, and soft peach/blush colorway from @Image1 EXACTLY. The product is a twist-up stick balm with a matte blush body and matching blush cap, dark grey wordmark "FUELED." on the body. The outer box is matching blush, dark grey wordmark. Keep small ingredient text on the box as illegible texture, not readable type. The stick is pristine, never crushed, never dented, never opened-and-spilled.

CRITICAL — CHARACTER LOCK (for panels with a person): a woman in her late twenties, soft natural beauty, light freckles, lived-in warmth. Render the FACE as SOFT WARM-TONED BLUR — like a Sofia Coppola film. Hair edges and jawline crisp, only the central face surface is blurred. NO discernible facial features. This face will be filled in naturally by the animator downstream — do not draw eyes / nose / mouth.

AESTHETIC: warm morning domestic light through linen curtains, soft blush + cream + sand palette, 50mm lens, shallow depth of field, slight grain, Sofia Coppola-soft (not clinical). Lived-in bathroom corner, ceramic, terrycotton, a small folded linen square. Quiet, intimate, gentle. Never sterile, never medical.

PANELS (timestamped for a 15-second spot @ 2.5s per beat):
01 [0:00–0:02.5] SCENE: STILLNESS | ACTION: slow push-in on the FUELED stick standing on a cream ceramic dish next to a folded linen square, morning light catching the blush body, no hands, no face | SOUND: soft morning ambience, gentle piano note
02 [0:02.5–0:05.0] SCENE: PICK UP | ACTION: a woman's hand (soft warm-toned blur face just visible at top edge of frame, no features) lifts the stick from the dish, twists the cap off, slow 50mm close-up | SOUND: soft cap-click, warm pad swell
03 [0:05.0–0:07.5] SCENE: GLIDE | ACTION: extreme close-up of the balm gliding smoothly across soft skin (forearm or shoulder, NOT explicit scar, NOT clinical), single fluid horizontal motion, blush balm leaves a soft satin sheen | SOUND: silk-on-skin whisper, music continues
04 [0:07.5–0:10.0] SCENE: SETTLE | ACTION: macro-close on the balm-treated skin catching warm light, soft natural texture, balm absorbing, completely calm and still | SOUND: held warm chord, ambient breath of room tone
05 [0:10.0–0:12.5] SCENE: REPLACE | ACTION: she caps the stick (face still soft warm-toned blur, hair and jawline crisp), places it back on the ceramic dish, hand exits frame, sun slowly brightens | SOUND: soft cap-click, music gentle rise
06 [0:12.5–0:15.0] SCENE: END CARD | ACTION: clean hero shot of the FUELED stick standing next to the matching blush box on cream linen, warm morning light, centered composition | SOUND: final warm chord, soft music tail

End-card text (panel 06 only): "${BRAND} ${PRODUCT}. ${TAGLINE}. ${DOMAIN}"

Render the full storyboard as ONE single image, 3×2 grid landscape. Captions legible in monospace. No watermarks. No extra text beyond what is specified. Same product silhouette and same character (soft warm blur face) every panel.`;

// --- run -------------------------------------------------------------------
const OUT = path.resolve('./out');
fs.mkdirSync(OUT, { recursive: true });

const body = {
    prompt: PROMPT,
    image_urls: [refUrl],
    image_size: { width: 2560, height: 1792 },
    quality: 'high',
    num_images: 1,
    output_format: 'png',
};

console.log(`[${SLUG}] Submitting to GPT Image 2 (high quality, 2560x1792)...`);
const t0 = Date.now();
const res = await fetch('https://fal.run/openai/gpt-image-2/edit', {
    method: 'POST',
    headers: { Authorization: `Key ${FAL_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
});
const json = await res.json();
console.log(`[${SLUG}] Returned in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
if (!json.images?.length) {
    console.error('NO IMAGES:', JSON.stringify(json));
    process.exit(1);
}

const ts = Date.now();
const fname = `gpt2_${SLUG}_${ts}.png`;
const buf = Buffer.from(await (await fetch(json.images[0].url)).arrayBuffer());
fs.writeFileSync(path.join(OUT, fname), buf);
console.log(`[${SLUG}] Saved: ${path.join(OUT, fname)}`);
console.log(`[${SLUG}] Cost: ~$0.18`);
