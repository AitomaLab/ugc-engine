# Aitoma Studio — UX/UI Implementation Blueprint

**Date:** Mar 10, 2026
**Author:** Manus AI
**Repository:** `AitomaLab/ugc-engine`
**Frontend Path:** `frontend/src/`

---

## 1. Introduction & Scope

This document is the definitive, self-contained implementation blueprint for overhauling the UGC Engine frontend to match the approved `aitoma-mockup/index.html` design. It covers **every page, every component, and every CSS change** required. No prior document should be referenced; this is the sole source of truth.

### 1.1. Core Design Transformation

| Dimension | Current State | Target State |
|---|---|---|
| Theme | Dark (slate/black) | Light (white/blue) |
| Navigation | Left sidebar | Fixed horizontal header |
| Layout | Full-width, single-column | Header + content area (max 1400px) |
| Font | System default | Inter (Google Fonts) |
| Brand color | Blue gradient | `#337AFF` (primary), `#1A5FD4` (dark) |
| Background | `#0d0f14` | `#F0F4FF` |
| Cards | Glass panels (dark) | White frosted glass with blue borders |

### 1.2. Critical Rules

1. **No emojis anywhere in the UI.** All emoji placeholders in the mockup must be replaced with inline SVG icons or text labels.
2. **No existing functionality must break.** All API calls, state management, and form submissions must be preserved.
3. **All existing routes remain.** New routes are added; no existing routes are removed.
4. **Antigravity design guidelines apply.** The new design uses the Aitoma brand palette, Inter typeface, and the component patterns defined in this document.

---

## 2. Global Styles & CSS Variables

All global styles, CSS variables, and utility classes are managed in a single file.

**File:** `frontend/src/app/globals.css`

**Action:** Replace the entire file content with the following.

```css
/* ─── GOOGLE FONT ───────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

/* ─── BRAND TOKENS ─────────────────────────────────────────── */
:root {
  --blue:        #337AFF;
  --blue-dark:   #1A5FD4;
  --blue-light:  #EBF1FF;
  --blue-glow:   rgba(51, 122, 255, 0.25);
  --bg:          #F0F4FF;
  --surface:     rgba(255, 255, 255, 0.72);
  --surface-2:   rgba(255, 255, 255, 0.55);
  --border:      rgba(51, 122, 255, 0.14);
  --border-soft: rgba(0, 0, 0, 0.07);
  --text-1:      #0D1B3E;
  --text-2:      #4A5578;
  --text-3:      #8A93B0;
  --green:       #22C55E;
  --amber:       #F59E0B;
  --red:         #EF4444;
  --radius:      14px;
  --radius-sm:   8px;
  --shadow:      0 4px 24px rgba(51, 122, 255, 0.10);
  --shadow-lg:   0 8px 40px rgba(51, 122, 255, 0.18);
  --header-h:    60px;
}

/* ─── RESET & BASE ────────────────────────────────────────── */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html { scroll-behavior: smooth; }

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg);
  color: var(--text-1);
  min-height: 100vh;
  overflow-x: hidden;
}

button { cursor: pointer; border: none; background: none; font-family: inherit; }
a { text-decoration: none; color: inherit; }

/* ─── SCROLLBAR ────────────────────────────────────────────── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(51, 122, 255, 0.3); }

/* ─── HEADER ───────────────────────────────────────────────── */
.header {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: var(--header-h);
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border-bottom: 1px solid var(--border);
  display: flex;
  align-items: center;
  padding: 0 24px;
  z-index: 1000;
  box-shadow: 0 2px 16px rgba(51, 122, 255, 0.07);
}

/* Logo */
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-right: 32px;
  flex-shrink: 0;
  text-decoration: none;
}

.logo-mark {
  width: 32px; height: 32px;
  background: linear-gradient(135deg, var(--blue) 0%, var(--blue-dark) 100%);
  border-radius: 8px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 2px 8px var(--blue-glow);
}

.logo-mark svg { width: 18px; height: 18px; fill: white; }

.logo-text {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-1);
  letter-spacing: -0.3px;
}

.logo-text span { color: var(--blue); }

/* Main nav */
.main-nav {
  display: flex;
  align-items: center;
  gap: 2px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: var(--radius-sm);
  font-size: 13.5px;
  font-weight: 500;
  color: var(--text-2);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
  text-decoration: none;
}

.nav-item:hover { background: var(--blue-light); color: var(--blue); }
.nav-item.active { background: var(--blue-light); color: var(--blue); font-weight: 600; }
.nav-item svg { width: 15px; height: 15px; stroke: currentColor; fill: none; stroke-width: 1.75; flex-shrink: 0; }

.nav-divider {
  width: 1px; height: 20px;
  background: var(--border);
  margin: 0 8px;
  flex-shrink: 0;
}

/* Header right actions */
.header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-shrink: 0;
  margin-left: 16px;
}

.btn-cinematic {
  display: flex; align-items: center; gap: 7px;
  padding: 7px 16px;
  border-radius: var(--radius-sm);
  font-size: 13px; font-weight: 600;
  color: var(--blue);
  background: var(--blue-light);
  border: 1.5px solid rgba(51, 122, 255, 0.25);
  transition: all 0.15s;
  text-decoration: none;
}

.btn-cinematic:hover { background: rgba(51, 122, 255, 0.15); border-color: var(--blue); }
.btn-cinematic svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 1.75; }

.btn-create {
  display: flex; align-items: center; gap: 7px;
  padding: 7px 18px;
  border-radius: var(--radius-sm);
  font-size: 13px; font-weight: 600;
  color: white;
  background: linear-gradient(135deg, var(--blue) 0%, var(--blue-dark) 100%);
  box-shadow: 0 2px 12px var(--blue-glow);
  transition: all 0.15s;
  text-decoration: none;
}

.btn-create:hover { box-shadow: 0 4px 20px rgba(51, 122, 255, 0.40); transform: translateY(-1px); }
.btn-create svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 2; }

.icon-btn {
  width: 36px; height: 36px;
  border-radius: var(--radius-sm);
  display: flex; align-items: center; justify-content: center;
  color: var(--text-2);
  transition: all 0.15s;
  position: relative;
}

.icon-btn:hover { background: var(--blue-light); color: var(--blue); }
.icon-btn svg { width: 18px; height: 18px; stroke: currentColor; fill: none; stroke-width: 1.75; }

.notif-dot {
  position: absolute;
  top: 6px; right: 6px;
  width: 7px; height: 7px;
  background: var(--blue);
  border-radius: 50%;
  border: 1.5px solid white;
}

.avatar {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--blue) 0%, #6B4EFF 100%);
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; color: white;
  cursor: pointer;
  border: 2px solid white;
  box-shadow: 0 2px 8px var(--blue-glow);
}

/* Profile dropdown */
.profile-wrapper { position: relative; }

.profile-dropdown {
  display: none;
  position: absolute;
  top: calc(100% + 10px);
  right: 0;
  width: 280px;
  background: rgba(255, 255, 255, 0.97);
  backdrop-filter: blur(20px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: 0 16px 48px rgba(51, 122, 255, 0.18);
  z-index: 2000;
  overflow: hidden;
}

.profile-wrapper.open .profile-dropdown { display: block; }

.pd-header {
  padding: 16px 18px;
  border-bottom: 1px solid var(--border-soft);
  display: flex; align-items: center; gap: 12px;
}

.pd-avatar {
  width: 40px; height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--blue) 0%, #6B4EFF 100%);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: 700; color: white;
  flex-shrink: 0;
}

.pd-name { font-size: 13px; font-weight: 700; color: var(--text-1); }
.pd-plan { font-size: 11px; color: var(--text-3); margin-top: 1px; }

.pd-credits {
  padding: 16px 18px;
  border-bottom: 1px solid var(--border-soft);
}

.pd-credits-label {
  font-size: 10px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.6px;
  color: var(--text-3); margin-bottom: 8px;
}

.pd-credits-row {
  display: flex; align-items: baseline;
  justify-content: space-between; margin-bottom: 8px;
}

.pd-credits-value { font-size: 22px; font-weight: 800; color: var(--text-1); letter-spacing: -0.5px; }
.pd-credits-total { font-size: 12px; color: var(--text-3); }
.pd-bar-bg { height: 6px; background: var(--border); border-radius: 3px; overflow: hidden; margin-bottom: 6px; }
.pd-bar-fill { height: 100%; background: linear-gradient(90deg, var(--blue), #6B4EFF); border-radius: 3px; width: 62%; }
.pd-bar-labels { display: flex; justify-content: space-between; font-size: 10px; color: var(--text-3); margin-bottom: 10px; }

.pd-topup {
  width: 100%; padding: 8px;
  background: linear-gradient(135deg, var(--blue), var(--blue-dark));
  color: white; border-radius: var(--radius-sm);
  font-size: 12px; font-weight: 600; cursor: pointer; text-align: center;
}

.pd-menu-item {
  display: flex; align-items: center; gap: 10px;
  padding: 11px 18px;
  font-size: 13px; font-weight: 500; color: var(--text-2);
  cursor: pointer; transition: background 0.12s;
}

.pd-menu-item:hover { background: var(--blue-light); color: var(--blue); }
.pd-menu-item svg { width: 15px; height: 15px; stroke: currentColor; fill: none; stroke-width: 1.75; flex-shrink: 0; }
.pd-menu-item.danger { color: var(--red); }
.pd-menu-item.danger:hover { background: rgba(239, 68, 68, 0.08); color: var(--red); }
.pd-divider { height: 1px; background: var(--border-soft); margin: 4px 0; }

/* ─── MAIN CONTENT WRAPPER ─────────────────────────────────── */
.app-body {
  margin-top: var(--header-h);
  min-height: calc(100vh - var(--header-h));
}

.content-area {
  padding: 32px 40px;
  max-width: 1400px;
  margin: 0 auto;
}

/* ─── PAGE HEADER ──────────────────────────────────────────── */
.page-header { margin-bottom: 28px; }

.page-header h1 {
  font-size: 26px; font-weight: 800;
  color: var(--text-1); letter-spacing: -0.5px;
}

.page-header h1 span {
  background: linear-gradient(135deg, var(--blue), #6B4EFF);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
}

.page-header p { font-size: 14px; color: var(--text-2); margin-top: 4px; }

/* ─── SECTION TITLE ────────────────────────────────────────── */
.section-title {
  font-size: 15px; font-weight: 700; color: var(--text-1);
  margin-bottom: 16px;
  display: flex; align-items: center; justify-content: space-between;
}

.section-title a { font-size: 12px; font-weight: 500; color: var(--blue); text-decoration: none; }

/* ─── DASHBOARD ────────────────────────────────────────────── */
.stats-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 28px;
}

.stat-card {
  background: var(--surface);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
  box-shadow: var(--shadow);
}

.stat-label {
  font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.6px;
  color: var(--text-3); margin-bottom: 8px;
}

.stat-value {
  font-size: 28px; font-weight: 800;
  color: var(--text-1); letter-spacing: -1px; line-height: 1;
}

.stat-sub { font-size: 12px; color: var(--text-3); margin-top: 4px; }

.stat-badge {
  display: inline-flex; align-items: center; gap: 3px;
  font-size: 11px; font-weight: 600;
  padding: 2px 7px; border-radius: 20px; margin-top: 6px;
}

.stat-badge.up { background: rgba(34, 197, 94, 0.12); color: var(--green); }
.stat-badge.blue { background: var(--blue-light); color: var(--blue); }

/* Campaign tracker */
.tracker-card {
  background: var(--surface);
  backdrop-filter: blur(12px);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 24px;
  box-shadow: var(--shadow);
  margin-bottom: 28px;
}

.tracker-scroll { max-height: 260px; overflow-y: auto; padding-right: 4px; }

.campaign-row {
  display: flex; align-items: center; gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-soft);
}

.campaign-row:last-child { border-bottom: none; padding-bottom: 0; }
.campaign-row:first-child { padding-top: 0; }

.campaign-thumb {
  width: 40px; height: 40px;
  border-radius: 8px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}

/* Campaign thumb icon — use a small SVG or colored square, no emoji */
.campaign-thumb svg { width: 18px; height: 18px; stroke: var(--blue); fill: none; stroke-width: 1.5; }

.campaign-info { flex: 1; min-width: 0; }
.campaign-name { font-size: 13px; font-weight: 600; color: var(--text-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.campaign-meta { font-size: 11px; color: var(--text-3); margin-top: 2px; }

.campaign-progress { width: 80px; }
.prog-bar { height: 4px; background: var(--border); border-radius: 2px; overflow: hidden; margin-bottom: 3px; }
.prog-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, var(--blue), #6B4EFF); }
.prog-label { font-size: 10px; color: var(--text-3); text-align: right; }

.status-pill {
  font-size: 10px; font-weight: 600;
  padding: 3px 8px; border-radius: 20px; flex-shrink: 0;
}

.status-pill.active { background: rgba(34, 197, 94, 0.12); color: var(--green); }
.status-pill.pending { background: rgba(245, 158, 11, 0.12); color: var(--amber); }
.status-pill.done { background: var(--blue-light); color: var(--blue); }
.status-pill.failed { background: rgba(239, 68, 68, 0.12); color: var(--red); }

/* Recent videos grid */
.video-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 14px;
}

.video-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
  transition: all 0.2s;
  cursor: pointer;
}

.video-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); border-color: rgba(51, 122, 255, 0.3); }

.video-thumb {
  aspect-ratio: 9/16;
  position: relative;
  overflow: hidden;
  background-size: cover;
  background-position: center;
}

.video-thumb .play-overlay {
  position: absolute; inset: 0;
  background: rgba(0, 0, 0, 0.3);
  display: flex; align-items: center; justify-content: center;
  opacity: 0; transition: opacity 0.2s;
}

.video-card:hover .play-overlay { opacity: 1; }

.play-btn {
  width: 44px; height: 44px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
}

.play-btn svg { width: 18px; height: 18px; fill: var(--blue); margin-left: 2px; }

.video-info { padding: 10px 12px; }
.video-name { font-size: 12px; font-weight: 600; color: var(--text-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.video-date { font-size: 11px; color: var(--text-3); margin-top: 2px; }

/* Gradient backgrounds for video thumbnails (used as fallback when no real video) */
.grad-1 { background: linear-gradient(160deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); }
.grad-2 { background: linear-gradient(160deg, #1a0533 0%, #2d1b69 50%, #11998e 100%); }
.grad-3 { background: linear-gradient(160deg, #d32f2f 0%, #c2185b 50%, #7b1fa2 100%); }
.grad-4 { background: linear-gradient(160deg, #1e3c72 0%, #2a5298 100%); }
.grad-5 { background: linear-gradient(160deg, #2d1b69 0%, #11998e 100%); }

/* ─── CREATE PAGE ──────────────────────────────────────────── */
.create-layout {
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 0;
  min-height: calc(100vh - var(--header-h));
}

.config-panel {
  background: rgba(255, 255, 255, 0.82);
  backdrop-filter: blur(20px);
  border-right: 1px solid var(--border);
  padding: 24px 20px;
  overflow-y: auto;
  height: calc(100vh - var(--header-h));
  position: sticky;
  top: var(--header-h);
}

.config-section { margin-bottom: 24px; }

.config-label {
  font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.7px;
  color: var(--text-3); margin-bottom: 10px;
  display: flex; align-items: center; justify-content: space-between;
}

/* Progress steps */
.config-step { display: flex; align-items: center; gap: 10px; margin-bottom: 8px; }

.step-num {
  width: 22px; height: 22px;
  border-radius: 50%;
  background: var(--blue); color: white;
  font-size: 11px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}

.step-num.done { background: var(--green); }
.step-num.inactive { background: var(--border); color: var(--text-3); }
.step-text { font-size: 13px; font-weight: 500; color: var(--text-1); }

/* Pill selectors */
.pill-group { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }

.pill {
  padding: 5px 12px;
  border-radius: 20px;
  font-size: 12px; font-weight: 500;
  color: var(--text-2);
  background: var(--surface);
  border: 1.5px solid var(--border);
  cursor: pointer; transition: all 0.15s;
}

.pill:hover { border-color: var(--blue); color: var(--blue); }
.pill.selected { background: var(--blue-light); border-color: var(--blue); color: var(--blue); font-weight: 600; }

/* Config textarea */
.config-textarea {
  width: 100%;
  padding: 10px 12px;
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: inherit; font-size: 13px; color: var(--text-1);
  resize: none; outline: none;
  transition: border-color 0.15s; line-height: 1.5;
}

.config-textarea:focus { border-color: var(--blue); }
.config-textarea::placeholder { color: var(--text-3); }

/* Generate button */
.btn-generate {
  width: 100%; padding: 13px;
  background: linear-gradient(135deg, var(--blue) 0%, var(--blue-dark) 100%);
  color: white;
  border-radius: var(--radius-sm);
  font-size: 14px; font-weight: 700;
  display: flex; align-items: center; justify-content: center; gap: 8px;
  box-shadow: 0 4px 16px var(--blue-glow);
  transition: all 0.15s; margin-top: 8px; cursor: pointer;
}

.btn-generate:hover { box-shadow: 0 6px 24px rgba(51, 122, 255, 0.45); transform: translateY(-1px); }
.btn-generate:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

.btn-generate .credit-cost {
  background: rgba(255, 255, 255, 0.2);
  padding: 2px 8px; border-radius: 10px; font-size: 12px;
}

/* Product selector in config panel */
.prod-filter-pills { display: flex; gap: 4px; }

.prod-filter {
  font-size: 10px; font-weight: 600;
  padding: 2px 8px; border-radius: 20px; cursor: pointer;
  background: transparent; color: var(--text-3);
  border: 1px solid var(--border-soft); transition: all 0.12s;
}

.prod-filter.active { background: var(--blue-light); color: var(--blue); border-color: rgba(51, 122, 255, 0.25); }

.product-selector-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 7px; margin-top: 8px;
}

.prod-card {
  border-radius: var(--radius-sm);
  border: 2px solid var(--border);
  background: var(--surface);
  cursor: pointer; transition: all 0.15s;
  overflow: hidden; text-align: center;
}

.prod-card:hover { border-color: var(--blue); }
.prod-card.selected { border-color: var(--blue); background: var(--blue-light); }
.prod-card.hidden { display: none; }

.prod-thumb {
  aspect-ratio: 1;
  display: flex; align-items: center; justify-content: center;
  background-size: cover; background-position: center;
}

/* Prod thumb icon — use actual product image; SVG icon as fallback */
.prod-thumb svg { width: 20px; height: 20px; stroke: var(--blue); fill: none; stroke-width: 1.75; }

.prod-card-name { font-size: 10px; font-weight: 700; color: var(--text-1); padding: 4px 4px 1px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.prod-card-type { font-size: 9px; color: var(--text-3); padding: 0 4px 5px; }
.prod-card.selected .prod-card-name { color: var(--blue); }

/* Video count stepper */
.video-count-row { display: flex; align-items: center; gap: 10px; margin-top: 4px; }

.count-btn {
  width: 30px; height: 30px;
  border-radius: 8px;
  background: var(--surface);
  border: 1.5px solid var(--border);
  font-size: 18px; font-weight: 600; color: var(--text-1);
  display: flex; align-items: center; justify-content: center;
  cursor: pointer; transition: all 0.12s;
}

.count-btn:hover { background: var(--blue-light); border-color: var(--blue); color: var(--blue); }

.count-display {
  font-size: 20px; font-weight: 800; color: var(--text-1);
  min-width: 28px; text-align: center; letter-spacing: -0.5px;
}

.count-label { font-size: 11px; font-weight: 600; color: var(--text-2); flex: 1; }
.count-label.campaign { color: var(--blue); }

.count-hint { font-size: 10px; color: var(--text-3); margin-top: 5px; transition: all 0.2s; }
.count-hint.campaign { color: var(--blue); font-weight: 600; }

/* Generation summary box */
.gen-summary {
  background: var(--blue-light);
  border: 1.5px solid rgba(51, 122, 255, 0.2);
  border-radius: var(--radius-sm);
  padding: 12px 14px; margin-bottom: 12px;
}

.gen-summary-title {
  font-size: 11px; font-weight: 700;
  text-transform: uppercase; letter-spacing: 0.6px;
  color: var(--blue); margin-bottom: 8px;
}

.gen-summary-row {
  display: flex; justify-content: space-between;
  font-size: 12px; color: var(--text-2); margin-bottom: 4px;
}

.gen-summary-row span:last-child { font-weight: 600; color: var(--text-1); }

.gen-summary-divider { border-top: 1px solid rgba(51, 122, 255, 0.2); margin: 8px 0; }

.gen-summary-total {
  display: flex; justify-content: space-between;
  font-size: 13px; font-weight: 700; color: var(--text-1);
}

.gen-summary-total span:last-child { color: var(--blue); }

/* Right workspace */
.workspace { padding: 32px 40px; overflow-y: auto; }

/* How it works panel */
.how-it-works {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 32px;
  text-align: center;
  margin-bottom: 24px;
  box-shadow: var(--shadow);
}

.hiw-title { font-size: 22px; font-weight: 800; color: var(--text-1); margin-bottom: 6px; letter-spacing: -0.5px; }
.hiw-title span { color: var(--blue); }
.hiw-sub { font-size: 13px; color: var(--text-2); margin-bottom: 28px; }

.hiw-steps { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }

.hiw-step-num {
  width: 32px; height: 32px;
  background: var(--blue); color: white;
  border-radius: 8px; font-size: 14px; font-weight: 800;
  display: flex; align-items: center; justify-content: center;
  margin: 0 auto 12px;
}

.hiw-step-img {
  aspect-ratio: 4/3;
  border-radius: var(--radius-sm);
  margin-bottom: 12px;
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}

.hiw-step-label { font-size: 12px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--text-1); margin-bottom: 4px; }
.hiw-step-desc { font-size: 12px; color: var(--text-2); }

/* Influencer selector grid */
.influencer-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px; margin-bottom: 24px;
}

.inf-card {
  border-radius: var(--radius);
  overflow: hidden; cursor: pointer;
  position: relative;
  border: 2.5px solid transparent;
  transition: all 0.2s;
  box-shadow: var(--shadow);
}

.inf-card:hover { border-color: rgba(51, 122, 255, 0.5); transform: translateY(-2px); }
.inf-card.selected { border-color: var(--blue); box-shadow: 0 0 0 3px var(--blue-glow); }

.inf-thumb {
  aspect-ratio: 9/16;
  display: flex; align-items: flex-end; justify-content: center;
  padding-bottom: 12px; position: relative;
  background-size: cover; background-position: center;
}

.inf-name {
  font-size: 13px; font-weight: 700; color: white;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
  position: relative; z-index: 2;
}

.inf-thumb::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0;
  height: 60%;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.7) 0%, transparent 100%);
}

.inf-check {
  position: absolute; top: 8px; right: 8px;
  width: 22px; height: 22px;
  background: var(--blue); border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  z-index: 3; opacity: 0; transition: opacity 0.15s;
}

.inf-card.selected .inf-check { opacity: 1; }
.inf-check svg { width: 12px; height: 12px; stroke: white; fill: none; stroke-width: 2.5; }

/* ─── ASSET PAGES (Videos, Influencers, Scripts, etc.) ─────── */
.asset-toolbar {
  display: flex; align-items: center; gap: 10px;
  margin-bottom: 24px; flex-wrap: wrap;
}

.asset-toolbar-left { flex: 1; display: flex; gap: 10px; align-items: center; }

.search-box {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 14px;
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  min-width: 220px;
}

.search-box svg { width: 15px; height: 15px; stroke: var(--text-3); fill: none; stroke-width: 1.75; flex-shrink: 0; }
.search-box input { border: none; background: none; font-family: inherit; font-size: 13px; color: var(--text-1); outline: none; width: 100%; }
.search-box input::placeholder { color: var(--text-3); }

.filter-select {
  padding: 8px 14px;
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: inherit; font-size: 13px; color: var(--text-2);
  outline: none; cursor: pointer;
}

/* Videos page grid */
.videos-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
}

.vcard {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow);
  transition: all 0.2s;
}

.vcard:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); border-color: rgba(51, 122, 255, 0.3); }

.vcard-thumb {
  aspect-ratio: 9/16;
  position: relative;
  display: flex; align-items: flex-start; justify-content: flex-end;
  padding: 8px;
  background-size: cover; background-position: center;
}

.vcard-badge {
  font-size: 10px; font-weight: 700;
  padding: 3px 8px; border-radius: 20px;
  z-index: 2; position: relative; color: white;
}

.vcard-badge.done { background: rgba(34, 197, 94, 0.9); }
.vcard-badge.processing { background: rgba(245, 158, 11, 0.9); }
.vcard-badge.queued { background: rgba(139, 92, 246, 0.9); }
.vcard-badge.failed { background: rgba(239, 68, 68, 0.9); }

.vcard-info { padding: 10px 12px; }
.vcard-name { font-size: 12px; font-weight: 600; color: var(--text-1); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.vcard-meta { font-size: 11px; color: var(--text-3); margin-top: 2px; }

.vcard-actions { display: flex; gap: 6px; padding: 0 12px 10px; }

.vcard-action-btn {
  flex: 1; padding: 5px;
  border-radius: 6px; font-size: 11px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; gap: 4px;
  cursor: pointer; transition: all 0.15s;
}

.vcard-action-btn.primary { background: var(--blue-light); color: var(--blue); border: 1px solid rgba(51, 122, 255, 0.2); }
.vcard-action-btn.secondary { background: var(--surface); color: var(--text-2); border: 1px solid var(--border-soft); }
.vcard-action-btn svg { width: 11px; height: 11px; stroke: currentColor; fill: none; stroke-width: 2; }

/* Influencers page */
.influencers-grid {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
}

.icard {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow);
  transition: all 0.2s; cursor: pointer;
}

.icard:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); border-color: rgba(51, 122, 255, 0.3); }

.icard-thumb {
  aspect-ratio: 9/16;
  position: relative;
  display: flex; align-items: flex-end; justify-content: center;
  padding-bottom: 12px;
  background-size: cover; background-position: center;
}

.icard-thumb::after {
  content: '';
  position: absolute; bottom: 0; left: 0; right: 0;
  height: 55%;
  background: linear-gradient(to top, rgba(0, 0, 0, 0.75) 0%, transparent 100%);
}

.icard-name {
  font-size: 14px; font-weight: 700; color: white;
  text-shadow: 0 1px 4px rgba(0, 0, 0, 0.5);
  position: relative; z-index: 2;
}

.icard-info { padding: 10px 12px; }
.icard-tags { display: flex; gap: 4px; flex-wrap: wrap; margin-bottom: 8px; }
.icard-tag { font-size: 10px; font-weight: 500; padding: 2px 7px; border-radius: 20px; background: var(--blue-light); color: var(--blue); }

.icard-btn {
  width: 100%; padding: 7px;
  background: linear-gradient(135deg, var(--blue), var(--blue-dark));
  color: white; border-radius: 6px;
  font-size: 12px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; gap: 5px;
  cursor: pointer; box-shadow: 0 2px 8px var(--blue-glow);
}

.icard-btn svg { width: 12px; height: 12px; stroke: currentColor; fill: none; stroke-width: 2; }

/* Scripts page */
.scripts-list { display: flex; flex-direction: column; gap: 12px; }

.script-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 18px 20px; box-shadow: var(--shadow);
  display: flex; align-items: flex-start; gap: 16px;
  cursor: pointer; transition: all 0.2s;
}

.script-card:hover { border-color: rgba(51, 122, 255, 0.3); box-shadow: var(--shadow-lg); }

.script-icon {
  width: 40px; height: 40px;
  background: var(--blue-light); border-radius: 10px;
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}

.script-icon svg { width: 18px; height: 18px; stroke: var(--blue); fill: none; stroke-width: 1.75; }

.script-body { flex: 1; min-width: 0; }
.script-name { font-size: 14px; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.script-preview { font-size: 12px; color: var(--text-2); line-height: 1.5; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.script-meta { font-size: 11px; color: var(--text-3); margin-top: 6px; display: flex; gap: 12px; }

.script-actions { display: flex; gap: 8px; align-items: center; flex-shrink: 0; }

.script-action-btn {
  padding: 6px 12px; border-radius: 6px;
  font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s;
}

.script-action-btn.primary { background: var(--blue-light); color: var(--blue); border: 1px solid rgba(51, 122, 255, 0.2); }
.script-action-btn.ghost { background: transparent; color: var(--text-3); border: 1px solid var(--border-soft); }

/* App Clips page */
.clips-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.clip-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow);
  transition: all 0.2s; cursor: pointer;
}

.clip-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); border-color: rgba(51, 122, 255, 0.3); }

.clip-thumb {
  aspect-ratio: 16/9;
  display: flex; align-items: center; justify-content: center;
  position: relative;
  background-size: cover; background-position: center;
}

/* Clip thumb icon — use actual video preview or SVG icon, no emoji */
.clip-thumb svg { width: 32px; height: 32px; stroke: rgba(255,255,255,0.6); fill: none; stroke-width: 1.5; }

.clip-info { padding: 12px 14px; }
.clip-name { font-size: 13px; font-weight: 600; color: var(--text-1); margin-bottom: 3px; }
.clip-meta { font-size: 11px; color: var(--text-3); }

/* Products page */
.products-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.product-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow);
  transition: all 0.2s;
}

.product-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); border-color: rgba(51, 122, 255, 0.3); }

.product-img {
  aspect-ratio: 1;
  display: flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #f8f9ff 0%, #eef2ff 100%);
  overflow: hidden;
}

.product-img img { width: 100%; height: 100%; object-fit: cover; }

/* Fallback icon for product image */
.product-img svg { width: 48px; height: 48px; stroke: var(--text-3); fill: none; stroke-width: 1.25; }

.product-info { padding: 14px 16px; }
.product-name { font-size: 14px; font-weight: 600; color: var(--text-1); margin-bottom: 4px; }
.product-meta { font-size: 12px; color: var(--text-3); }

.product-actions { display: flex; gap: 8px; padding: 0 16px 14px; }

.product-btn {
  flex: 1; padding: 7px; border-radius: 6px;
  font-size: 12px; font-weight: 600;
  display: flex; align-items: center; justify-content: center; gap: 4px;
  cursor: pointer; transition: all 0.15s;
}

.product-btn.primary { background: var(--blue); color: white; box-shadow: 0 2px 8px var(--blue-glow); }
.product-btn.secondary { background: var(--surface); color: var(--text-2); border: 1px solid var(--border-soft); }
.product-btn svg { width: 12px; height: 12px; stroke: currentColor; fill: none; stroke-width: 2; }

/* ─── ACTIVITY PAGE ────────────────────────────────────────── */
.activity-table {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow);
}

.table-header {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr 1fr 120px;
  padding: 12px 20px;
  background: rgba(51, 122, 255, 0.04);
  border-bottom: 1px solid var(--border);
}

.th { font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: var(--text-3); }

.table-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr 1fr 120px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-soft);
  align-items: center; transition: background 0.15s;
}

.table-row:last-child { border-bottom: none; }
.table-row:hover { background: rgba(51, 122, 255, 0.03); }

.td { font-size: 13px; color: var(--text-1); }
.td.muted { color: var(--text-3); font-size: 12px; }

.job-name-cell { display: flex; align-items: center; gap: 10px; }

.job-icon {
  width: 32px; height: 32px;
  border-radius: 8px; background: var(--blue-light);
  display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}

.job-icon svg { width: 14px; height: 14px; stroke: var(--blue); fill: none; stroke-width: 1.75; }

.job-name { font-size: 13px; font-weight: 600; color: var(--text-1); }
.job-id { font-size: 11px; color: var(--text-3); }

.campaign-tag {
  display: inline-block; font-size: 11px; font-weight: 600;
  padding: 3px 8px; border-radius: 20px;
  background: var(--blue-light); color: var(--blue);
}

.row-actions { display: flex; gap: 6px; }

.row-btn {
  padding: 5px 10px; border-radius: 6px;
  font-size: 11px; font-weight: 600; cursor: pointer; transition: all 0.15s;
}

.row-btn.primary { background: var(--blue-light); color: var(--blue); border: 1px solid rgba(51, 122, 255, 0.2); }
.row-btn.ghost { background: transparent; color: var(--text-3); border: 1px solid var(--border-soft); }

/* ─── CINEMATIC SHOTS PAGE ─────────────────────────────────── */
.cinematic-layout {
  display: grid;
  grid-template-columns: 300px 1fr;
  gap: 0;
  min-height: calc(100vh - var(--header-h));
}

.upload-zone {
  border: 2px dashed var(--border);
  border-radius: var(--radius);
  padding: 32px 20px;
  text-align: center; cursor: pointer; transition: all 0.15s;
}

.upload-zone:hover { background: var(--blue-light); border-color: var(--blue); }

.upload-zone svg {
  width: 28px; height: 28px;
  stroke: var(--blue); fill: none; stroke-width: 1.5;
  margin: 0 auto 8px; display: block;
}

.upload-zone p { font-size: 13px; color: var(--text-2); }
.upload-zone p span { color: var(--blue); font-weight: 600; }

.shot-type-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px; margin-bottom: 16px;
}

.shot-type-card {
  aspect-ratio: 1;
  border-radius: var(--radius-sm);
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 6px; cursor: pointer;
  border: 2px solid var(--border);
  background: var(--surface);
  transition: all 0.15s; padding: 8px; text-align: center;
}

.shot-type-card:hover { border-color: var(--blue); background: var(--blue-light); }
.shot-type-card.selected { border-color: var(--blue); background: var(--blue-light); }

/* Shot type icon — use SVG icon, no emoji */
.shot-type-card .shot-icon svg { width: 20px; height: 20px; stroke: var(--text-2); fill: none; stroke-width: 1.5; }
.shot-type-card.selected .shot-icon svg { stroke: var(--blue); }

.shot-type-card .shot-label { font-size: 10px; font-weight: 600; color: var(--text-2); }
.shot-type-card.selected .shot-label { color: var(--blue); }

.cinematic-workspace {
  padding: 32px 40px;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  min-height: calc(100vh - var(--header-h));
}

.shot-preview {
  width: 320px; aspect-ratio: 1;
  border-radius: var(--radius);
  background: linear-gradient(135deg, #eef2ff 0%, #f8f9ff 100%);
  border: 1px solid var(--border);
  display: flex; align-items: center; justify-content: center;
  box-shadow: var(--shadow-lg);
  margin-bottom: 20px; position: relative; overflow: hidden;
}

.shot-preview-label { font-size: 13px; color: var(--text-2); text-align: center; }

/* ─── MODALS ───────────────────────────────────────────────── */
.modal-overlay {
  position: fixed; inset: 0; z-index: 50;
  display: flex; align-items: center; justify-content: center;
  background: rgba(13, 27, 62, 0.5);
  backdrop-filter: blur(8px);
  padding: 16px;
}

.modal-box {
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  width: 100%; max-width: 520px;
  overflow: hidden; box-shadow: var(--shadow-lg);
}

.modal-header {
  padding: 20px 24px;
  border-bottom: 1px solid var(--border-soft);
  display: flex; justify-content: space-between; align-items: center;
}

.modal-header h3 { font-size: 16px; font-weight: 700; color: var(--text-1); }

.modal-close {
  width: 28px; height: 28px;
  border-radius: 6px; display: flex; align-items: center; justify-content: center;
  color: var(--text-3); transition: all 0.15s; cursor: pointer;
}

.modal-close:hover { background: var(--blue-light); color: var(--blue); }
.modal-close svg { width: 16px; height: 16px; stroke: currentColor; fill: none; stroke-width: 2; }

.modal-body { padding: 24px; max-height: 70vh; overflow-y: auto; }

.modal-footer {
  padding: 16px 24px;
  border-top: 1px solid var(--border-soft);
  display: flex; justify-content: flex-end; gap: 10px;
}

/* ─── FORM ELEMENTS ────────────────────────────────────────── */
.input-field {
  width: 100%;
  padding: 9px 12px;
  background: white;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  font-family: inherit; font-size: 13px; color: var(--text-1);
  outline: none; transition: border-color 0.15s;
}

.input-field:focus { border-color: var(--blue); }
.input-field::placeholder { color: var(--text-3); }

.form-label {
  display: block;
  font-size: 11px; font-weight: 600;
  text-transform: uppercase; letter-spacing: 0.5px;
  color: var(--text-3); margin-bottom: 6px;
}

.form-label .required { color: var(--red); margin-left: 2px; }

.form-group { margin-bottom: 18px; }

/* ─── BUTTONS (generic) ────────────────────────────────────── */
.btn-primary {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  padding: 9px 20px;
  background: linear-gradient(135deg, var(--blue), var(--blue-dark));
  color: white; border-radius: var(--radius-sm);
  font-size: 13px; font-weight: 600;
  box-shadow: 0 2px 12px var(--blue-glow);
  transition: all 0.15s; cursor: pointer;
}

.btn-primary:hover { box-shadow: 0 4px 20px rgba(51, 122, 255, 0.4); transform: translateY(-1px); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; transform: none; }

.btn-secondary {
  display: inline-flex; align-items: center; justify-content: center; gap: 6px;
  padding: 9px 20px;
  background: transparent; color: var(--text-2);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 13px; font-weight: 600;
  transition: all 0.15s; cursor: pointer;
}

.btn-secondary:hover { background: var(--blue-light); color: var(--blue); border-color: var(--blue); }

/* ─── EMPTY STATE ──────────────────────────────────────────── */
.empty-state {
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  padding: 60px 20px; text-align: center;
}

.empty-icon {
  width: 64px; height: 64px;
  background: var(--blue-light); border-radius: 16px;
  display: flex; align-items: center; justify-content: center; margin-bottom: 16px;
}

.empty-icon svg { width: 28px; height: 28px; stroke: var(--blue); fill: none; stroke-width: 1.5; }

.empty-title { font-size: 17px; font-weight: 700; color: var(--text-1); margin-bottom: 6px; }
.empty-sub { font-size: 13px; color: var(--text-2); max-width: 300px; line-height: 1.5; margin-bottom: 20px; }

/* ─── RESPONSIVE ───────────────────────────────────────────── */
@media (max-width: 1200px) {
  .stats-row { grid-template-columns: repeat(3, 1fr); }
  .video-grid { grid-template-columns: repeat(4, 1fr); }
  .videos-grid { grid-template-columns: repeat(4, 1fr); }
  .influencers-grid { grid-template-columns: repeat(4, 1fr); }
  .influencer-grid { grid-template-columns: repeat(3, 1fr); }
  .products-grid { grid-template-columns: repeat(3, 1fr); }
  .clips-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 900px) {
  .content-area { padding: 24px 20px; }
  .stats-row { grid-template-columns: repeat(2, 1fr); }
  .create-layout { grid-template-columns: 1fr; }
  .cinematic-layout { grid-template-columns: 1fr; }
  .config-panel { height: auto; position: static; }
  .videos-grid { grid-template-columns: repeat(3, 1fr); }
  .influencers-grid { grid-template-columns: repeat(3, 1fr); }
  .products-grid { grid-template-columns: repeat(2, 1fr); }
  .clips-grid { grid-template-columns: repeat(2, 1fr); }
  .table-header, .table-row { grid-template-columns: 2fr 1fr 1fr 80px; }
  .table-header .th:nth-child(3),
  .table-row .td:nth-child(3) { display: none; }
}
```

---

## 3. Root Layout (`layout.tsx`)

The root layout is updated to remove the old sidebar and introduce the new `Header` component.

**File:** `frontend/src/app/layout.tsx`

**Action:** Replace the entire file content.

```tsx
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import './globals.css';
import { Header } from '@/components/layout/Header';

const inter = Inter({ subsets: ['latin'], weight: ['300','400','500','600','700','800'] });

export const metadata: Metadata = {
  title: 'Aitoma Studio',
  description: 'AI-powered UGC video generation engine',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <Header />
        <main className="app-body">
          {children}
        </main>
      </body>
    </html>
  );
}
```

---

## 4. Header Component

This is a new component that replaces the old sidebar navigation.

**Action:** Create the directory `frontend/src/components/layout/` and the file `Header.tsx` within it.

**File:** `frontend/src/components/layout/Header.tsx`

```tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState } from 'react';

// SVG icon components — no emoji allowed
const IconGrid = () => <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>;
const IconPlay = () => <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polygon points="10,8 16,12 10,16"/></svg>;
const IconVideo = () => <svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>;
const IconUser = () => <svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>;
const IconFile = () => <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>;
const IconPhone = () => <svg viewBox="0 0 24 24"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>;
const IconBox = () => <svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>;
const IconActivity = () => <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>;
const IconArrowRight = () => <svg viewBox="0 0 24 24"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>;
const IconPlus = () => <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>;
const IconBell = () => <svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>;
const IconCheck = () => <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>;
const IconSettings = () => <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>;
const IconStar = () => <svg viewBox="0 0 24 24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>;
const IconLogOut = () => <svg viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>;
const IconLogoMark = () => <svg viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/></svg>;

const NAV_ITEMS = [
  { href: '/', label: 'Studio', Icon: IconGrid },
  { href: '/create', label: 'Create', Icon: IconPlay },
  { divider: true },
  { href: '/library', label: 'Videos', Icon: IconVideo },
  { href: '/influencers', label: 'Influencers', Icon: IconUser },
  { href: '/scripts', label: 'Scripts', Icon: IconFile },
  { href: '/app-clips', label: 'App Clips', Icon: IconPhone },
  { href: '/products', label: 'Products', Icon: IconBox },
  { divider: true },
  { href: '/activity', label: 'Activity', Icon: IconActivity },
];

function NavItem({ href, label, Icon }: { href: string; label: string; Icon: React.ComponentType }) {
  const pathname = usePathname();
  const isActive = pathname === href || (href !== '/' && pathname.startsWith(href));
  return (
    <Link href={href} className={`nav-item ${isActive ? 'active' : ''}`}>
      <Icon />
      {label}
    </Link>
  );
}

function ProfileDropdown() {
  const [open, setOpen] = useState(false);
  return (
    <div className={`profile-wrapper ${open ? 'open' : ''}`} onClick={() => setOpen(!open)}>
      <div className="avatar">AS</div>
      <div className="profile-dropdown" onClick={e => e.stopPropagation()}>
        <div className="pd-header">
          <div className="pd-avatar">AS</div>
          <div>
            <div className="pd-name">Aitoma Studio</div>
            <div className="pd-plan">Creator Plan · Resets in 18 days</div>
          </div>
        </div>
        <div className="pd-credits">
          <div className="pd-credits-label">Monthly Credits</div>
          <div className="pd-credits-row">
            <span className="pd-credits-value">1,860</span>
            <span className="pd-credits-total">of 3,000</span>
          </div>
          <div className="pd-bar-bg"><div className="pd-bar-fill" /></div>
          <div className="pd-bar-labels"><span>Used: 1,140</span><span>62% remaining</span></div>
          <button className="pd-topup">Top Up Credits</button>
        </div>
        <div className="pd-menu-item"><IconUser />View Profile</div>
        <div className="pd-menu-item"><IconSettings />Manage Account</div>
        <div className="pd-menu-item"><IconStar />Upgrade Plan</div>
        <div className="pd-divider" />
        <div className="pd-menu-item danger"><IconLogOut />Sign Out</div>
      </div>
    </div>
  );
}

export function Header() {
  return (
    <header className="header">
      <Link href="/" className="logo">
        <div className="logo-mark"><IconLogoMark /></div>
        <span className="logo-text">Aitoma <span>Studio</span></span>
      </Link>

      <nav className="main-nav">
        {NAV_ITEMS.map((item, i) =>
          'divider' in item ? (
            <div key={`div-${i}`} className="nav-divider" />
          ) : (
            <NavItem key={item.href} href={item.href!} label={item.label!} Icon={item.Icon!} />
          )
        )}
      </nav>

      <div className="header-actions">
        <Link href="/cinematic" className="btn-cinematic">
          <IconArrowRight />
          Cinematic Shots
        </Link>
        <Link href="/create" className="btn-create">
          <IconPlus />
          Create Video
        </Link>
        <div className="nav-divider" />
        <button className="icon-btn">
          <IconBell />
          <span className="notif-dot" />
        </button>
        <ProfileDropdown />
      </div>
    </header>
  );
}
```

---

## 5. Dashboard / Studio Page (`/`)

**File:** `frontend/src/app/page.tsx`

**Action:** Replace the JSX return value of the `Home` component. Preserve all existing data fetching (`apiFetch`, `useState`, `useEffect`, `stats`, `jobs` state). The component structure below maps the existing data to the new layout.

```tsx
// Keep all existing imports and data fetching logic unchanged.
// Only replace the JSX returned by the component.

return (
  <div className="content-area">
    {/* Page Header */}
    <div className="page-header">
      <h1>Good morning, <span>Studio</span></h1>
      <p>Here is what is happening with your campaigns today.</p>
    </div>

    {/* Stats Row — map from existing stats state */}
    <div className="stats-row">
      <div className="stat-card">
        <div className="stat-label">Total Videos</div>
        <div className="stat-value">{stats?.total_jobs ?? 0}</div>
        <div className="stat-sub">All time</div>
        {stats?.total_jobs > 0 && <div className="stat-badge up">+{stats.total_jobs} generated</div>}
      </div>
      <div className="stat-card">
        <div className="stat-label">Active Campaigns</div>
        <div className="stat-value">{stats?.processing ?? 0}</div>
        <div className="stat-sub">Currently generating</div>
        {stats?.pending > 0 && <div className="stat-badge blue">{stats.pending} in queue</div>}
      </div>
      <div className="stat-card">
        <div className="stat-label">Success Rate</div>
        <div className="stat-value">{successRate}%</div>
        <div className="stat-sub">Last 30 days</div>
        <div className="stat-badge up">{stats?.success ?? 0} completed</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">AI Influencers</div>
        <div className="stat-value">{stats?.influencers ?? 0}</div>
        <div className="stat-sub">Active profiles</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Total Spend</div>
        <div className="stat-value">${costStats?.total_spend_month?.toFixed(2) ?? '0.00'}</div>
        <div className="stat-sub">This month</div>
      </div>
    </div>

    {/* Campaign Tracker */}
    <div className="tracker-card">
      <div className="section-title">
        Campaign Tracker
        <Link href="/activity">View all</Link>
      </div>
      <div className="tracker-scroll">
        {activeCampaigns.map(campaign => (
          <div key={campaign.name} className="campaign-row">
            <div className="campaign-thumb" style={{background: 'var(--blue-light)'}}>
              {/* Use a video icon SVG — no emoji */}
              <svg viewBox="0 0 24 24"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
            </div>
            <div className="campaign-info">
              <div className="campaign-name">{campaign.name}</div>
              <div className="campaign-meta">{campaign.meta}</div>
            </div>
            <div className="campaign-progress">
              <div className="prog-bar">
                <div className="prog-fill" style={{width: `${campaign.progress}%`}} />
              </div>
              <div className="prog-label">{campaign.done}/{campaign.total} done</div>
            </div>
            <div className={`status-pill ${campaign.status}`}>{campaign.statusLabel}</div>
          </div>
        ))}
      </div>
    </div>

    {/* Recent Videos */}
    <div className="section-title">
      Recent Videos
      <Link href="/library">View all</Link>
    </div>
    <div className="video-grid">
      {recentVideos.map((job, i) => (
        <div key={job.id} className="video-card" onClick={() => job.final_video_url && window.open(job.final_video_url)}>
          <div className={`video-thumb grad-${(i % 5) + 1}`}>
            {job.final_video_url && (
              <video src={job.final_video_url} className="w-full h-full object-cover" muted loop playsInline />
            )}
            <div className="play-overlay">
              <div className="play-btn">
                <svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>
              </div>
            </div>
          </div>
          <div className="video-info">
            <div className="video-name">{influencerMap.get(job.influencer_id ?? '')?.name ?? 'Unknown'} — {job.campaign_name ?? 'Single'}</div>
            <div className="video-date">{formatDate(job.created_at ?? '')}</div>
          </div>
        </div>
      ))}
    </div>
  </div>
);
```

---

## 6. Create Page (`/create`)

The Create page is redesigned into a two-column layout. The left panel is the configuration sidebar; the right panel is the workspace.

**File:** `frontend/src/app/create/page.tsx`

**Action:** Replace the JSX return value. Preserve all existing state and data fetching logic. The key structural change is wrapping everything in `create-layout`, with a `config-panel` on the left and `workspace` on the right.

### 6.1. Left Config Panel Structure

The config panel contains the following sections in order:

1. **Panel title:** "New Video" (15px, 800 weight, `var(--text-1)`)
2. **Progress section** (`config-section`): Three `config-step` items with `step-num` badges (done/active/inactive states).
3. **Product section** (`config-section`): A `config-label` with inline `prod-filter-pills` (All / Physical / Digital). Below it, a `product-selector-grid` (3 columns) of `prod-card` items. Each card shows the product image (or a placeholder SVG icon — **no emoji**), name, and type. An "Add New" card at the end links to `/products`.
4. **Number of Videos section** (`config-section`): A `video-count-row` with `count-btn` (minus), `count-display`, `count-btn` (plus), and `count-label`. Below it, a `count-hint`.
5. **Duration section** (`config-section`): `pill-group` with "15s" and "30s" pills.
6. **Script section** (`config-section`): `pill-group` with "AI Generate", "Custom", "From Library" pills. A `config-textarea` below for the script input.
7. **Cinematic Shot section** (`config-section`): `pill-group` with "Include Shot" / "No Shot". When "Include Shot" is selected, a second `pill-group` appears with shot style options (Hero, Macro Detail, Floating, Moody).
8. **Generation Summary box** (`.gen-summary`): Shows Influencer, Type, Cinematic Shot, and total Credits.
9. **Generate button** (`.btn-generate`): Full-width, with a `.credit-cost` badge.

### 6.2. Right Workspace Structure

The workspace contains:

1. **How It Works panel** (`.how-it-works`): Title "Create a Studio-Quality Video", subtitle, and a 3-step grid (`.hiw-steps`). Each step has a numbered badge, a visual preview area, a label, and a description. **No emoji in step images** — use gradient backgrounds with descriptive text.
2. **Section title:** "Choose Your AI Influencer"
3. **Influencer grid** (`.influencer-grid`, 4 columns): Each `.inf-card` shows the influencer's photo as a background image on `.inf-thumb`. The name overlays the bottom. A `.inf-check` badge appears on selection. **Influencer images come from the database `image_url` field.**

### 6.3. JSX Structure

```tsx
return (
  <div className="create-layout">
    {/* Left Config Panel */}
    <div className="config-panel">
      <div style={{fontSize:'15px', fontWeight:800, color:'var(--text-1)', marginBottom:'20px', letterSpacing:'-0.3px'}}>
        New Video
      </div>

      {/* Progress */}
      <div className="config-section">
        <div className="config-label">Progress</div>
        <div className="config-step">
          <div className={`step-num ${selectedInfluencer ? 'done' : ''}`}>
            {selectedInfluencer ? <svg viewBox="0 0 24 24" style={{width:10,height:10,stroke:'white',fill:'none',strokeWidth:3}}><polyline points="20 6 9 17 4 12"/></svg> : '1'}
          </div>
          <div className="step-text">Select Influencer</div>
        </div>
        <div className="config-step">
          <div className={`step-num ${selectedInfluencer && selectedProduct ? '' : 'inactive'}`}>2</div>
          <div className="step-text">Configure Video</div>
        </div>
        <div className="config-step">
          <div className="step-num inactive">3</div>
          <div className="step-text">Review and Generate</div>
        </div>
      </div>

      {/* Product Selector */}
      <div className="config-section">
        <div className="config-label">
          <span>Product</span>
          <div className="prod-filter-pills">
            {['all','physical','digital'].map(f => (
              <span key={f} className={`prod-filter ${productFilter === f ? 'active' : ''}`} onClick={() => setProductFilter(f)}>
                {f.charAt(0).toUpperCase() + f.slice(1)}
              </span>
            ))}
          </div>
        </div>
        <div className="product-selector-grid">
          {filteredProducts.map(p => (
            <div key={p.id} className={`prod-card ${selectedProduct === p.id ? 'selected' : ''}`} onClick={() => setSelectedProduct(p.id)}>
              <div className="prod-thumb" style={p.image_url ? {backgroundImage:`url(${p.image_url})`} : {}}>
                {!p.image_url && <svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>}
              </div>
              <div className="prod-card-name">{p.name}</div>
              <div className="prod-card-type">{p.type ?? 'Product'}</div>
            </div>
          ))}
          <div className="prod-card prod-card-add" onClick={() => router.push('/products')}>
            <div className="prod-thumb" style={{background:'var(--blue-light)'}}>
              <svg style={{width:20,height:20,stroke:'var(--blue)',fill:'none',strokeWidth:2}} viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            </div>
            <div className="prod-card-name" style={{color:'var(--blue)'}}>Add New</div>
            <div className="prod-card-type">&nbsp;</div>
          </div>
        </div>
      </div>

      {/* Video Count */}
      <div className="config-section">
        <div className="config-label">Number of Videos</div>
        <div className="video-count-row">
          <button className="count-btn" onClick={() => setVideoCount(c => Math.max(1, c - 1))}>−</button>
          <div className="count-display">{videoCount}</div>
          <button className="count-btn" onClick={() => setVideoCount(c => Math.min(50, c + 1))}>+</button>
          <div className={`count-label ${videoCount > 1 ? 'campaign' : ''}`}>
            {videoCount === 1 ? 'Single Video' : `Campaign (${videoCount} videos)`}
          </div>
        </div>
        <div className={`count-hint ${videoCount > 1 ? 'campaign' : ''}`}>
          {videoCount === 1 ? 'Add 2+ videos to launch a campaign' : `This will launch a campaign with ${videoCount} videos`}
        </div>
      </div>

      {/* Duration */}
      <div className="config-section">
        <div className="config-label">Duration</div>
        <div className="pill-group">
          {[15, 30].map(d => (
            <div key={d} className={`pill ${duration === d ? 'selected' : ''}`} onClick={() => setDuration(d)}>{d}s</div>
          ))}
        </div>
      </div>

      {/* Script */}
      <div className="config-section">
        <div className="config-label">Script</div>
        <div className="pill-group">
          {['AI Generate','Custom','From Library'].map(s => (
            <div key={s} className={`pill ${scriptMode === s ? 'selected' : ''}`} onClick={() => setScriptMode(s)}>{s}</div>
          ))}
        </div>
        <textarea className="config-textarea" rows={3} placeholder="Describe your product or paste a custom script..." value={scriptText} onChange={e => setScriptText(e.target.value)} />
      </div>

      {/* Cinematic Shot */}
      <div className="config-section">
        <div className="config-label">Cinematic Shot</div>
        <div className="pill-group">
          {['Include Shot','No Shot'].map(s => (
            <div key={s} className={`pill ${cinematicMode === s ? 'selected' : ''}`} onClick={() => setCinematicMode(s)}>{s}</div>
          ))}
        </div>
        {cinematicMode === 'Include Shot' && (
          <div className="pill-group" style={{marginTop:'6px'}}>
            {['Hero','Macro Detail','Floating','Moody'].map(s => (
              <div key={s} className={`pill ${shotStyle === s ? 'selected' : ''}`} onClick={() => setShotStyle(s)}>{s}</div>
            ))}
          </div>
        )}
      </div>

      {/* Generation Summary */}
      <div className="gen-summary">
        <div className="gen-summary-title">Generation Summary</div>
        <div className="gen-summary-row"><span>Influencer</span><span>{selectedInfluencerName ?? '—'}</span></div>
        <div className="gen-summary-row"><span>Type</span><span>{duration}s Video</span></div>
        {cinematicMode === 'Include Shot' && <div className="gen-summary-row"><span>Cinematic Shot</span><span>{shotStyle}</span></div>}
        <div className="gen-summary-divider" />
        <div className="gen-summary-total"><span>Credits</span><span>{totalCredits} cr</span></div>
      </div>

      <button className="btn-generate" onClick={handleSubmit} disabled={submitting || !selectedInfluencer}>
        <svg style={{width:16,height:16,stroke:'white',fill:'none',strokeWidth:2}} viewBox="0 0 24 24"><polygon points="13,2 3,14 12,14 11,22 21,10 12,10"/></svg>
        {submitting ? 'Generating...' : 'Generate Video'}
        <span className="credit-cost">{totalCredits} cr</span>
      </button>
    </div>

    {/* Right Workspace */}
    <div className="workspace">
      <div className="how-it-works">
        <div className="hiw-title">Create a <span>Studio-Quality</span> Video</div>
        <div className="hiw-sub">Select an AI influencer below, configure your video, and generate in seconds.</div>
        <div className="hiw-steps">
          {[
            {num:1, label:'Select Influencer', desc:'Pick from your AI influencer roster', bg:'grad-1', text:'Choose your AI Influencer'},
            {num:2, label:'Configure', desc:'Set type, duration, and script', bg:'grad-2', text:'Configure video type and script'},
            {num:3, label:'Generate', desc:'Your video is ready in approximately 2 minutes', bg:'grad-4', text:'Generate and download'},
          ].map(step => (
            <div key={step.num} className="hiw-step">
              <div className="hiw-step-num">{step.num}</div>
              <div className={`hiw-step-img ${step.bg}`}>
                <div style={{textAlign:'center',color:'rgba(255,255,255,0.7)',fontSize:'12px',padding:'8px'}}>{step.text}</div>
              </div>
              <div className="hiw-step-label">{step.label}</div>
              <div className="hiw-step-desc">{step.desc}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="section-title">Choose Your AI Influencer</div>
      <div className="influencer-grid">
        {influencers.map(inf => (
          <div key={inf.id} className={`inf-card ${selectedInfluencer === inf.id ? 'selected' : ''}`} onClick={() => setSelectedInfluencer(inf.id)}>
            <div className="inf-thumb" style={inf.image_url ? {backgroundImage:`url(${inf.image_url})`} : {background:'linear-gradient(160deg,#1a1a2e,#0f3460)'}}>
              <div className="inf-check">
                <svg viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"/></svg>
              </div>
              <span className="inf-name">{inf.name}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  </div>
);
```

---

## 7. Videos / Library Page (`/library`)

The library page is repurposed to show only generated videos.

**File:** `frontend/src/app/library/page.tsx`

**Action:** Replace the JSX return value. Keep existing data fetching. The page now uses the `content-area` wrapper and the `videos-grid` layout.

```tsx
return (
  <div className="content-area">
    <div className="page-header">
      <h1>Videos</h1>
      <p>All your generated UGC videos in one place.</p>
    </div>

    <div className="asset-toolbar">
      <div className="asset-toolbar-left">
        <div className="search-box">
          <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input type="text" placeholder="Search videos..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="filter-select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All Status</option>
          <option value="success">Completed</option>
          <option value="processing">Processing</option>
          <option value="pending">Queued</option>
          <option value="failed">Failed</option>
        </select>
        <select className="filter-select" value={sortOrder} onChange={e => setSortOrder(e.target.value)}>
          <option value="newest">Newest First</option>
          <option value="oldest">Oldest First</option>
        </select>
      </div>
      <Link href="/create" className="btn-create">
        <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        Create Video
      </Link>
    </div>

    {filteredJobs.length === 0 ? (
      <div className="empty-state">
        <div className="empty-icon">
          <svg viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/></svg>
        </div>
        <div className="empty-title">No videos yet</div>
        <div className="empty-sub">Create your first video to get started.</div>
        <Link href="/create" className="btn-primary">Create Video</Link>
      </div>
    ) : (
      <div className="videos-grid">
        {filteredJobs.map((job, i) => {
          const statusClass = job.status === 'success' ? 'done' : job.status === 'processing' ? 'processing' : job.status === 'pending' ? 'queued' : 'failed';
          const statusLabel = job.status === 'success' ? 'Done' : job.status === 'processing' ? 'Processing' : job.status === 'pending' ? 'Queued' : 'Failed';
          return (
            <div key={job.id} className="vcard">
              <div className={`vcard-thumb grad-${(i % 5) + 1}`} style={job.final_video_url ? {} : {}}>
                {job.final_video_url && (
                  <video src={job.final_video_url} className="w-full h-full object-cover" muted loop playsInline />
                )}
                <span className={`vcard-badge ${statusClass}`}>{statusLabel}</span>
              </div>
              <div className="vcard-info">
                <div className="vcard-name">{influencerMap.get(job.influencer_id ?? '')?.name ?? 'Unknown'} — {job.campaign_name ?? 'Single'}</div>
                <div className="vcard-meta">{formatDate(job.created_at ?? '')}</div>
              </div>
              <div className="vcard-actions">
                {job.final_video_url ? (
                  <>
                    <button className="vcard-action-btn primary" onClick={() => window.open(job.final_video_url)}>
                      <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                      Save
                    </button>
                    <button className="vcard-action-btn secondary">
                      <svg viewBox="0 0 24 24"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
                      Share
                    </button>
                  </>
                ) : (
                  <button className="vcard-action-btn secondary" style={{flex:1}} disabled>
                    {statusLabel}...
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    )}
  </div>
);
```

---

## 8. Influencers Page (`/influencers`)

**Action:** Create a new file `frontend/src/app/influencers/page.tsx`. This page replaces the influencer management that was previously embedded in the `/library` page.

```tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/utils';
import { Influencer } from '@/lib/types';
import { InfluencerModal } from '@/app/library/InfluencerModal';

export default function InfluencersPage() {
  const [influencers, setInfluencers] = useState<Influencer[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [genderFilter, setGenderFilter] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Influencer | null>(null);

  const fetchInfluencers = useCallback(async () => {
    try {
      const data = await apiFetch<Influencer[]>('/influencers');
      setInfluencers(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchInfluencers(); }, [fetchInfluencers]);

  const filtered = influencers.filter(inf =>
    inf.name.toLowerCase().includes(search.toLowerCase()) &&
    (genderFilter === '' || inf.gender === genderFilter)
  );

  return (
    <div className="content-area">
      <div className="page-header">
        <h1>AI Influencers</h1>
        <p>Your roster of AI-powered influencer profiles.</p>
      </div>

      <div className="asset-toolbar">
        <div className="asset-toolbar-left">
          <div className="search-box">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" placeholder="Search influencers..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="filter-select" value={genderFilter} onChange={e => setGenderFilter(e.target.value)}>
            <option value="">All Types</option>
            <option value="Female">Female</option>
            <option value="Male">Male</option>
          </select>
        </div>
        <button className="btn-create" onClick={() => { setEditTarget(null); setModalOpen(true); }}>
          <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New Influencer
        </button>
      </div>

      {loading ? (
        <div className="empty-state"><div className="empty-title">Loading influencers...</div></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon"><svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg></div>
          <div className="empty-title">No influencers found</div>
          <div className="empty-sub">Add your first AI influencer to get started.</div>
          <button className="btn-primary" onClick={() => { setEditTarget(null); setModalOpen(true); }}>Add Influencer</button>
        </div>
      ) : (
        <div className="influencers-grid">
          {filtered.map(inf => (
            <div key={inf.id} className="icard" onClick={() => { setEditTarget(inf); setModalOpen(true); }}>
              <div className="icard-thumb" style={inf.image_url ? {backgroundImage:`url(${inf.image_url})`} : {background:'linear-gradient(160deg,#1a1a2e,#0f3460)'}}>
                <span className="icard-name">{inf.name}</span>
              </div>
              <div className="icard-info">
                <div className="icard-tags">
                  {inf.gender && <span className="icard-tag">{inf.gender}</span>}
                  {inf.style && <span className="icard-tag">{inf.style}</span>}
                </div>
                <div className="icard-btn">
                  <svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>
                  Use in Video
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <InfluencerModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        initialData={editTarget}
        onSave={() => { fetchInfluencers(); setModalOpen(false); }}
      />
    </div>
  );
}
```

---

## 9. InfluencerModal Component

The existing `InfluencerModal.tsx` needs minor updates to replace emoji with SVG icons and update button styles to match the new design system.

**File:** `frontend/src/app/library/InfluencerModal.tsx`

**Action:** Apply the following targeted changes.

| Location | Current | Replacement |
|---|---|---|
| Profile image preview placeholder | `<span className="text-2xl text-slate-600">👤</span>` | `<svg className="w-8 h-8" viewBox="0 0 24 24" style={{stroke:'var(--text-3)',fill:'none',strokeWidth:1.5}}><circle cx="12" cy="8" r="4"/><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/></svg>` |
| Gender buttons (Male/Female) | `{g === 'Male' ? '♂️' : '♀️'} {g}` | `{g}` (text only
, no gender symbol) |
| Cancel button | `className="px-4 py-2 rounded-lg bg-slate-700 text-slate-200 hover:bg-slate-600 font-medium text-sm"` | `className="btn-secondary"` |
| Save button | `className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-medium text-sm"` | `className="btn-primary"` |
| Modal container | `className="bg-slate-800 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden"` | `className="modal-box"` |
| Modal header | `className="flex items-center justify-between p-5 border-b border-slate-700"` | `className="modal-header"` |
| Modal header title | `className="text-lg font-bold text-white"` | `className=""` (inherits from `.modal-header h3`) |
| Modal body | `className="p-5 space-y-4 max-h-[70vh] overflow-y-auto"` | `className="modal-body"` |
| Modal footer | `className="flex justify-end gap-3 p-5 border-t border-slate-700"` | `className="modal-footer"` |
| Input fields | `className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white text-sm..."` | `className="input-field"` |
| Labels | `className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1"` | `className="form-label"` |

---

## 10. Scripts Page (`/scripts`)

**Action:** Create a new file `frontend/src/app/scripts/page.tsx`.

```tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiFetch } from '@/lib/utils';

interface Script {
  id: string;
  name: string;
  content: string;
  product_name?: string;
  video_type?: string;
  created_at?: string;
}

export default function ScriptsPage() {
  const [scripts, setScripts] = useState<Script[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const fetchScripts = useCallback(async () => {
    try {
      const data = await apiFetch<Script[]>('/scripts');
      setScripts(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchScripts(); }, [fetchScripts]);

  const filtered = scripts.filter(s =>
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    (s.content ?? '').toLowerCase().includes(search.toLowerCase())
  );

  const formatDate = (d: string) => new Date(d).toLocaleDateString('en-US', { month:'numeric', day:'numeric', year:'numeric' });

  return (
    <div className="content-area">
      <div className="page-header">
        <h1>Scripts</h1>
        <p>Your library of UGC video scripts.</p>
      </div>

      <div className="asset-toolbar">
        <div className="asset-toolbar-left">
          <div className="search-box">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" placeholder="Search scripts..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>
        <button className="btn-create">
          <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New Script
        </button>
      </div>

      {loading ? (
        <div className="empty-state"><div className="empty-title">Loading scripts...</div></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
          </div>
          <div className="empty-title">No scripts yet</div>
          <div className="empty-sub">Scripts are automatically saved when you generate a video with AI Generate mode.</div>
        </div>
      ) : (
        <div className="scripts-list">
          {filtered.map(script => (
            <div key={script.id} className="script-card">
              <div className="script-icon">
                <svg viewBox="0 0 24 24"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
              </div>
              <div className="script-body">
                <div className="script-name">{script.name}</div>
                <div className="script-preview">"{script.content?.slice(0, 120)}..."</div>
                <div className="script-meta">
                  {script.video_type && <span>{script.video_type}</span>}
                  {script.product_name && <span>{script.product_name}</span>}
                  {script.created_at && <span>{formatDate(script.created_at)}</span>}
                </div>
              </div>
              <div className="script-actions">
                <button className="script-action-btn primary">Use</button>
                <button className="script-action-btn ghost">Edit</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## 11. App Clips Page (`/app-clips`)

**Action:** Create a new file `frontend/src/app/app-clips/page.tsx`. This page surfaces clips optimised for app store previews and ads. It uses the same API endpoint as the library but filters for `clip` type, or uses a dedicated `/clips` endpoint if available.

```tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/utils';

interface Clip {
  id: string;
  name: string;
  aspect_ratio?: string;
  duration?: number;
  created_at?: string;
  thumbnail_url?: string;
  video_url?: string;
  campaign_name?: string;
}

export default function AppClipsPage() {
  const [clips, setClips] = useState<Clip[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');

  const fetchClips = useCallback(async () => {
    try {
      // Use the clips endpoint; fall back to jobs filtered by type
      const data = await apiFetch<Clip[]>('/clips');
      setClips(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchClips(); }, [fetchClips]);

  const filtered = clips.filter(c =>
    c.name.toLowerCase().includes(search.toLowerCase())
  );

  const formatDate = (d: string) => new Date(d).toLocaleDateString('en-US', { month:'numeric', day:'numeric', year:'numeric' });

  const GRAD_CLASSES = ['grad-1','grad-2','grad-3','grad-4','grad-5'];

  return (
    <div className="content-area">
      <div className="page-header">
        <h1>App Clips</h1>
        <p>Short-form clips optimised for app store previews and ads.</p>
      </div>

      <div className="asset-toolbar">
        <div className="asset-toolbar-left">
          <div className="search-box">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" placeholder="Search app clips..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
        </div>
        <Link href="/create" className="btn-create">
          <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          New App Clip
        </Link>
      </div>

      {loading ? (
        <div className="empty-state"><div className="empty-title">Loading clips...</div></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            <svg viewBox="0 0 24 24"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
          </div>
          <div className="empty-title">No app clips yet</div>
          <div className="empty-sub">App clips are short-form versions of your videos optimised for app store previews.</div>
          <Link href="/create" className="btn-primary">Create Video</Link>
        </div>
      ) : (
        <div className="clips-grid">
          {filtered.map((clip, i) => (
            <div key={clip.id} className="clip-card">
              <div
                className={`clip-thumb ${GRAD_CLASSES[i % GRAD_CLASSES.length]}`}
                style={clip.thumbnail_url ? {backgroundImage:`url(${clip.thumbnail_url})`} : {}}
              >
                {/* Phone / clip icon as visual indicator — no emoji */}
                {!clip.thumbnail_url && (
                  <svg viewBox="0 0 24 24"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>
                )}
              </div>
              <div className="clip-info">
                <div className="clip-name">{clip.name}</div>
                <div className="clip-meta">
                  {clip.aspect_ratio && `${clip.aspect_ratio} · `}
                  {clip.duration && `${clip.duration}s · `}
                  {clip.created_at && formatDate(clip.created_at)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## 12. Products Page (`/products`)

The existing products page (currently at `/library` under a tab) is moved to its own route.

**Action:** Create a new file `frontend/src/app/products/page.tsx`. Migrate the product management logic from `ProductUpload.tsx` and `ProductShotsGallery.tsx` into this page, or keep them as sub-components.

```tsx
'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/utils';
import { Product } from '@/lib/types';

export default function ProductsPage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('');

  const fetchProducts = useCallback(async () => {
    try {
      const data = await apiFetch<Product[]>('/products');
      setProducts(data);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => { fetchProducts(); }, [fetchProducts]);

  const filtered = products.filter(p =>
    p.name.toLowerCase().includes(search.toLowerCase()) &&
    (typeFilter === '' || (p.type ?? '').toLowerCase() === typeFilter.toLowerCase())
  );

  return (
    <div className="content-area">
      <div className="page-header">
        <h1>Products</h1>
        <p>Manage the products used in your UGC campaigns.</p>
      </div>

      <div className="asset-toolbar">
        <div className="asset-toolbar-left">
          <div className="search-box">
            <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <input type="text" placeholder="Search products..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select className="filter-select" value={typeFilter} onChange={e => setTypeFilter(e.target.value)}>
            <option value="">All Types</option>
            <option value="physical">Physical</option>
            <option value="digital">Digital</option>
          </select>
        </div>
        <button className="btn-create" onClick={() => {/* open product upload modal */}}>
          <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Add Product
        </button>
      </div>

      {loading ? (
        <div className="empty-state"><div className="empty-title">Loading products...</div></div>
      ) : filtered.length === 0 ? (
        <div className="empty-state">
          <div className="empty-icon">
            <svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
          </div>
          <div className="empty-title">No products yet</div>
          <div className="empty-sub">Add a product to start creating UGC videos.</div>
          <button className="btn-primary">Add Product</button>
        </div>
      ) : (
        <div className="products-grid">
          {filtered.map(product => (
            <div key={product.id} className="product-card">
              <div className="product-img">
                {product.image_url ? (
                  <img src={product.image_url} alt={product.name} />
                ) : (
                  <svg viewBox="0 0 24 24"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/></svg>
                )}
              </div>
              <div className="product-info">
                <div className="product-name">{product.name}</div>
                <div className="product-meta">{product.type ?? 'Product'} · {product.job_count ?? 0} videos generated</div>
              </div>
              <div className="product-actions">
                <Link href="/cinematic" className="product-btn primary">
                  <svg viewBox="0 0 24 24"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/></svg>
                  Cinematic
                </Link>
                <Link href="/create" className="product-btn secondary">
                  <svg viewBox="0 0 24 24"><polygon points="5,3 19,12 5,21"/></svg>
                  Create
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

---

## 13. Cinematic Shots Page (`/cinematic`)

This is a new page. It provides a two-column layout: a left config panel for uploading a product image and selecting a shot style, and a right workspace for previewing and generating the cinematic shot.

**Action:** Create a new file `frontend/src/app/cinematic/page.tsx`.

### 13.1. Shot Style Options

The following shot styles are available. Each is represented by an SVG icon and a text label — **no emoji**.

| Style | Icon SVG Path Description |
|---|---|
| Hero | Camera/film icon: `<path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/>` |
| Macro Detail | Zoom/magnify icon: `<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>` |
| Floating | Layers/stack icon: `<polygon points="12 2 2 7 12 12 22 7"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>` |
| Moody | Moon/atmosphere icon: `<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>` |

### 13.2. Full Component

```tsx
'use client';

import { useState, useRef, useCallback } from 'react';
import { apiFetch } from '@/lib/utils';

const SHOT_STYLES = [
  { key: 'hero', label: 'Hero', icon: <svg viewBox="0 0 24 24"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg> },
  { key: 'macro', label: 'Macro Detail', icon: <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> },
  { key: 'floating', label: 'Floating', icon: <svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg> },
  { key: 'moody', label: 'Moody', icon: <svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg> },
];

export default function CinematicPage() {
  const [selectedStyle, setSelectedStyle] = useState('hero');
  const [uploadedImage, setUploadedImage] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [prompt, setPrompt] = useState('');
  const [generating, setGenerating] = useState(false);
  const [generatedShot, setGeneratedShot] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadedFile(file);
    const reader = new FileReader();
    reader.onload = ev => setUploadedImage(ev.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const file = e.dataTransfer.files?.[0];
    if (!file) return;
    setUploadedFile(file);
    const reader = new FileReader();
    reader.onload = ev => setUploadedImage(ev.target?.result as string);
    reader.readAsDataURL(file);
  }, []);

  const handleGenerate = async () => {
    if (!uploadedFile) return;
    setGenerating(true);
    setError(null);
    try {
      const formData = new FormData();
      formData.append('image', uploadedFile);
      formData.append('style', selectedStyle);
      formData.append('prompt', prompt);
      const result = await apiFetch<{url: string}>('/cinematic/generate', {
        method: 'POST',
        body: formData,
      });
      setGeneratedShot(result.url);
    } catch (e: any) {
      setError(e.message ?? 'Generation failed. Please try again.');
    }
    setGenerating(false);
  };

  return (
    <div className="cinematic-layout">
      {/* Left Config Panel */}
      <div className="config-panel">
        <div style={{fontSize:'15px', fontWeight:800, color:'var(--text-1)', marginBottom:'20px', letterSpacing:'-0.3px'}}>
          Cinematic Shots
        </div>

        {/* Product Image Upload */}
        <div className="config-section">
          <div className="config-label">Product Image</div>
          <div
            className="upload-zone"
            onClick={() => fileInputRef.current?.click()}
            onDrop={handleDrop}
            onDragOver={e => e.preventDefault()}
          >
            {uploadedImage ? (
              <img src={uploadedImage} alt="Product" style={{width:'100%', borderRadius:'var(--radius-sm)', objectFit:'cover', maxHeight:'160px'}} />
            ) : (
              <>
                <svg viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                <p>Drop image here or <span>browse</span></p>
              </>
            )}
          </div>
          <input ref={fileInputRef} type="file" accept="image/*" style={{display:'none'}} onChange={handleFileChange} />
        </div>

        {/* Shot Style Selector */}
        <div className="config-section">
          <div className="config-label">Shot Style</div>
          <div className="shot-type-grid">
            {SHOT_STYLES.map(style => (
              <div
                key={style.key}
                className={`shot-type-card ${selectedStyle === style.key ? 'selected' : ''}`}
                onClick={() => setSelectedStyle(style.key)}
              >
                <div className="shot-icon">{style.icon}</div>
                <div className="shot-label">{style.label}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Prompt */}
        <div className="config-section">
          <div className="config-label">Additional Prompt (Optional)</div>
          <textarea
            className="config-textarea"
            rows={3}
            placeholder="Describe the scene, lighting, or mood..."
            value={prompt}
            onChange={e => setPrompt(e.target.value)}
          />
        </div>

        {error && (
          <div style={{background:'rgba(239,68,68,0.1)', border:'1px solid rgba(239,68,68,0.3)', borderRadius:'var(--radius-sm)', padding:'10px 12px', marginBottom:'12px', fontSize:'12px', color:'var(--red)'}}>
            {error}
          </div>
        )}

        <button
          className="btn-generate"
          onClick={handleGenerate}
          disabled={generating || !uploadedFile}
        >
          <svg style={{width:16,height:16,stroke:'white',fill:'none',strokeWidth:2}} viewBox="0 0 24 24"><polygon points="13,2 3,14 12,14 11,22 21,10 12,10"/></svg>
          {generating ? 'Generating...' : 'Generate Shot'}
          <span className="credit-cost">50 cr</span>
        </button>
      </div>

      {/* Right Workspace */}
      <div className="cinematic-workspace">
        {generatedShot ? (
          <>
            <div className="shot-preview">
              <img src={generatedShot} alt="Generated cinematic shot" style={{width:'100%', height:'100%', objectFit:'cover', borderRadius:'var(--radius)'}} />
            </div>
            <div style={{display:'flex', gap:'10px'}}>
              <button className="btn-primary" onClick={() => window.open(generatedShot)}>
                <svg viewBox="0 0 24 24" style={{width:14,height:14,stroke:'white',fill:'none',strokeWidth:2}}><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                Download
              </button>
              <button className="btn-secondary" onClick={() => { setGeneratedShot(null); setUploadedImage(null); setUploadedFile(null); }}>
                Generate Another
              </button>
            </div>
          </>
        ) : (
          <div className="empty-state">
            <div className="shot-preview" style={{background:'linear-gradient(135deg, #eef2ff 0%, #f8f9ff 100%)'}}>
              <div className="shot-preview-label">
                <svg viewBox="0 0 24 24" style={{width:40,height:40,stroke:'var(--text-3)',fill:'none',strokeWidth:1.25,display:'block',margin:'0 auto 12px'}}><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/><polyline points="10 17 15 12 10 7"/><line x1="15" y1="12" x2="3" y2="12"/></svg>
                Upload a product image and select a shot style to generate a cinematic product shot.
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
```

---

## 14. Activity Page (`/activity`)

**File:** `frontend/src/app/activity/page.tsx`

**Action:** Replace the JSX return value. Keep all existing data fetching and filtering logic.

```tsx
return (
  <div className="content-area">
    <div className="page-header">
      <h1>Activity</h1>
      <p>Monitor all generation jobs, track campaign progress, and view credit usage.</p>
    </div>

    <div className="asset-toolbar">
      <div className="asset-toolbar-left">
        <div className="search-box">
          <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input type="text" placeholder="Search jobs..." value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <select className="filter-select" value={statusFilter} onChange={e => setStatusFilter(e.target.value)}>
          <option value="">All Status</option>
          <option value="success">Completed</option>
          <option value="processing">Processing</option>
          <option value="pending">Queued</option>
          <option value="failed">Failed</option>
        </select>
      </div>
    </div>

    {filteredJobs.length === 0 ? (
      <div className="empty-state">
        <div className="empty-icon">
          <svg viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
        </div>
        <div className="empty-title">No activity yet</div>
        <div className="empty-sub">Your generation jobs will appear here.</div>
      </div>
    ) : (
      <div className="activity-table">
        <div className="table-header">
          <div className="th">Job</div>
          <div className="th">Campaign</div>
          <div className="th">Influencer</div>
          <div className="th">Status</div>
          <div className="th">Cost</div>
          <div className="th">Actions</div>
        </div>
        {filteredJobs.map(job => {
          const statusClass = job.status === 'success' ? 'done' : job.status === 'processing' ? 'active' : job.status === 'pending' ? 'pending' : 'failed';
          const statusLabel = job.status === 'success' ? 'Completed' : job.status === 'processing' ? 'Processing' : job.status === 'pending' ? 'Queued' : 'Failed';
          return (
            <div key={job.id} className="table-row">
              <div className="td">
                <div className="job-name-cell">
                  <div className="job-icon">
                    <svg viewBox="0 0 24 24"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2"/></svg>
                  </div>
                  <div>
                    <div className="job-name">{influencerMap.get(job.influencer_id ?? '')?.name ?? 'Unknown'} — {job.campaign_name ?? 'Single'}</div>
                    <div className="job-id">{job.id.slice(0, 12)}...</div>
                  </div>
                </div>
              </div>
              <div className="td">
                {job.campaign_name ? <span className="campaign-tag">{job.campaign_name}</span> : <span className="td muted">—</span>}
              </div>
              <div className="td muted">{influencerMap.get(job.influencer_id ?? '')?.name ?? '—'}</div>
              <div className="td"><span className={`status-pill ${statusClass}`}>{statusLabel}</span></div>
              <div className="td muted">{job.cost_credits ? `${job.cost_credits} cr` : '—'}</div>
              <div className="td">
                <div className="row-actions">
                  {job.final_video_url && (
                    <button className="row-btn primary" onClick={() => window.open(job.final_video_url)}>View</button>
                  )}
                  {(job.status === 'pending' || job.status === 'processing') && (
                    <button className="row-btn ghost" onClick={() => handleCancel(job.id)}>Cancel</button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    )}
  </div>
);
```

---

## 15. Manage Page (`/manage`)

The existing Manage page is a settings/admin area. It keeps its current functionality but is updated to match the new design system.

**File:** `frontend/src/app/manage/page.tsx`

**Action:** Replace the JSX return value. Keep all existing data fetching and mutation logic.

```tsx
return (
  <div className="content-area">
    <div className="page-header">
      <h1>Manage</h1>
      <p>Configure your workspace, API keys, and account settings.</p>
    </div>

    {/* Settings sections are rendered as cards */}
    <div style={{display:'flex', flexDirection:'column', gap:'20px'}}>

      {/* API Configuration */}
      <div className="tracker-card">
        <div className="section-title">API Configuration</div>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:'16px'}}>
          <div className="form-group">
            <label className="form-label">Runway API Key</label>
            <input type="password" className="input-field" value={runwayKey} onChange={e => setRunwayKey(e.target.value)} placeholder="sk-..." />
          </div>
          <div className="form-group">
            <label className="form-label">OpenAI API Key</label>
            <input type="password" className="input-field" value={openaiKey} onChange={e => setOpenaiKey(e.target.value)} placeholder="sk-..." />
          </div>
          <div className="form-group">
            <label className="form-label">ElevenLabs API Key</label>
            <input type="password" className="input-field" value={elevenLabsKey} onChange={e => setElevenLabsKey(e.target.value)} placeholder="..." />
          </div>
          <div className="form-group">
            <label className="form-label">AWS S3 Bucket</label>
            <input type="text" className="input-field" value={s3Bucket} onChange={e => setS3Bucket(e.target.value)} placeholder="my-bucket" />
          </div>
        </div>
        <div style={{display:'flex', justifyContent:'flex-end', marginTop:'8px'}}>
          <button className="btn-primary" onClick={handleSaveConfig}>Save Configuration</button>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="tracker-card" style={{borderColor:'rgba(239,68,68,0.25)'}}>
        <div className="section-title" style={{color:'var(--red)'}}>Danger Zone</div>
        <p style={{fontSize:'13px', color:'var(--text-2)', marginBottom:'16px'}}>
          These actions are irreversible. Please proceed with caution.
        </p>
        <div style={{display:'flex', gap:'10px'}}>
          <button className="btn-secondary" style={{borderColor:'rgba(239,68,68,0.3)', color:'var(--red)'}} onClick={handleClearJobs}>
            Clear All Jobs
          </button>
          <button className="btn-secondary" style={{borderColor:'rgba(239,68,68,0.3)', color:'var(--red)'}} onClick={handleResetWorkspace}>
            Reset Workspace
          </button>
        </div>
      </div>

    </div>
  </div>
);
```

---

## 16. GenerateShotModal Component

The existing `GenerateShotModal.tsx` is updated to use the new design system classes.

**File:** `frontend/src/app/library/GenerateShotModal.tsx`

**Action:** Apply the following targeted changes.

| Location | Current | Replacement |
|---|---|---|
| Modal container | `className="bg-slate-800 rounded-2xl shadow-2xl w-full max-w-lg overflow-hidden"` | `className="modal-box"` |
| Modal header | `className="flex items-center justify-between p-5 border-b border-slate-700"` | `className="modal-header"` |
| Modal body | `className="p-5 space-y-4 max-h-[70vh] overflow-y-auto"` | `className="modal-body"` |
| Modal footer | `className="flex justify-end gap-3 p-5 border-t border-slate-700"` | `className="modal-footer"` |
| Cancel button | `className="px-4 py-2 rounded-lg bg-slate-700 text-slate-200..."` | `className="btn-secondary"` |
| Generate button | `className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white..."` | `className="btn-primary"` |
| Input fields | `className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-white..."` | `className="input-field"` |
| Labels | `className="block text-xs font-semibold text-slate-400 uppercase tracking-wide mb-1"` | `className="form-label"` |
| Shot style buttons | `className="p-3 rounded-xl border-2 text-center cursor-pointer transition-all..."` | `className={`shot-type-card ${selected ? 'selected' : ''}`}` |
| Shot style icons | Any emoji (e.g. `🎬`, `🔬`, `✨`, `🌙`) | Replace with inline SVG icons as defined in Section 13.1 |

---

## 17. ProductShotsGallery Component

**File:** `frontend/src/app/library/ProductShotsGallery.tsx`

**Action:** Apply the following targeted changes.

| Location | Current | Replacement |
|---|---|---|
| Gallery container | `className="grid grid-cols-2 md:grid-cols-3 gap-4"` | `className="products-grid"` (or a 3-column grid variant) |
| Shot cards | `className="bg-slate-800 rounded-xl overflow-hidden border border-slate-700..."` | `className="product-card"` |
| Download button | `className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-500..."` | `className="product-btn primary"` |
| Empty state | Any dark-themed empty state | Use `.empty-state` structure from Section 2 |

---

## 18. Navigation Route Map

The following table documents all routes, their corresponding files, and the navigation item that links to them.

| Route | File | Nav Item | Notes |
|---|---|---|---|
| `/` | `app/page.tsx` | Studio | Dashboard |
| `/create` | `app/create/page.tsx` | Create | Also accessible via header "Create Video" button |
| `/library` | `app/library/page.tsx` | Videos | Renamed from "Library" |
| `/influencers` | `app/influencers/page.tsx` | Influencers | New dedicated page |
| `/scripts` | `app/scripts/page.tsx` | Scripts | New dedicated page |
| `/app-clips` | `app/app-clips/page.tsx` | App Clips | New page |
| `/products` | `app/products/page.tsx` | Products | New dedicated page |
| `/cinematic` | `app/cinematic/page.tsx` | — | Accessible via header "Cinematic Shots" button and Products page |
| `/activity` | `app/activity/page.tsx` | Activity | Existing page, restyled |
| `/manage` | `app/manage/page.tsx` | — | Accessible via profile dropdown "Manage Account" |

---

## 19. Shared Component: `AssetToolbar`

To reduce code duplication, the toolbar used on all asset pages can be extracted into a shared component.

**Action:** Create `frontend/src/components/ui/AssetToolbar.tsx`.

```tsx
import Link from 'next/link';

interface AssetToolbarProps {
  searchValue: string;
  onSearchChange: (v: string) => void;
  searchPlaceholder?: string;
  filters?: React.ReactNode;
  createHref?: string;
  createLabel?: string;
  onCreateClick?: () => void;
}

export function AssetToolbar({
  searchValue, onSearchChange, searchPlaceholder = 'Search...',
  filters, createHref, createLabel, onCreateClick,
}: AssetToolbarProps) {
  return (
    <div className="asset-toolbar">
      <div className="asset-toolbar-left">
        <div className="search-box">
          <svg viewBox="0 0 24 24"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={searchValue}
            onChange={e => onSearchChange(e.target.value)}
          />
        </div>
        {filters}
      </div>
      {(createHref || onCreateClick) && (
        createHref ? (
          <Link href={createHref} className="btn-create">
            <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            {createLabel ?? 'Create'}
          </Link>
        ) : (
          <button className="btn-create" onClick={onCreateClick}>
            <svg viewBox="0 0 24 24"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            {createLabel ?? 'Create'}
          </button>
        )
      )}
    </div>
  );
}
```

---

## 20. Implementation Checklist

The following checklist summarises every file that must be created or modified.

### Files to Modify

| File | Action |
|---|---|
| `frontend/src/app/globals.css` | Full replacement with new design system CSS |
| `frontend/src/app/layout.tsx` | Replace sidebar with Header component |
| `frontend/src/app/page.tsx` | Replace JSX with new dashboard layout |
| `frontend/src/app/create/page.tsx` | Replace JSX with new two-column create layout |
| `frontend/src/app/library/page.tsx` | Replace JSX with new videos grid layout |
| `frontend/src/app/activity/page.tsx` | Replace JSX with new activity table layout |
| `frontend/src/app/manage/page.tsx` | Replace JSX with new settings card layout |
| `frontend/src/app/library/InfluencerModal.tsx` | Apply targeted class and icon replacements |
| `frontend/src/app/library/GenerateShotModal.tsx` | Apply targeted class and icon replacements |
| `frontend/src/app/library/ProductShotsGallery.tsx` | Apply targeted class replacements |

### Files to Create

| File | Purpose |
|---|---|
| `frontend/src/components/layout/Header.tsx` | New horizontal navigation header |
| `frontend/src/components/ui/AssetToolbar.tsx` | Shared search and filter toolbar |
| `frontend/src/app/influencers/page.tsx` | Dedicated influencers page |
| `frontend/src/app/scripts/page.tsx` | Dedicated scripts page |
| `frontend/src/app/app-clips/page.tsx` | Dedicated app clips page |
| `frontend/src/app/products/page.tsx` | Dedicated products page |
| `frontend/src/app/cinematic/page.tsx` | New cinematic shots generation page |

### Files to Remove (after migration)

| File | Reason |
|---|---|
| Any old `Sidebar.tsx` or `sidebar.css` | Replaced by Header |
| Any old tab-based layout in `/library` | Replaced by dedicated pages |

---

## 21. Emoji Replacement Reference

All emoji used in the mockup for illustrative purposes must be replaced with inline SVG icons. The following table provides the complete mapping.

| Context | Emoji | SVG Replacement |
|---|---|---|
| Campaign tracker — beauty product | Lipstick emoji | `<svg viewBox="0 0 24 24"><path d="M12 2a7 7 0 0 1 7 7c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 7-7z"/></svg>` (location/product pin) |
| Campaign tracker — sneaker product | Sneaker emoji | `<svg viewBox="0 0 24 24"><path d="M2 12l2-2 4 4 8-8 4 4-12 12z"/></svg>` (check/tick) or use product image |
| Product cards — all products | Any emoji | Use actual `product.image_url` from database; if null, use box SVG icon |
| Influencer cards — all influencers | Any emoji | Use actual `influencer.image_url` from database; if null, use person SVG icon |
| App Clips thumbnails | Phone emoji | `<svg viewBox="0 0 24 24"><rect x="5" y="2" width="14" height="20" rx="2"/><line x1="12" y1="18" x2="12.01" y2="18"/></svg>` |
| How-it-works steps | Any emoji | Use gradient background with descriptive text |
| Shot styles | Camera, magnify, sparkle, moon emoji | See Section 13.1 for SVG replacements |
| Profile dropdown | Any emoji | Use SVG icons as defined in Header component |

---

## 22. Conclusion

This document is the complete, self-contained implementation guide for the Aitoma Studio UX/UI overhaul. Every page, component, CSS class, and interaction pattern is specified in full. The implementation team should follow the checklist in Section 20, working through each file in order, starting with the global CSS and layout files before proceeding to individual pages.

The key principles to maintain throughout implementation are:

1. **No emoji in the UI** — every visual element uses SVG icons or real asset images.
2. **No broken functionality** — all API calls, state management, and form logic from the existing codebase must be preserved and reconnected to the new JSX structures.
3. **Real assets everywhere** — influencer images, product images, and video thumbnails must come from the database; gradient fallbacks are only used when the asset URL is null.
4. **Consistent design tokens** — all colours, spacing, typography, and shadow values must reference the CSS variables defined in Section 2, never hardcoded values.
