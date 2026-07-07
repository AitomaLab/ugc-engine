"""Brand Studio — scrape, ideas (OpenRouter), render (Fal GPT Image 2)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

import httpx
from html import unescape
from pathlib import Path
from typing import Any

FAL_ENDPOINT = "https://fal.run/openai/gpt-image-2"
FAL_EDIT_ENDPOINT = "https://fal.run/openai/gpt-image-2/edit"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_SERVICE_DIR = Path(__file__).resolve().parent.parent
_STATE_ROOT = _SERVICE_DIR / "data" / "brands"

ADJ = [
    "bold", "playful", "fun", "minimal", "clean", "modern", "luxury", "premium",
    "elegant", "warm", "friendly", "cheeky", "irreverent", "calm", "energetic",
    "retro", "vintage", "sophisticated", "quirky", "punchy", "bright", "soft",
    "natural", "organic", "youthful", "wholesome", "fresh", "real",
]
JUNK_HEX = {"#007bff", "#0d6efd", "#0a58ca", "#6610f2", "#0dcaf0"}


def _fal_key() -> str | None:
    return (os.getenv("FAL_KEY") or "").strip() or None


def _openrouter_key() -> str | None:
    return (os.getenv("OPENROUTER_API_KEY") or "").strip() or None


def _ideas_model() -> str:
    return os.getenv("OPENROUTER_IDEAS_MODEL") or "anthropic/claude-sonnet-4.6"


def _openrouter_model() -> str:
    return os.getenv("OPENROUTER_MODEL") or "z-ai/glm-5.2"


def _user_dir(user_id: str) -> Path:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_id) or "anon"
    return _STATE_ROOT / safe


def _state_file(user_id: str) -> Path:
    return _user_dir(user_id) / "brand-state.json"


def _session_file(user_id: str) -> Path:
    return _user_dir(user_id) / "studio-session.json"


def read_brand_state(user_id: str) -> dict | None:
    path = _state_file(user_id)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return None


def write_brand_state(user_id: str, brand: dict) -> None:
    path = _state_file(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(brand, f, indent=2)


def read_studio_session(user_id: str) -> dict | None:
    path = _session_file(user_id)
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except OSError:
        return None


def write_studio_session(user_id: str, session: dict) -> None:
    path = _session_file(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session, f, indent=2)


def _upload_render_bytes(data: bytes, storage_path: str) -> str:
    from supabase import create_client

    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not supabase_url or not service_key:
        raise RuntimeError("missing SUPABASE_URL or service key")
    bucket = "user-uploads"
    sb = create_client(supabase_url, service_key)
    sb.storage.from_(bucket).upload(
        storage_path,
        data,
        file_options={"content-type": "image/png", "upsert": "true"},
    )
    return sb.storage.from_(bucket).get_public_url(storage_path)


def _img_url(it: Any) -> str:
    if isinstance(it, str):
        return it
    if isinstance(it, dict):
        return it.get("url") or it.get("src") or ""
    return ""


def _vision_url(u: str) -> str:
    if not u:
        return ""
    base = u.split("?", 1)[0].split("#", 1)[0].lower()
    if base.endswith(".svg") or u.startswith("data:image/svg"):
        return ""
    if u.startswith("https://") or u.startswith("data:"):
        return u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("//"):
        return "https:" + u
    return ""


def openrouter_chat(
    messages: list,
    *,
    max_tokens: int = 2200,
    temperature: float = 0.85,
    timeout: int = 180,
    model: str | None = None,
    provider: dict | None = None,
) -> str:
    key = _openrouter_key()
    if not key:
        raise RuntimeError("no OPENROUTER_API_KEY configured")
    body: dict[str, Any] = {
        "model": model or _openrouter_model(),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
    }
    if provider:
        body["provider"] = provider
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://studio.aitoma.ai",
            "X-Title": "Aitoma Brand Studio",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        out = json.loads(resp.read())
    return out["choices"][0]["message"]["content"]


def ideas_prompt(brand: dict, direction: str, n: int, nprod: int = 0, lang: str = "en") -> str:
    name = brand.get("name", "the brand")
    colors = ", ".join((brand.get("colors") or [])[:5])
    voice = brand.get("voice", "")
    vt = ", ".join(brand.get("voiceTags") or [])
    if direction.strip():
        dline = (
            f'Creative direction for this whole batch: "{direction.strip()}". '
            "EVERY idea must clearly fit this direction."
        )
    else:
        dline = "No specific direction was given - propose a varied, on-brand mix."
    if nprod:
        photo_note = (
            "\nIMPORTANT - you are shown real PRODUCT photo(s) below, each labelled PRODUCT[k] "
            "where k is its index number, plus some IMAGERY mood photo(s). Look at them. "
            "For EACH slide, set \"productRef\" to the index number k of the single product photo "
            "that best fits that slide. Use null only when no product photo fits.\n"
        )
        ref_field = '    "productRef": <the index number k of the best-matching PRODUCT photo, or null>\n'
    else:
        photo_note = ""
        ref_field = '    "productRef": null\n'
    prompt = (
        f"Brand: {name}\nPalette: {colors}\nVoice: {voice}\nVoice tags: {vt}\n{dline}\n{photo_note}\n"
        f"Write {n} distinct Instagram carousel post ideas for this brand. "
        "Vary slide counts from 1 to 4.\n\n"
        f"Return ONLY a JSON array of {n} objects, no markdown. Each object:\n"
        "{\n"
        '  "tone": "3-5 word label",\n'
        '  "title": "short internal title",\n'
        f'  "idea": "ONE short sentence (max 30 words) for {name}",\n'
        '  "caption": "Instagram caption with hook, value, CTA, 2 hashtags",\n'
        '  "slides": [ { "role": "HOOK|LINEUP|PROOF|WHY|SHOP", '
        '"headline": "ALL-CAPS max 6 words", "badge": "short sticker",\n'
        f"{ref_field}"
        "  } ]\n"
        "}\n"
        "JSON only."
    )
    if lang.lower().startswith("es"):
        prompt += (
            "\n\nWrite ALL user-facing text (tone, title, idea, caption, headlines, badges) "
            "in Spanish (español). Keep JSON keys in English."
        )
    return prompt


def parse_ideas(raw: str) -> list | None:
    txt = raw.strip()
    txt = re.sub(r"^```(?:json)?\s*", "", txt)
    txt = re.sub(r"\s*```$", "", txt).strip()
    try:
        data = json.loads(txt)
    except Exception:
        m = re.search(r"\[.*\]", txt, re.S)
        if not m:
            return None
        try:
            data = json.loads(m.group(0))
        except Exception:
            return None
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("ideas")
    return None


def _fetch(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _chrome_exe() -> str | None:
    for p in (
        r"C:/Program Files/Google/Chrome/Application/chrome.exe",
        r"C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    ):
        if os.path.isfile(p):
            return p
    return None


def _fetch_browser(url: str, timeout: int = 60) -> str:
    exe = _chrome_exe()
    if not exe:
        raise RuntimeError("no chrome for browser-fetch fallback")
    out = subprocess.run(
        [exe, "--headless=new", "--disable-gpu", "--virtual-time-budget=6000", "--dump-dom", url],
        capture_output=True,
        timeout=timeout,
    )
    html = out.stdout.decode("utf-8", "ignore")
    if len(html) < 500:
        raise RuntimeError("browser-fetch returned empty")
    return html


_MIN_HTML_LEN = 500


def _fetch_httpx(url: str, timeout: float = 8.0) -> str:
    t = httpx.Timeout(connect=5.0, read=timeout, write=5.0, pool=5.0)
    with httpx.Client(timeout=t, follow_redirects=True, headers={"User-Agent": UA}) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text
        if len(html) < _MIN_HTML_LEN:
            raise RuntimeError("httpx fetch returned empty")
        return html


def _fetch_any(url: str, timeout: int = 15) -> str:
    """Race httpx + Chrome headless; first valid HTML wins within a wall-clock budget."""
    import time as _time

    deadline = _time.monotonic() + max(5, timeout)
    errors: list[str] = []

    def remaining() -> float:
        return max(0.5, deadline - _time.monotonic())

    pool = ThreadPoolExecutor(max_workers=2)
    try:
        futures = [pool.submit(_fetch_httpx, url, min(8.0, remaining()))]
        if _chrome_exe():
            futures.append(pool.submit(_fetch_browser, url, max(2, min(12, int(remaining())))))

        pending = set(futures)
        while pending and _time.monotonic() < deadline:
            done, pending = wait(pending, timeout=remaining(), return_when=FIRST_COMPLETED)
            for fut in done:
                try:
                    html = fut.result()
                    if html and len(html) >= _MIN_HTML_LEN:
                        return html
                except Exception as exc:
                    errors.append(str(exc))

        hint = errors[0] if errors else "timed out"
        raise RuntimeError(f"could not fetch page: {hint}")
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def _html_products(html: str, name: str) -> list[dict]:
    out, seen = [], set()
    for u in re.findall(r'https?://[^"\'\s)]+?\.(?:png|jpg|jpeg|webp)', html):
        u = u.split("?")[0]
        low = u.lower()
        if u in seen or any(
            k in low for k in ("icon", "logo", "sprite", "favicon", "placeholder", "badge", "flag", "payment")
        ):
            continue
        seen.add(u)
        out.append({"name": name, "url": u})
        if len(out) >= 8:
            break
    return out


def _pretty_font(s: str) -> str:
    s = s.strip().strip('"\'').split(",")[0].strip()
    s = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", s)
    s = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", s)
    return s.strip()


def _meta(html: str, *keys: str) -> str:
    for k in keys:
        m = re.search(
            r'(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']+)' % re.escape(k),
            html,
            re.I,
        )
        if not m:
            m = re.search(
                r'content=["\']([^"\']+)["\'][^>]*(?:property|name)=["\']%s["\']' % re.escape(k),
                html,
                re.I,
            )
        if m:
            return unescape(m.group(1).strip())
    return ""


def _colors(html: str) -> list[str]:
    hexes = re.findall(r"#([0-9a-fA-F]{6})\b", html)

    def vivid(h: str) -> bool:
        r, g, b = int(h[:2], 16), int(h[2:4], 16), int(h[4:], 16)
        if max(r, g, b) - min(r, g, b) < 22:
            return False
        if ("#" + h.lower()) in JUNK_HEX:
            return False
        if all(c in (0, 255) for c in (r, g, b)):
            return False
        return True

    cnt = Counter("#" + h.lower() for h in hexes if vivid(h))
    cols = [c for c, _ in cnt.most_common(6)]
    tc = _meta(html, "theme-color")
    if re.match(r"^#[0-9a-fA-F]{6}$", tc or "") and tc.lower() not in cols:
        cols.insert(0, tc.lower())
    if not any(int(c[1:3], 16) + int(c[3:5], 16) + int(c[5:7], 16) < 180 for c in cols):
        cols.append("#161214")
    return cols[:6] or ["#1c1a16", "#6f6a5c", "#d9d3c6", "#f2efe8", "#ff6b1a"]


def _fonts(html: str) -> str:
    cands: list[str] = []
    m = re.search(r'fontFamily"\s*:\s*\{[^}]*?\[\s*"([^"]+)"', html)
    if m:
        cands.append(m.group(1))
    m = re.search(r'font_family"\s*:\s*"([^"]+)"', html)
    if m:
        cands.append(m.group(1))
    cands += re.findall(r"@font-face[^}]*?font-family:\s*[\"']?([^;\"'}]+)", html, re.I)
    cands += re.findall(r"font-family:\s*([^;\"}\n]+)", html, re.I)
    generic = ("sans-serif", "serif", "monospace", "inherit", "var(", "arial", "helvetica", "system", "apple")
    for c in cands:
        name = c.strip().strip("\"'").split(",")[0].strip()
        if name and not any(g in name.lower() for g in generic) and len(name) > 1:
            return _pretty_font(name)
    return "Inter"


def _images(html: str, origin: str) -> list[str]:
    imagery: list[str] = []
    og = _meta(html, "og:image")
    if og:
        imagery.append(urllib.parse.urljoin(origin, og))
    for u in re.findall(r'https?://[^"\'\s)]+?\.(?:png|jpg|jpeg|webp)', html):
        if any(k in u.lower() for k in ("hero", "condensation", "lifestyle", "banner")) and u not in imagery:
            imagery.append(u)
    return imagery[:4]


def _looks_like_shopify(html: str) -> bool:
    sample = (html or "")[:120_000].lower()
    return any(
        marker in sample
        for marker in (
            "cdn.shopify.com",
            "shopify.theme",
            "shopify-section",
            "myshopify.com",
            '"shopify"',
        )
    )


def _shopify_products(origin: str) -> list[dict]:
    try:
        data = json.loads(_fetch(origin.rstrip("/") + "/products.json?limit=12", timeout=5))
    except Exception:
        return []
    out = []
    for p in data.get("products", [])[:8]:
        imgs = p.get("images") or []
        if imgs and imgs[0].get("src"):
            out.append({"name": (p.get("title") or "").strip()[:40], "url": imgs[0]["src"]})
    return out


def scrape_brand(url: str) -> dict:
    url = url.strip()
    if not re.match(r"^https?://", url):
        url = "https://" + url
    html = _fetch_any(url)
    p = urllib.parse.urlparse(url)
    origin = f"{p.scheme}://{p.netloc}"
    name = _meta(html, "og:site_name").strip()
    if not name:
        t = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        name = unescape(re.split(r"[|\-–]", (t.group(1) if t else ""))[0].strip())
    if not name:
        name = p.netloc.replace("www.", "").split(".")[0].title()
    if name and name.islower():
        name = name.title()
    desc = _meta(html, "og:description", "description")
    if len(desc.strip()) < 25:
        kw = _meta(html, "keywords")
        desc = (desc + " " + kw).strip() if kw else desc
    headlines = [
        unescape(re.sub(r"<[^>]+>", "", h)).strip()
        for h in re.findall(r"<h1[^>]*>(.*?)</h1>", html, re.I | re.S)
    ]
    headlines = [h for h in headlines if 2 < len(h) < 60][:4]
    tags = [a for a in ADJ if re.search(r"\b" + a + r"\b", (desc + " " + html[:4000]).lower())][:5]
    products = _shopify_products(origin) if _looks_like_shopify(html) else []
    if not products:
        products = _html_products(html, name)
    font = _fonts(html)
    imagery = _images(html, origin)
    if len(imagery) < 3 and products:
        for pr in products:
            if pr["url"] not in imagery:
                imagery.append(pr["url"])
            if len(imagery) >= 4:
                break
    return {
        "name": name[:40],
        "url": p.netloc.replace("www.", ""),
        "scrapedReal": True,
        "fonts": {"display": font, "body": font, "note": "pulled from the site"},
        "colors": _colors(html),
        "voice": (desc[:180] if len(desc.strip()) >= 12 else ""),
        "voiceTags": tags,
        "taglines": headlines,
        "imagery": imagery[:4],
        "productImages": products,
    }


def generate_images(prompt: str, image_urls: list[str], n: int = 1) -> dict:
    prompt = (prompt or "").strip()
    n = max(1, min(5, n))
    refs = [v for v in (_vision_url(u) for u in image_urls) if v.startswith("https://")][:3]
    if not prompt:
        raise ValueError("empty prompt")
    fal_key = _fal_key()
    if not fal_key:
        raise RuntimeError("No FAL_KEY found")
    endpoint = FAL_EDIT_ENDPOINT if refs else FAL_ENDPOINT

    def fire(image_size):
        body: dict[str, Any] = {
            "prompt": prompt,
            "image_size": image_size,
            "quality": "high",
            "num_images": n,
            "output_format": "png",
        }
        if refs:
            body["image_urls"] = refs
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(body).encode("utf-8"),
            headers={"Authorization": f"Key {fal_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=240) as resp:
            out = json.loads(resp.read())
        return [img.get("url") for img in out.get("images", []) if img.get("url")]

    first_size = {"width": 1088, "height": 1360} if refs else {"width": 1080, "height": 1350}
    try:
        return {"images": fire(first_size), "mode": "edit" if refs else "text"}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:400]
        if e.code == 422 and "image_size" in detail:
            return {"images": fire("portrait_4_3"), "mode": "edit" if refs else "text"}
        raise RuntimeError(f"Fal error: {detail}") from e


def generate_ideas(brand: dict, direction: str, count: int, lang: str = "en") -> dict:
    if not _openrouter_key():
        raise RuntimeError("no OPENROUTER_API_KEY configured")
    n = max(1, min(8, count))
    prods = (brand.get("productImages") or [])[:6]
    usable = [(idx, p, _vision_url(_img_url(p))) for idx, p in enumerate(prods)]
    usable = [(idx, p, v) for idx, p, v in usable if v]
    moods = [v for v in (_vision_url(_img_url(m)) for m in (brand.get("imagery") or [])[:3]) if v]
    content: list[dict] = [{"type": "text", "text": ideas_prompt(brand, direction, n, len(usable), lang=lang)}]
    for idx, p, v in usable:
        nm = p.get("name", "") if isinstance(p, dict) else ""
        content.append({"type": "text", "text": f"PRODUCT[{idx}]{(' - ' + nm) if nm else ''}:"})
        content.append({"type": "image_url", "image_url": {"url": v}})
    for v in moods:
        content.append({"type": "text", "text": "IMAGERY (overall mood / vibe reference):"})
        content.append({"type": "image_url", "image_url": {"url": v}})
    system = (
        "You are a world-class DTC creative director. "
        "Reply with valid JSON only — no markdown."
    )
    if lang.lower().startswith("es"):
        system += " Write all user-facing copy in Spanish (español)."
    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]
    model = _ideas_model()
    raw = openrouter_chat(
        msgs,
        model=model,
        max_tokens=2600,
        provider={"order": ["Anthropic"], "allow_fallbacks": True},
    )
    ideas = parse_ideas(raw)
    if not ideas:
        raise RuntimeError(f"could not parse ideas JSON: {raw[:400]}")
    return {"ideas": ideas[:n], "model": model, "products": len(prods)}


def store_image(
    url: str,
    *,
    brand: str,
    post_id: str,
    slide: str,
    role: str,
    user_id: str,
) -> dict:
    if not url.startswith(("http://", "https://")):
        raise ValueError("need an http(s) image url")
    slug = re.sub(r"[^a-z0-9]+", "-", (brand or "brand").lower()).strip("-") or "brand"
    pid = re.sub(r"[^0-9A-Za-z]+", "", str(post_id or "0")) or "0"
    sn = re.sub(r"[^0-9]+", "", str(slide or "0")) or "0"
    role_clean = re.sub(r"[^a-z0-9]+", "", str(role or "").lower())
    safe_user = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_id) or "anon"
    fname = f"post{pid}_slide{sn}{('_' + role_clean) if role_clean else ''}.png"
    storage_path = f"brand-studio/{safe_user}/{slug}/{fname}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
    try:
        public_url = _upload_render_bytes(data, storage_path)
        return {"ok": True, "url": public_url, "bytes": len(data)}
    except Exception as exc:
        folder = _user_dir(user_id) / "renders" / slug
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / fname
        dest.write_bytes(data)
        rel = f"renders/{slug}/{fname}"
        print(f"[brand_studio] Supabase upload failed ({exc}); saved locally at {dest}")
        return {"ok": True, "url": url, "path": rel, "bytes": len(data), "ephemeral": True}


def render_file_path(user_id: str, rel_path: str) -> Path | None:
    """Resolve a stored render relative path for the static fallback route."""
    safe = re.sub(r"[^a-zA-Z0-9_./-]+", "", rel_path or "").strip("/")
    if not safe or ".." in safe.split("/"):
        return None
    if not safe.startswith("renders/"):
        return None
    full = _user_dir(user_id) / safe
    if not full.is_file():
        return None
    return full


def _brand_slug(brand: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (brand or "brand").lower()).strip("-") or "brand"


_RENDER_FNAME = re.compile(r"^post(\d+)_slide(\d+)", re.I)


def list_stored_renders(user_id: str, brand: str) -> dict[str, dict[str, str]]:
    """Return {post_id: {slide_number: public_url}} from Supabase and local disk."""
    slug = _brand_slug(brand)
    safe_user = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_id) or "anon"
    out: dict[str, dict[str, str]] = {}

    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if supabase_url and service_key:
        try:
            from supabase import create_client

            prefix = f"brand-studio/{safe_user}/{slug}"
            sb = create_client(supabase_url, service_key)
            items = sb.storage.from_("user-uploads").list(prefix)
            for item in items or []:
                name = item.get("name") if isinstance(item, dict) else None
                if not name:
                    continue
                m = _RENDER_FNAME.match(name)
                if not m:
                    continue
                pid, sn = m.group(1), m.group(2)
                public = sb.storage.from_("user-uploads").get_public_url(f"{prefix}/{name}")
                out.setdefault(pid, {})[sn] = public
        except Exception as exc:
            print(f"[brand_studio] Supabase render list failed: {exc}")

    folder = _user_dir(user_id) / "renders" / slug
    if folder.is_dir():
        for path in folder.glob("post*_slide*.png"):
            m = _RENDER_FNAME.match(path.name)
            if not m:
                continue
            pid, sn = m.group(1), m.group(2)
            if sn in out.get(pid, {}):
                continue
            try:
                data = path.read_bytes()
                storage_path = f"brand-studio/{safe_user}/{slug}/{path.name}"
                public = _upload_render_bytes(data, storage_path)
                out.setdefault(pid, {})[sn] = public
            except Exception as exc:
                print(f"[brand_studio] local render re-upload failed ({path.name}): {exc}")

    return out
