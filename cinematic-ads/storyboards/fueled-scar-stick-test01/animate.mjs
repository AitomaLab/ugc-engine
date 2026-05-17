// animate.mjs — Step 4: Seedance 2.0 Pro animation for FUELED. Scar Stick
// Pass the storyboard (@Image1) + the original product photo (@Image2)
//
// Run:  node animate.mjs              # defaults to 720p
//       RESOLUTION=480p node animate.mjs   # cheap test
// Reads FAL_KEY from /Users/MD/ugc-engine/.env
// Output: out/seedance2p_fueled_scar_stick_{dur}s_{res}_{timestamp}.mp4

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

const STORYBOARD = '/Users/MD/ugc-engine/cinematic-ads/storyboards/fueled-scar-stick-test01/out/gpt2_fueled_scar_stick_1778959524831.png';
const PRODUCT_REF_LOCAL = '/Users/MD/ugc-engine/References/inputs/fuled.png';

const RESOLUTION = process.env.RESOLUTION || '720p';   // '720p' final, '480p' test
const DURATION = '15';

// Simple 1-3 sentence prompt — A/B winner per skill. Names BOTH refs explicitly.
// No "blur" / "face" combo (avoids word-bleed trap). No clinical language.
const PROMPT = `Turn this storyboard (@Image1) into a cinematic 15-second beauty ad. Match the FUELED. silicone scar stick with its soft peach/blush twist-up body, matching blush cap, and dark grey "FUELED." wordmark exactly using @Image2 as the clean product reference — the stick is pristine in every beat. Warm morning domestic light, soft blush + cream palette, intimate Sofia Coppola-soft aesthetic, shallow depth of field. Music + ambient sound design only, no dialogue.`;

// --- upload helper ---------------------------------------------------------
async function uploadToFal(filePath, contentType) {
    const buf = fs.readFileSync(filePath);
    const init = await fetch('https://rest.alpha.fal.ai/storage/upload/initiate', {
        method: 'POST',
        headers: { Authorization: `Key ${FAL_KEY}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ content_type: contentType, file_name: path.basename(filePath) }),
    });
    if (!init.ok) throw new Error(`upload/initiate failed: ${init.status} ${await init.text()}`);
    const { upload_url, file_url } = await init.json();
    if (!upload_url) throw new Error('Fal storage init missing upload_url');
    const put = await fetch(upload_url, { method: 'PUT', headers: { 'Content-Type': contentType }, body: buf });
    if (!put.ok) throw new Error(`upload PUT failed: ${put.status} ${await put.text()}`);
    return file_url;
}

console.log(`[${SLUG}] Uploading storyboard to Fal storage...`);
const storyboardUrl = await uploadToFal(STORYBOARD, 'image/png');
console.log(`[${SLUG}] Storyboard: ${storyboardUrl}`);

console.log(`[${SLUG}] Uploading product ref to Fal storage...`);
const productUrl = await uploadToFal(PRODUCT_REF_LOCAL, 'image/png');
console.log(`[${SLUG}] Product:    ${productUrl}`);

// --- run -------------------------------------------------------------------
const OUT = path.resolve('./out');
fs.mkdirSync(OUT, { recursive: true });

const body = {
    prompt: PROMPT,
    image_urls: [storyboardUrl, productUrl],
    resolution: RESOLUTION,
    duration: DURATION,
    aspect_ratio: '16:9',
    generate_audio: true,
};

const cost = RESOLUTION === '720p'
    ? (parseInt(DURATION) * 0.30).toFixed(2)
    : (parseInt(DURATION) * 0.18).toFixed(2);
console.log(`[${SLUG}] Submitting to Seedance 2.0 Pro (${DURATION}s, ${RESOLUTION}, ~$${cost})...`);

// Queue-based — survives long renders (sync endpoint headers-timeouts at ~5min on Node)
const t0 = Date.now();
const submit = await fetch('https://queue.fal.run/fal-ai/bytedance/seedance-2.0/reference-to-video', {
    method: 'POST',
    headers: { Authorization: `Key ${FAL_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
});
const submitJson = await submit.json();
const requestId = submitJson.request_id;
const statusUrl = submitJson.status_url;
const responseUrl = submitJson.response_url;
if (!requestId) { console.error('SUBMIT FAILED:', JSON.stringify(submitJson, null, 2)); process.exit(1); }
console.log(`[${SLUG}] Queued: request_id=${requestId}`);

let json = null;
for (let i = 0; i < 240; i++) {  // up to 20 min @ 5s polls
    await new Promise(r => setTimeout(r, 5000));
    const st = await fetch(statusUrl, { headers: { Authorization: `Key ${FAL_KEY}` } });
    const stj = await st.json();
    const status = stj.status;
    if (i % 6 === 0) console.log(`[${SLUG}] [${((Date.now() - t0) / 1000).toFixed(0)}s] status=${status}`);
    if (status === 'COMPLETED') {
        const final = await fetch(responseUrl, { headers: { Authorization: `Key ${FAL_KEY}` } });
        json = await final.json();
        break;
    }
    if (status === 'FAILED' || status === 'ERROR') {
        console.error(`[${SLUG}] FAILED:`, JSON.stringify(stj, null, 2));
        process.exit(1);
    }
}
console.log(`[${SLUG}] Returned in ${((Date.now() - t0) / 1000).toFixed(1)}s`);

if (!json?.video?.url) {
    console.error('NO VIDEO. Full response:');
    console.error(JSON.stringify(json, null, 2));
    process.exit(1);
}

const ts = Date.now();
const fname = `seedance2p_${SLUG}_${DURATION}s_${RESOLUTION}_${ts}.mp4`;
const buf = Buffer.from(await (await fetch(json.video.url)).arrayBuffer());
fs.writeFileSync(path.join(OUT, fname), buf);
console.log(`[${SLUG}] Saved: ${path.join(OUT, fname)}`);
console.log(`[${SLUG}] Seed:  ${json.seed ?? '(none)'}`);
console.log(`[${SLUG}] Cost:  ~$${cost}`);
