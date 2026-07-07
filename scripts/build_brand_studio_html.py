#!/usr/bin/env python3
"""Transform themed render-studio index.html into embedded studio.html for /brands."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
THEMED = ROOT / "render-studio" / "index.themed.html"
ZIP_ENTRY = (
    "render-studio-ui-theme-update/project/uploads/render-studio/index.html"
)


def _load_themed_html() -> str:
    if THEMED.exists():
        return THEMED.read_text(encoding="utf-8")
    import zipfile

    zip_path = Path.home() / "Downloads" / "Render-studio UI theme update-handoff.zip"
    with zipfile.ZipFile(zip_path) as zf:
        return zf.read(ZIP_ENTRY).decode("utf-8")


src = _load_themed_html()

m = re.search(r"<style>(.*?)</style>", src, re.S)
style = m.group(1) if m else ""

body_m = re.search(r"<body>(.*?)</body>", src, re.S)
body = body_m.group(1) if body_m else ""

toolbar = (
    '<div class="fallback-banner" id="fallbackBanner"><span>⚠</span>'
    '<span><b>Template mode</b> — OpenRouter is unavailable. Ideas and captions are '
    'built-in placeholders, not Claude Sonnet 4.6. Add <code>OPENROUTER_API_KEY</code> '
    'to env and restart Creative OS.</span>'
    '<button type="button" id="fallbackDismiss">Dismiss</button></div>\n\n'
    "<!-- ===== APP ===== -->"
)
body = re.sub(
    r"<!-- ===== TOP BAR ===== -->.*?<!-- ===== APP ===== -->",
    toolbar,
    body,
    count=1,
    flags=re.S,
)

# Only replace the root `body` selector — not `.left-body`, `.row-body`, etc.
style = re.sub(r"^body\{", ".brand-studio-root{", style, flags=re.M)
style = re.sub(r"^body\.dark", ".brand-studio-root.dark", style, flags=re.M)
style = style.replace("html{color-scheme", ".brand-studio-root{color-scheme")
style = re.sub(
    r"\.app\{([^}]*?)height:calc\(100vh - 60px\)",
    r".app{\1flex:1;min-height:0;height:auto",
    style,
)
style = re.sub(
    r"^\.brand-studio-root\{",
    ".brand-studio-root{height:100%;overflow:hidden;box-sizing:border-box;padding:0;display:flex;flex-direction:column;min-height:0;",
    style,
    count=1,
    flags=re.M,
)
# Flex fill layout (no card inset)
style = style.replace(
    ".topbar{\n  height:60px;",
    ".topbar{\n  height:60px;flex-shrink:0;",
)
style = re.sub(
    r"\.app\{display:grid;grid-template-columns:320px 1fr;[^}]+\}",
    ".app{display:grid;grid-template-columns:320px 1fr;flex:1;min-height:0;height:auto;transition:grid-template-columns .28s ease;overflow:hidden;background:var(--glass-soft);}",
    style,
    count=1,
)
style = style.replace(
    ".panel{overflow-y:auto;overflow-x:hidden;}",
    ".panel{overflow-y:auto;overflow-x:hidden;min-height:0;}",
)
style = style.replace(
    ".panel.left{border-right:1px solid var(--line);background:var(--glass-soft);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);padding:0;position:relative;}",
    ".panel.left{border-right:1px solid var(--line);background:var(--glass-soft);backdrop-filter:blur(16px);-webkit-backdrop-filter:blur(16px);padding:0;position:relative;overflow:hidden;}",
)
RESPONSIVE_CSS = """
@media (max-width:1100px){
  .render-controls{grid-template-columns:1fr;}
  .panel.center{padding:20px 16px 48px;}
}
@media (max-width:768px){
  .app,.app.left-collapsed{grid-template-columns:1fr;}
  .panel.left{max-height:40vh;border-right:none;border-bottom:1px solid var(--line);}
}
"""
if "@media (max-width:1100px)" not in style:
    style = style.rstrip() + RESPONSIVE_CSS
style = style.replace("assets/", "/brands/")
body = body.replace("assets/", "/brands/")
style = re.sub(r"Blotato[^\n]*", "Aitoma Publish", style)

new_sched = """async function schedulePost(p){
  if(p.scheduled)return;
  const imageUrls=(p.slides||[]).map(s=>s&&s.url).filter(u=>/^https?:/i.test(u||''));
  if(!p.rendered || !imageUrls.length){ toast('Render the carousel first - no images to schedule',3800); return; }
  if(window.brandStudioOpenSchedule){
    window.brandStudioOpenSchedule({caption:p.caption,imageUrls});
    return;
  }
  toast('Opening Publish…',2400);
}"""
body = re.sub(r"async function schedulePost\(p\)\{.*?\n\}", new_sched, body, count=1, flags=re.S)
body = re.sub(
    r"/\* ---------- schedule \(full-screen view\) ----------.*?\*/",
    "/* ---------- schedule (opens Aitoma Publish modal) ---------- */",
    body,
    count=1,
    flags=re.S,
)
body = body.replace(
    "if(_schedOpen)_schedOpen.onclick=e=>{e.stopPropagation();window.open('https://my.blotato.com/queue/schedules','_blank','noopener');};",
    "if(_schedOpen)_schedOpen.onclick=e=>{e.stopPropagation();window.brandStudioOpenSchedule&&window.brandStudioOpenSchedule();};",
)
body = body.replace("const SERVED=location.protocol.startsWith('http');", "const SERVED=true;")
body = body.replace(
    "const SERVED=true;",
    "const SERVED=true;\nconst $root=()=>document.querySelector('.brand-studio-root');",
)
body = body.replace(
    "function applyTheme(t){document.body.classList.toggle('dark',t==='dark');",
    "function applyTheme(t){const root=$root();if(root)root.classList.toggle('dark',t==='dark');",
)
body = body.replace(
    "if(_themeBtn)_themeBtn.onclick=()=>{const dark=!document.body.classList.contains('dark');",
    "if(_themeBtn)_themeBtn.onclick=()=>{const root=$root();const dark=!(root&&root.classList.contains('dark'));",
)
body = body.replace(
    "const dark=document.body.classList.contains('dark');",
    "const root=$root();const dark=root&&root.classList.contains('dark');",
)

scripts = re.findall(r"<script>(.*?)</script>", body, re.S)
body = re.sub(r"<script>.*?</script>", "", body, flags=re.S)
extra = (
    "\nconst _viewSched=$('#viewScheduledBtn');"
    "if(_viewSched){_viewSched.onclick=e=>{e.preventDefault();"
    "window.brandStudioOpenSchedule&&window.brandStudioOpenSchedule();};}\n"
)
script_block = "".join(scripts) + extra
out = f'<div class="brand-studio-root">{body}<script>{script_block}</script></div>'
full = f"<style>{style}</style>{out}"

dest = ROOT / "frontend" / "public" / "brands" / "studio.html"
dest.write_text(full, encoding="utf-8")
print(f"wrote {dest} ({len(full)} chars)")
