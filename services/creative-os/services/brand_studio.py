"""Brand Studio — scrape, ideas (OpenRouter), render (Fal GPT Image 2)."""
from __future__ import annotations

import base64
import hashlib
import io
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
    if u.startswith("data:"):
        mime = u.split(";", 1)[0].lower().replace("data:", "").strip()
        if mime not in ("image/jpeg", "image/jpg", "image/png", "image/webp"):
            return ""
        return u
    base = u.split("?", 1)[0].split("#", 1)[0].lower()
    blocked = (".svg", ".ico", ".avif", ".bmp", ".gif")
    if any(base.endswith(ext) for ext in blocked):
        return ""
    if "favicon" in base:
        return ""
    if u.startswith("https://") or u.startswith("data:"):
        return u
    if u.startswith("http://"):
        return "https://" + u[len("http://") :]
    if u.startswith("//"):
        return "https:" + u
    return ""


def _logo_vision_url(logo: dict | str) -> str:
    """Vision-safe logo URL for OpenRouter (excludes favicon / .ico)."""
    u = _img_url(logo)
    if not u:
        return ""
    if isinstance(logo, dict):
        ctx = str(logo.get("context") or "").lower()
        if "favicon" in ctx:
            return ""
    return _vision_url(u)


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
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            out = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:400]
        raise RuntimeError(f"OpenRouter error {e.code}: {detail}") from e
    usage = out.get("usage") or {}
    if usage:
        prompt_tok = usage.get("prompt_tokens", 0)
        completion_tok = usage.get("completion_tokens", 0)
        total_tok = usage.get("total_tokens", prompt_tok + completion_tok)
        est_cogs = (prompt_tok * 3 + completion_tok * 15) / 1_000_000
        print(
            f"[brand_studio] openrouter usage model={body.get('model')} "
            f"prompt_tokens={prompt_tok} completion_tokens={completion_tok} "
            f"total_tokens={total_tok} est_cogs_usd={est_cogs:.4f}"
        )
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


_LOGO_JUNK = (
    "facebook", "twitter", "instagram", "linkedin", "youtube", "pinterest", "tiktok",
    "payment", "visa", "mastercard", "apple-pay", "google-play", "sprite", "flag",
    "badge", "placeholder", "avatar", "gravatar", "emoji",
)


def _classify_logo_hints(text: str) -> tuple[str, str]:
    low = (text or "").lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", low) if t]
    kind = "unknown"
    contrast = "unknown"
    if any(k in tokens or k in low for k in ("favicon", "touchicon", "icon", "mark", "symbol", "glyph")):
        kind = "icon"
    if any(k in tokens for k in ("wordmark", "fulllogo", "horizontal", "lockup")) or "wordmark" in low:
        kind = "wordmark" if kind == "unknown" else "combo"
    elif any(k in tokens for k in ("combo", "stacked", "vertical")):
        kind = "combo"
    elif "logo" in tokens and kind == "unknown":
        kind = "wordmark"
    if re.search(r"\bon[-_]dark\b", low) or re.search(r"\bfor[-_]dark\b", low):
        contrast = "light"
    elif any(k in tokens for k in ("white", "light", "inverted", "reverse")):
        contrast = "light"
    elif any(k in tokens for k in ("dark", "black")):
        contrast = "dark"
    elif re.search(r"\bon[-_]light\b", low) or re.search(r"\bfor[-_]light\b", low):
        contrast = "dark"
    elif any(k in tokens for k in ("color", "colour", "primary")):
        contrast = "color"
    return kind, contrast


def _hex_luminance(hex_color: str) -> float:
    h = (hex_color or "").strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return 0.5
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 0.5
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _palette_dark(palette: list | None) -> bool:
    colors = [c for c in (palette or [])[:2] if isinstance(c, str) and c.startswith("#")]
    if not colors:
        return True
    return sum(_hex_luminance(c) for c in colors) / len(colors) < 0.45


def _classify_brightness_from_url(url: str) -> str | None:
    render = _vision_url(url)
    if not render or render.startswith("data:"):
        return None
    try:
        from PIL import Image
        import io

        req = urllib.request.Request(render, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read()
        if len(data) > 2_000_000:
            return None
        img = Image.open(io.BytesIO(data)).convert("RGBA")
        img.thumbnail((64, 64))
        opaque = [(r, g, b) for r, g, b, a in img.getdata() if a > 128]
        if not opaque:
            return None
        lum = sum(0.299 * r + 0.587 * g + 0.114 * b for r, g, b in opaque) / (255.0 * len(opaque))
        return "light" if lum > 0.55 else "dark"
    except Exception:
        return None


def _logo_is_junk(url: str, context: str = "") -> bool:
    low = f"{url} {context}".lower()
    return any(k in low for k in _LOGO_JUNK)


def _normalize_logo_key(url: str) -> str:
    p = urllib.parse.urlparse(url.split("?", 1)[0].split("#", 1)[0])
    return (p.netloc + p.path).lower()


def _jsonld_logos(html: str, origin: str) -> list[str]:
    urls: list[str] = []
    for block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.I | re.S,
    ):
        try:
            data = json.loads(block.strip())
        except Exception:
            continue

        def walk(obj: Any) -> None:
            if isinstance(obj, dict):
                logo = obj.get("logo")
                if isinstance(logo, str):
                    urls.append(urllib.parse.urljoin(origin, logo))
                elif isinstance(logo, dict) and logo.get("url"):
                    urls.append(urllib.parse.urljoin(origin, logo["url"]))
                for v in obj.values():
                    walk(v)
            elif isinstance(obj, list):
                for v in obj:
                    walk(v)

        walk(data)
    return urls


def _link_icon_logos(html: str, origin: str) -> list[tuple[str, str]]:
    """Return (url, context_hint) from link rel icons, largest sizes first."""
    icons: list[tuple[int, str, str]] = []
    for m in re.finditer(
        r'<link[^>]+rel=["\']([^"\']+)["\'][^>]*>',
        html,
        re.I,
    ):
        tag = m.group(0)
        rel = m.group(1).lower()
        if not any(r in rel for r in ("icon", "apple-touch-icon", "shortcut icon")):
            continue
        href_m = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
        if not href_m:
            continue
        href = urllib.parse.urljoin(origin, unescape(href_m.group(1).strip()))
        sizes_m = re.search(r'sizes=["\']([^"\']+)["\']', tag, re.I)
        size_px = 0
        if sizes_m:
            for part in sizes_m.group(1).split():
                dim = re.match(r"(\d+)x(\d+)", part.strip())
                if dim:
                    size_px = max(size_px, int(dim.group(1)), int(dim.group(2)))
        if "apple-touch" in rel:
            size_px = max(size_px, 180)
        icons.append((size_px, href, rel))
    icons.sort(key=lambda x: x[0], reverse=True)
    return [(u, ctx) for _, u, ctx in icons]


def _header_img_logos(html: str, origin: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for m in re.finditer(r"<img[^>]+>", html[:80_000], re.I):
        tag = m.group(0)
        ctx = tag.lower()
        if "logo" not in ctx and "brand" not in ctx:
            continue
        src_m = re.search(r'src=["\']([^"\']+)["\']', tag, re.I)
        if not src_m:
            continue
        src = urllib.parse.urljoin(origin, unescape(src_m.group(1).strip()))
        if _logo_is_junk(src, ctx):
            continue
        out.append((src, ctx))
    return out


def _path_logos(html: str, origin: str) -> list[str]:
    urls: list[str] = []
    for u in re.findall(
        r'["\']([^"\']*(?:/|\\)?logo[^"\']*\.(?:png|jpg|jpeg|webp|svg|ico))["\']',
        html,
        re.I,
    ):
        full = urllib.parse.urljoin(origin, u.replace("\\", "/"))
        if not _logo_is_junk(full, u):
            urls.append(full)
    return urls


def _make_logo_entry(url: str, *, context: str = "", source: str = "scraped") -> dict:
    kind, contrast = _classify_logo_hints(f"{url} {context}")
    entry = {"url": url, "kind": kind, "contrast": contrast, "source": source}
    if contrast == "unknown" and _vision_url(url):
        bright = _classify_brightness_from_url(url)
        if bright:
            entry["contrast"] = bright
    return entry


def _extract_logos(html: str, origin: str) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []

    def add(url: str, context: str = "") -> None:
        url = (url or "").strip()
        if not url or url.startswith("data:"):
            return
        if not url.startswith("http"):
            url = urllib.parse.urljoin(origin, url)
        key = _normalize_logo_key(url)
        if key in seen or _logo_is_junk(url, context):
            return
        seen.add(key)
        out.append(_make_logo_entry(url, context=context))

    for u in _jsonld_logos(html, origin):
        add(u, "jsonld logo")
    for u, ctx in _link_icon_logos(html, origin):
        add(u, ctx)
    for u, ctx in _header_img_logos(html, origin):
        add(u, ctx)
    for u in _path_logos(html, origin):
        add(u, "path logo")
    add(urllib.parse.urljoin(origin, "/favicon.ico"), "favicon fallback")
    return out[:6]


def should_show_logo(role_tag: str = "", layout: str = "") -> bool:
    """Whether a carousel slide should display the brand logo (post-composited)."""
    tag = (role_tag or "").upper()
    lay = (layout or "").lower()
    if tag in ("HOOK", "SHOP") or lay == "cta":
        return True
    if tag in ("LINEUP", "FLAVOR") or lay == "hero":
        return True
    return False


def logo_placement(role_tag: str = "", layout: str = "") -> str | None:
    """prominent | small | None"""
    if not should_show_logo(role_tag, layout):
        return None
    tag = (role_tag or "").upper()
    lay = (layout or "").lower()
    if tag in ("LINEUP", "FLAVOR") or lay == "hero":
        return "small"
    return "prominent"


def _parse_data_url(url: str) -> tuple[bytes, str]:
    if not url.startswith("data:"):
        raise ValueError("not a data url")
    header, _, payload = url.partition(",")
    mime = header.split(";", 1)[0].replace("data:", "").strip().lower()
    if ";base64" in header:
        return base64.b64decode(payload), mime
    return urllib.parse.unquote_to_bytes(payload), mime


def _fetch_image_bytes(url: str) -> bytes:
    if url.startswith("data:"):
        data, _ = _parse_data_url(url)
        return data
    safe = _vision_url(url) or (url if url.startswith("https://") else "")
    if not safe:
        raise RuntimeError(f"cannot fetch image: {url[:80]}")
    req = urllib.request.Request(safe, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = resp.read()
    if len(data) > 8_000_000:
        raise RuntimeError("image too large")
    return data


def _logo_src_key(src: str) -> str:
    return hashlib.sha256((src or "").encode()).hexdigest()[:16]


def _rasterize_logo_png(data: bytes, *, url_hint: str = "", max_dim: int = 512) -> bytes:
    hint = (url_hint or "").lower()
    if hint.startswith("data:image/jpeg") or hint.startswith("data:image/jpg") or hint.endswith((".jpg", ".jpeg")):
        print("[brand_studio] warning: JPEG logo source cannot preserve transparency — re-upload as PNG")
    is_svg = hint.endswith(".svg") or data[:300].lstrip().startswith((b"<svg", b"<?xml"))
    if is_svg:
        try:
            import cairosvg

            data = cairosvg.svg2png(bytestring=data, output_width=max_dim)
        except ImportError as exc:
            raise RuntimeError("SVG logo — upload a PNG or install cairosvg") from exc
    from PIL import Image, ImageOps

    im = Image.open(io.BytesIO(data))
    im = ImageOps.exif_transpose(im)
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    alpha = im.split()[-1]
    bbox = alpha.getbbox()
    if bbox:
        im = im.crop(bbox)
    if max(im.size) > max_dim:
        im.thumbnail((max_dim, max_dim), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, format="PNG", optimize=True)
    return out.getvalue()


def ensure_logo_render_url(
    logo: dict,
    *,
    user_id: str,
    brand_slug: str,
) -> str:
    """Fetch/rasterize a sidebar logo and return a stable HTTPS PNG URL for Fal refs."""
    if not isinstance(logo, dict):
        return ""
    src = _img_url(logo)
    if not src:
        return ""
    src_key = _logo_src_key(src)
    existing = (logo.get("renderUrl") or "").strip()
    if existing.startswith("https://") and logo.get("_renderSrcKey") == src_key:
        return existing
    try:
        raw = _fetch_image_bytes(src)
        png = _rasterize_logo_png(raw, url_hint=src)
    except Exception as exc:
        print(f"[brand_studio] ensure_logo_render_url failed ({src[:80]}): {exc}")
        return existing if existing.startswith("https://") else ""
    digest = hashlib.sha256(png).hexdigest()[:16]
    safe_user = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_id) or "anon"
    slug = _brand_slug(brand_slug)
    storage_path = f"brand-studio/{safe_user}/{slug}/logos/{digest}.png"
    try:
        public = _upload_render_bytes(png, storage_path)
    except Exception as exc:
        print(f"[brand_studio] logo upload failed: {exc}")
        return existing if existing.startswith("https://") else ""
    logo["renderUrl"] = public
    logo["_renderSrcKey"] = src_key
    return public


def ensure_logos_render_urls(logos: list, user_id: str, brand_slug: str) -> list:
    out: list = []
    for lg in logos or []:
        if isinstance(lg, dict):
            ensure_logo_render_url(lg, user_id=user_id, brand_slug=brand_slug)
            out.append(lg)
        elif isinstance(lg, str) and lg.strip():
            entry = {"url": lg.strip(), "source": "legacy"}
            ensure_logo_render_url(entry, user_id=user_id, brand_slug=brand_slug)
            out.append(entry)
    return out


def _logo_render_url(logo: dict | str) -> str:
    if isinstance(logo, dict):
        render = (logo.get("renderUrl") or "").strip()
        if render.startswith("https://"):
            return render
    u = _img_url(logo)
    if not u:
        return ""
    v = _vision_url(u)
    return v or (u if u.startswith("data:") else "")


def _mirror_ref_url(url: str, *, user_id: str, brand_slug: str, label: str) -> str:
    """Re-host data: or flaky refs as HTTPS PNG for Fal."""
    if not url:
        return ""
    if url.startswith("https://") and _vision_url(url):
        return url
    try:
        raw = _fetch_image_bytes(url)
        from PIL import Image, ImageOps

        im = Image.open(io.BytesIO(raw))
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGBA":
            im = im.convert("RGBA")
        alpha = im.split()[-1]
        bbox = alpha.getbbox()
        if bbox:
            im = im.crop(bbox)
        if max(im.size) > 1536:
            im.thumbnail((1536, 1536), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG", optimize=True)
        png = buf.getvalue()
    except Exception as exc:
        print(f"[brand_studio] mirror ref failed ({url[:60]}): {exc}")
        return _vision_url(url) or ""
    safe_user = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_id) or "anon"
    slug = _brand_slug(brand_slug)
    digest = hashlib.sha256(png).hexdigest()[:12]
    path = f"brand-studio/{safe_user}/{slug}/refs/{label}_{digest}.png"
    try:
        return _upload_render_bytes(png, path)
    except Exception:
        return _vision_url(url) or (url if url.startswith("https://") else "")


def composite_logo_bytes(bg_bytes: bytes, logo_bytes: bytes, placement: str = "prominent") -> bytes:
    from PIL import Image

    bg = Image.open(io.BytesIO(bg_bytes)).convert("RGBA")
    logo = Image.open(io.BytesIO(logo_bytes)).convert("RGBA")
    w, h = bg.size
    pad = max(12, int(min(w, h) * 0.04))
    max_w = int(w * (0.10 if placement == "small" else 0.18))
    lw, lh = logo.size
    if lw <= 0:
        raise ValueError("invalid logo width")
    scale = max_w / lw
    logo = logo.resize((max_w, max(1, int(lh * scale))), Image.LANCZOS)
    bg.paste(logo, (pad, pad), logo)
    out = io.BytesIO()
    bg.convert("RGB").save(out, format="PNG", optimize=True)
    return out.getvalue()


def composite_logo_on_image_url(image_url: str, logo_url: str, placement: str = "prominent") -> bytes:
    bg = _fetch_image_bytes(image_url)
    logo = _fetch_image_bytes(logo_url)
    return composite_logo_bytes(bg, logo, placement)


def select_logo(
    logos: list,
    *,
    role_tag: str = "",
    layout: str = "",
    palette: list | None = None,
    slide_index: int = 0,
    has_product_ref: bool = False,
) -> dict | None:
    if not logos:
        return None
    entries: list[dict] = []
    for lg in logos:
        if not isinstance(lg, dict):
            continue
        url = _img_url(lg)
        if not url:
            continue
        render_url = _logo_render_url(lg)
        if not render_url:
            continue
        entries.append({**lg, "url": url, "_render_url": render_url, "renderUrl": lg.get("renderUrl") or render_url})
    if not entries:
        return None

    tag = (role_tag or "").upper()
    lay = (layout or "").lower()
    want_contrast = "light" if _palette_dark(palette) else "dark"
    if tag in ("HOOK", "SHOP") or lay == "cta":
        want_kinds = ["wordmark", "combo", "icon"]
    elif tag == "PROOF" or lay == "stat":
        want_kinds = ["icon", "combo", "wordmark"]
    elif tag in ("LINEUP", "FLAVOR") or lay == "hero" or has_product_ref:
        want_kinds = ["combo", "wordmark", "icon"]
    else:
        want_kinds = ["combo", "wordmark", "icon"]

    def score(entry: dict) -> int:
        kind = entry.get("kind") or "unknown"
        contrast = entry.get("contrast") or "unknown"
        s = 0
        if kind in want_kinds:
            s += 10 - want_kinds.index(kind) * 2
        if contrast == want_contrast:
            s += 15
        elif contrast == "color":
            s += 8
        elif contrast == "unknown":
            s += 3
        if entry.get("uploaded"):
            s += 2
        return s

    best = max(entries, key=score)
    render = best.get("renderUrl") or best["_render_url"]
    return {
        "url": render,
        "renderUrl": render,
        "kind": best.get("kind") or "unknown",
        "contrast": best.get("contrast") or "unknown",
    }


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
    logos = _extract_logos(html, origin)
    return {
        "name": name[:40],
        "url": p.netloc.replace("www.", ""),
        "scrapedReal": True,
        "fonts": {"display": font, "body": font, "note": "pulled from the site"},
        "colors": _colors(html),
        "voice": (desc[:180] if len(desc.strip()) >= 12 else ""),
        "voiceTags": tags,
        "taglines": headlines,
        "logos": logos,
        "imagery": imagery[:4],
        "productImages": products,
    }


def generate_images(
    prompt: str,
    image_urls: list[str],
    n: int = 1,
    *,
    user_id: str = "",
    brand_slug: str = "",
    logo_policy: str = "hide",
) -> dict:
    prompt = (prompt or "").strip()
    n = max(1, min(5, n))
    refs: list[str] = []
    for idx, u in enumerate(image_urls or []):
        if not u:
            continue
        if user_id and brand_slug:
            v = _mirror_ref_url(u, user_id=user_id, brand_slug=brand_slug, label=f"ref{idx}")
        else:
            v = _vision_url(u) or (u if isinstance(u, str) and u.startswith("data:") else "")
        if v.startswith("https://"):
            refs.append(v)
        if len(refs) >= 3:
            break
    if not prompt:
        raise ValueError("empty prompt")
    fal_key = _fal_key()
    if not fal_key:
        raise RuntimeError("No FAL_KEY found")
    endpoint = FAL_EDIT_ENDPOINT if refs else FAL_ENDPOINT

    def fire(image_size, *, use_fidelity: bool = True):
        body: dict[str, Any] = {
            "prompt": prompt,
            "image_size": image_size,
            "quality": "high",
            "num_images": n,
            "output_format": "png",
        }
        if refs:
            body["image_urls"] = refs
            if use_fidelity:
                body["input_fidelity"] = "high"
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
        images = fire(first_size)
        mode = "edit" if refs else "text"
        est_cogs = 0.225 if mode == "edit" else 0.20
        logo_ref_included = logo_policy == "show" and len(refs) > 0
        print(
            f"[brand_studio] fal gpt-image-2/{mode} logoPolicy={logo_policy} logoRefIncluded={logo_ref_included} "
            f"refs={len(refs)} quality=high input_fidelity={'high' if refs else 'n/a'} "
            f"est_cogs_usd={est_cogs:.3f} images={len(images)}"
        )
        return {"images": images, "mode": mode}
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:400]
        if refs and e.code == 422 and "input_fidelity" in detail.lower():
            images = fire(first_size, use_fidelity=False)
            mode = "edit"
            print(
                f"[brand_studio] fal gpt-image-2/edit logoPolicy={logo_policy} refs={len(refs)} "
                f"(input_fidelity rejected, retried without)"
            )
            return {"images": images, "mode": mode}
        if e.code == 422 and "image_size" in detail:
            images = fire("portrait_4_3")
            mode = "edit" if refs else "text"
            est_cogs = 0.225 if mode == "edit" else 0.20
            print(
                f"[brand_studio] fal gpt-image-2/{mode} logoPolicy={logo_policy} refs={len(refs)} "
                f"quality=high est_cogs_usd={est_cogs:.3f} images={len(images)} (portrait_4_3 fallback)"
            )
            return {"images": images, "mode": mode}
        raise RuntimeError(f"Fal error: {detail}") from e


def _ideas_vision_attachments(brand: dict, *, max_images: int = 4) -> list[tuple[str, str, Any]]:
    """Ordered vision refs for ideas: (label, url, product_obj|None). Capped at max_images."""
    out: list[tuple[str, str, Any]] = []
    for idx, p in enumerate((brand.get("productImages") or [])[:6]):
        v = _vision_url(_img_url(p))
        if v:
            nm = p.get("name", "") if isinstance(p, dict) else ""
            label = f"PRODUCT[{idx}]{(' - ' + nm) if nm else ''}"
            out.append((label, v, p))
    for m in (brand.get("imagery") or [])[:3]:
        v = _vision_url(_img_url(m))
        if v:
            out.append(("IMAGERY (overall mood / vibe reference)", v, None))
    for lg in (brand.get("logos") or [])[:3]:
        v = _logo_vision_url(lg)
        if v:
            out.append(("BRAND LOGO (official mark — keep consistent in ideas)", v, None))
    return out[:max_images]


def _ideas_messages(
    brand: dict,
    direction: str,
    n: int,
    lang: str,
    attachments: list[tuple[str, str, Any]],
) -> list[dict]:
    nprod = sum(1 for label, _, _ in attachments if label.startswith("PRODUCT["))
    content: list[dict] = [
        {"type": "text", "text": ideas_prompt(brand, direction, n, nprod, lang=lang)},
    ]
    for label, url, _ in attachments:
        content.append({"type": "text", "text": f"{label}:"})
        content.append({"type": "image_url", "image_url": {"url": url}})
    system = (
        "You are a world-class DTC creative director. "
        "Reply with valid JSON only — no markdown."
    )
    if lang.lower().startswith("es"):
        system += " Write all user-facing copy in Spanish (español)."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": content},
    ]


def _call_ideas_openrouter(
    brand: dict,
    direction: str,
    n: int,
    lang: str,
    attachments: list[tuple[str, str, Any]],
) -> tuple[str, str]:
    msgs = _ideas_messages(brand, direction, n, lang, attachments)
    model = _ideas_model()
    raw = openrouter_chat(
        msgs,
        model=model,
        max_tokens=2600,
        provider={"order": ["Anthropic"], "allow_fallbacks": True},
    )
    return raw, model


def generate_ideas(brand: dict, direction: str, count: int, lang: str = "en") -> dict:
    if not _openrouter_key():
        raise RuntimeError("no OPENROUTER_API_KEY configured")
    n = max(1, min(8, count))
    prods = (brand.get("productImages") or [])[:6]
    attachments = _ideas_vision_attachments(brand)
    vision_urls = [url for _, url, _ in attachments]

    try:
        raw, model = _call_ideas_openrouter(brand, direction, n, lang, attachments)
        vision_fallback = False
    except RuntimeError as e:
        err = str(e)
        if attachments and "OpenRouter error 415" in err:
            print(
                f"[brand_studio] OpenRouter 415 with {len(vision_urls)} vision image(s); "
                f"retrying text-only. URLs={vision_urls}"
            )
            raw, model = _call_ideas_openrouter(brand, direction, n, lang, [])
            vision_fallback = True
        else:
            raise

    ideas = parse_ideas(raw)
    if not ideas:
        raise RuntimeError(f"could not parse ideas JSON: {raw[:400]}")
    result: dict[str, Any] = {"ideas": ideas[:n], "model": model, "products": len(prods)}
    if vision_fallback:
        result["visionFallback"] = True
    return result


def store_image_bytes(
    data: bytes,
    *,
    brand: str,
    post_id: str,
    slide: str,
    role: str,
    user_id: str,
) -> dict:
    slug = re.sub(r"[^a-z0-9]+", "-", (brand or "brand").lower()).strip("-") or "brand"
    pid = re.sub(r"[^0-9A-Za-z]+", "", str(post_id or "0")) or "0"
    sn = re.sub(r"[^0-9]+", "", str(slide or "0")) or "0"
    role_clean = re.sub(r"[^a-z0-9]+", "", str(role or "").lower())
    safe_user = re.sub(r"[^a-zA-Z0-9_-]+", "_", user_id) or "anon"
    fname = f"post{pid}_slide{sn}{('_' + role_clean) if role_clean else ''}.png"
    storage_path = f"brand-studio/{safe_user}/{slug}/{fname}"
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
        return {"ok": True, "path": rel, "bytes": len(data), "ephemeral": True}


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
