# Aitoma Studio UGC Engine — UX/UI Overhaul Specification
### For Antigravity Implementation

---

## 1. Mission & Core Directive

This document is the single source of truth for a complete visual and UX overhaul of the Aitoma Studio UGC Engine SaaS frontend. The goal is to transform the current dark-themed, generic interface into a professional, branded creative SaaS that reflects the Aitoma Studio identity — using the brand's exact colours, logo, typography, glassmorphism system, and interaction patterns.

**The non-negotiable rule is: no existing functionality may break.** Every API call, state management hook, routing structure, and data flow must remain 100% intact. This is a **visual and UX layer replacement only**. No backend files, API endpoints, or business logic should be touched. Antigravity must analyse the current codebase first, understand what each component does functionally, and then apply the visual overhaul as a skin on top of the working engine.

---

## 2. Current State Analysis

The frontend lives at `/frontend/src/app/` and is a Next.js App Router project using TailwindCSS. The current theme is a **dark slate theme** with the following characteristics that must be replaced:

| Current Element | Current Value | Problem |
|---|---|---|
| Background | `bg-slate-950`, `bg-slate-900` | Generic dark, no brand identity |
| Sidebar | `bg-slate-900/40 backdrop-blur-2xl border-slate-800/60` | Correct glass approach but wrong colours |
| Logo | Plain text "UGC Engine" in `gradient-text` | No logo asset used |
| Cards | `bg-slate-800/40`, `bg-slate-900` | Dark, heavy, not glass |
| Text | `text-slate-400`, `text-slate-200`, `text-slate-500` | Slate palette, not brand palette |
| Icons | Emoji used in several places (👤, ✍️, 📱) | Violates brand guidelines |
| Borders | `border-slate-800`, `border-slate-700/60` | Generic grey |
| Tabs | `bg-slate-800 border-blue-500` | Partially correct but needs refinement |
| Status badges | `bg-green-500/10`, `bg-red-500/10`, `bg-blue-500/10` | Acceptable, keep |
| Page layout | `bg-slate-950` root, `bg-slate-900/40` sidebar | Must become light `#F0F4FF` base |

The overall theme must **switch from dark to light**. The brand uses a light blue-white background (`#F0F4FF`) with glass cards, not a dark slate background. The sidebar may remain slightly darker as a contrast panel, but it must use the brand's dark colour (`#070A12`) rather than slate.

---

## 3. Brand Design System (Source of Truth)

All values below are extracted from the official Aitoma Studio UX/UI Style Guide and must be applied exactly as specified.

### 3.1 Colour Palette

Replace all Tailwind slate/gray colour references with the following brand CSS custom properties. Add these to `globals.css` under `:root`:

```css
:root {
  /* Brand Core */
  --background:       220 60% 98%;   /* #F0F4FF — page background */
  --foreground:       240 11% 11%;   /* #1A1A1F — primary text */
  --primary:          217 100% 60%;  /* #337AFF — brand blue */
  --primary-hover:    217 78% 47%;   /* button hover */
  --primary-light:    217 100% 95%;  /* light blue tint */
  --secondary:        220 19% 18%;   /* dark buttons */
  --accent:           252 93% 85%;   /* #C7BBFD — purple accent */
  --accent-warm:      40 100% 50%;   /* warm orange */
  --muted:            220 14% 96%;   /* muted backgrounds */
  --card:             0 0% 100%;     /* #FFFFFF — card bg */
  --border:           220 14% 92%;   /* default borders */
  --border-strong:    216 12% 84%;   /* stronger borders */
  --success:          160 84% 39%;   /* #10B981 */
  --warning:          38 92% 50%;    /* #FFA800 */
  --destructive:      0 84% 60%;     /* error */

  /* Text Hierarchy */
  --text-primary:     240 11% 11%;   /* #1A1A1F */
  --text-secondary:   240 4% 39%;    /* #4A5568 */
  --text-muted:       217 16% 65%;   /* #94A3B8 */

  /* Sidebar Dark */
  --sidebar-bg:       225 50% 5%;    /* #070A12 */
  --sidebar-border:   220 30% 12%;
}
```

### 3.2 Gradients

Add these gradient utility classes to `globals.css`:

```css
.gradient-text {
  background: linear-gradient(135deg, hsl(210,97%,57%), hsl(260,90%,80%), hsl(252,93%,85%));
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.gradient-cta {
  background: linear-gradient(135deg, hsl(217,100%,60%), hsl(249,72%,63%));
}

.gradient-hero-bg {
  background: linear-gradient(135deg, hsl(220,100%,98%) 0%, hsl(220,100%,96%) 50%, hsl(252,100%,97%) 100%);
}

.badge-gradient {
  background: linear-gradient(90deg, #337AFF, #6B5FE4);
}
```

### 3.3 Glassmorphism System

Add these two glass utility classes to `globals.css`. They are the core visual language of the app:

```css
/* Light glass — for cards, panels, modals on the light background */
.glass {
  background: rgba(255, 255, 255, 0.60);
  backdrop-filter: blur(14px) saturate(180%);
  -webkit-backdrop-filter: blur(14px) saturate(180%);
  border: 1px solid rgba(255, 255, 255, 0.80);
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.08),
              inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.glass:hover {
  box-shadow: 0 12px 40px rgba(51, 122, 255, 0.12),
              inset 0 1px 0 rgba(255, 255, 255, 0.95);
  border-color: rgba(51, 122, 255, 0.25);
  transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

/* Dark glass — for sidebar and dark overlays */
.glass-dark {
  background: rgba(7, 10, 18, 0.85);
  backdrop-filter: blur(14px) saturate(160%);
  -webkit-backdrop-filter: blur(14px) saturate(160%);
  border: 1px solid rgba(255, 255, 255, 0.06);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.30),
              inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
```

### 3.4 Typography

The brand font is **Inter**. Ensure it is loaded in `layout.tsx`:

```tsx
import { Inter } from 'next/font/google';
const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-inter',
  weight: ['400', '500', '600', '700'],
});
```

Apply `${inter.variable} font-sans antialiased` to the `<body>` tag.

Type scale to apply via Tailwind classes:

| Role | Class Equivalent | Specs |
|---|---|---|
| Page Title (h1) | `text-4xl font-bold tracking-tight` | 40px, weight 700, ls -1.5px |
| Section Title (h2) | `text-2xl font-semibold tracking-tight` | 28px, weight 600 |
| Card Title (h3) | `text-lg font-semibold` | 20px, weight 600 |
| Body | `text-sm` or `text-base` | 14–16px, weight 400 |
| Caption | `text-xs font-medium tracking-wide` | 12px, ls 0.5px |

### 3.5 Shadows

```css
.shadow-card        { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.shadow-card-hover  { box-shadow: 0 8px 24px rgba(51,122,255,0.10); }
.shadow-glow        { box-shadow: 0 4px 16px rgba(51,122,255,0.35); }
.shadow-glow-hover  { box-shadow: 0 6px 24px rgba(51,122,255,0.45); }
```

### 3.6 Border Radius

| Element | Radius |
|---|---|
| Cards | `rounded-2xl` (16px) or `rounded-3xl` (24px) for large modals |
| Buttons | `rounded-xl` (12px) |
| Badges / Pills | `rounded-full` (9999px) |
| Input fields | `rounded-xl` (12px) |
| Icon containers | `rounded-xl` (14px) |

### 3.7 Animations

Add to `globals.css`:

```css
@keyframes reveal {
  from { opacity: 0; transform: translateY(24px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes float {
  0%, 100% { transform: translateY(0); }
  50%       { transform: translateY(-12px); }
}
.animate-reveal {
  animation: reveal 0.6s cubic-bezier(0.16, 1, 0.3, 1) forwards;
}
.animate-float {
  animation: float 3s ease-in-out infinite;
}
```

### 3.8 Background Mesh

Replace the current root `bg-slate-950` with a fixed background mesh. Add this to the root `<body>` or a fixed `<div>` wrapper in `layout.tsx`:

```tsx
<div className="fixed inset-0 -z-10" style={{
  background: '#F0F4FF',
  backgroundImage: `
    radial-gradient(ellipse at 20% 30%, rgba(51,122,255,0.12) 0%, transparent 60%),
    radial-gradient(ellipse at 80% 70%, rgba(199,187,253,0.15) 0%, transparent 60%),
    radial-gradient(ellipse at 50% 10%, rgba(51,200,255,0.08) 0%, transparent 50%)
  `
}} />
```

---

## 4. Logo & Branding

### 4.1 Logo Assets

The following SVG logo files must be added to `/frontend/public/`:

- `studio-logo-black.svg` — for light backgrounds (sidebar top, login page)
- `studio-logo-white.svg` — for dark sections if any
- `studio-star-blue.svg` — icon-only mark (for favicon, loading states, small contexts)

### 4.2 Sidebar Logo Replacement

In `Sidebar.tsx`, replace the current text logo:

```tsx
// REMOVE THIS:
<h1 className="text-xl font-bold gradient-text tracking-tight">UGC Engine</h1>
<p className="text-[10px] text-slate-500 mt-1 uppercase tracking-[0.2em] font-semibold">Creative Platform</p>

// REPLACE WITH:
<img src="/studio-logo-white.svg" alt="Aitoma Studio" className="h-8 w-auto" />
```

### 4.3 Page Tab Title

In `layout.tsx`, update the metadata:

```tsx
export const metadata = {
  title: 'Aitoma Studio',
  description: 'AI-powered UGC content engine',
};
```

---

## 5. Sidebar Overhaul (`Sidebar.tsx`)

The sidebar structure and all navigation logic must remain unchanged. Only the visual classes change.

### 5.1 Sidebar Container

```tsx
// REMOVE: className="w-64 border-r border-slate-800/60 bg-slate-900/40 backdrop-blur-2xl flex flex-col sticky top-0 h-screen"
// REPLACE WITH:
className="w-64 flex flex-col sticky top-0 h-screen glass-dark border-r border-white/5"
```

### 5.2 Logo Area

```tsx
// REMOVE: className="p-6 border-b border-slate-800/40"
// REPLACE WITH:
className="p-6 border-b border-white/5"
```

### 5.3 Navigation Links

Active state — replace `bg-blue-500/10 text-white border-l-2 border-blue-500 shadow-[inset_0_0_20px_rgba(59,130,246,0.06)]` with:
```
bg-white/10 text-white border-l-2 border-[#337AFF] shadow-[inset_0_0_20px_rgba(51,122,255,0.08)]
```

Inactive state — replace `text-slate-400 hover:text-slate-200 hover:bg-slate-800/40 border-l-2 border-transparent` with:
```
text-white/50 hover:text-white hover:bg-white/8 border-l-2 border-transparent
```

Active icon — replace `text-blue-400` with `text-[#337AFF]`

Inactive icon — replace `text-slate-500 group-hover:text-slate-300` with `text-white/30 group-hover:text-white/70`

Shortcut text — replace `text-slate-600` with `text-white/20`

### 5.4 Notification Panel

Notification button — replace `text-slate-400 hover:text-slate-200 hover:bg-slate-800/40` with `text-white/50 hover:text-white hover:bg-white/8`

Notification badge — keep `bg-blue-500` (matches brand primary)

Notification dropdown — replace `bg-slate-900 border border-slate-700/60` with `glass-dark border border-white/8`

Notification items — replace `bg-slate-800/50 border border-slate-700/30` with `bg-white/5 border border-white/8`

Empty state text — replace `text-slate-500` with `text-white/30`

### 5.5 User Profile Area

Container — replace `border-t border-slate-800/40` with `border-t border-white/5`

Avatar — replace `bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-blue-500/20 text-blue-400` with `gradient-cta text-white` (solid gradient avatar)

Name text — replace `text-white` with `text-white` (keep)

Role text — replace `text-[10px] text-slate-500` with `text-[10px] text-white/40`

### 5.6 Remove All Emoji from Nav Items

In `Sidebar.tsx`, the `navItems` array uses Lucide React icons — these are acceptable. However, ensure no emoji characters appear anywhere in the sidebar. If any exist, replace with the appropriate Lucide icon component.

---

## 6. Root Layout (`layout.tsx`)

The root layout wraps all pages. Replace the current body background:

```tsx
// Current body className (approximate):
// "bg-slate-950 text-white min-h-screen"

// New body className:
`${inter.variable} font-sans antialiased min-h-screen text-[#1A1A1F]`
```

Add the background mesh div immediately inside `<body>`, before the main content wrapper:

```tsx
<body className={`${inter.variable} font-sans antialiased min-h-screen text-[#1A1A1F]`}>
  {/* Background Mesh */}
  <div className="fixed inset-0 -z-10" style={{
    background: '#F0F4FF',
    backgroundImage: `
      radial-gradient(ellipse at 20% 30%, rgba(51,122,255,0.12) 0%, transparent 60%),
      radial-gradient(ellipse at 80% 70%, rgba(199,187,253,0.15) 0%, transparent 60%),
      radial-gradient(ellipse at 50% 10%, rgba(51,200,255,0.08) 0%, transparent 50%)
    `
  }} />
  {/* Main App Layout */}
  <div className="flex min-h-screen">
    <Sidebar />
    <main className="flex-1 p-8 overflow-y-auto">
      {children}
    </main>
  </div>
</body>
```

---

## 7. Page-by-Page Visual Overhaul

For each page, the functional logic (state, API calls, event handlers) must remain 100% unchanged. Only className strings and structural wrappers change.

### 7.1 Universal Page Header Pattern

Every page currently has a title + subtitle at the top. Apply this standard pattern:

```tsx
<div className="mb-8 animate-reveal">
  <h1 className="text-3xl font-bold tracking-tight text-[#1A1A1F] mb-1">
    {/* Page Title */}
  </h1>
  <p className="text-[#4A5568] text-sm">
    {/* Page Subtitle */}
  </p>
</div>
```

Remove all `gradient-text` from page titles — reserve gradient text only for the logo and special hero-level headings.

### 7.2 Dashboard (`page.tsx` — root)

**Stats Cards:** Replace `bg-slate-800/40` or similar dark card backgrounds with `glass rounded-2xl p-6 shadow-card hover:shadow-card-hover transition-all duration-300`

**Text colours:** Replace `text-slate-400` → `text-[#4A5568]`, `text-slate-200` → `text-[#1A1A1F]`, `text-slate-500` → `text-[#94A3B8]`

**Metric numbers:** Apply `text-[#1A1A1F] font-bold text-2xl`

**Quick action buttons:** Apply `gradient-cta text-white rounded-xl px-6 py-3 font-semibold shadow-glow hover:shadow-glow-hover hover:-translate-y-0.5 transition-all duration-200`

**Section dividers:** Replace `border-slate-800` with `border-[#E8ECF4]`

### 7.3 Library (`library/page.tsx`)

**Tab Navigation:** Replace the current dark tab bar with:
```tsx
<div className="flex gap-1 mb-8 glass rounded-2xl p-1.5 w-fit">
  {tabs.map(tab => (
    <button
      key={tab.key}
      onClick={() => setActiveTab(tab.key)}
      className={`px-5 py-2.5 rounded-xl font-medium text-sm transition-all duration-200 ${
        activeTab === tab.key
          ? 'gradient-cta text-white shadow-glow'
          : 'text-[#4A5568] hover:text-[#1A1A1F] hover:bg-white/60'
      }`}
    >
      {tab.label}
    </button>
  ))}
</div>
```

**Remove all emoji** from tab labels (👤, ✍️, 📱). Replace with Lucide React icons:
- Influencers → `<Users size={16} />`
- Scripts → `<FileText size={16} />`
- App Clips → `<Play size={16} />`

**Product Cards:** Replace dark card backgrounds with `glass rounded-2xl p-5 shadow-card hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-300`

**Product image containers:** Apply `rounded-xl overflow-hidden bg-[#F0F4FF]`

**Product name:** `text-[#1A1A1F] font-semibold text-sm`

**Product meta:** `text-[#94A3B8] text-xs`

**"Generate Shot" button on cards:** `gradient-cta text-white rounded-xl px-4 py-2 text-xs font-semibold shadow-glow hover:shadow-glow-hover transition-all`

### 7.4 Generate Shot Modal (`library/GenerateShotModal.tsx`)

This is the most visually prominent modal in the Library. Full overhaul:

**Modal overlay:** Keep existing backdrop logic. Replace overlay bg with `bg-[#1A1A1F]/40 backdrop-blur-sm`

**Modal panel:** Replace dark bg with `glass rounded-3xl p-6 shadow-[0_24px_64px_rgba(51,122,255,0.15)] border border-white/80 max-w-md w-full`

**Modal title:** `text-[#1A1A1F] text-lg font-bold`

**Product header row:** `glass rounded-xl p-3 mb-5 flex items-center gap-3`

**Section labels:** `text-[#1A1A1F] text-xs font-bold uppercase tracking-wider mb-3`

**Shot Type Cards (the 6 selector cards):** Replace dark selection cards with:
```tsx
className={`glass rounded-xl p-3 cursor-pointer transition-all duration-200 ${
  selectedType === type.key
    ? 'border-[#337AFF] border-2 shadow-glow bg-[#337AFF]/5'
    : 'border-transparent border-2 hover:border-[#337AFF]/30 hover:shadow-card-hover'
}`}
```

**Shot type name:** `text-[#1A1A1F] font-semibold text-sm`

**Shot type description:** `text-[#94A3B8] text-xs mt-0.5`

**Variations selector (1/2/3/4):** Replace dark button group with:
```tsx
className={`w-10 h-10 rounded-xl font-bold text-sm transition-all duration-200 ${
  variations === n
    ? 'gradient-cta text-white shadow-glow'
    : 'glass text-[#4A5568] hover:text-[#1A1A1F]'
}`}
```

**Cost estimate row:** `glass rounded-xl p-3 flex justify-between items-center`
- Label: `text-[#4A5568] text-sm`
- Cost value: `text-[#337AFF] font-bold text-sm`

**Generate button:** `w-full gradient-cta text-white rounded-xl py-3.5 font-bold text-sm shadow-glow hover:shadow-glow-hover hover:-translate-y-0.5 transition-all duration-200`

### 7.5 Create Page (`create/page.tsx`)

This is the primary video generation wizard. It is the most complex page.

**Page wrapper:** No change to structure. Add `animate-reveal` to the top-level container div.

**Step Indicator:** Replace dark step pills with:
```tsx
<div className="flex items-center gap-2 mb-8">
  {steps.map((step, i) => (
    <div key={i} className="flex items-center gap-2">
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-all ${
        currentStep > i ? 'gradient-cta text-white shadow-glow' :
        currentStep === i ? 'border-2 border-[#337AFF] text-[#337AFF] bg-[#337AFF]/5' :
        'border-2 border-[#E8ECF4] text-[#94A3B8]'
      }`}>{i + 1}</div>
      {i < steps.length - 1 && (
        <div className={`h-0.5 w-8 rounded-full transition-all ${currentStep > i ? 'bg-[#337AFF]' : 'bg-[#E8ECF4]'}`} />
      )}
    </div>
  ))}
</div>
```

**Form Sections / Cards:** Each section of the form (influencer selection, script, settings, etc.) should be wrapped in:
```tsx
<div className="glass rounded-2xl p-6 mb-5 shadow-card">
  <h3 className="text-[#1A1A1F] font-semibold text-sm mb-4 flex items-center gap-2">
    {/* Section icon + title */}
  </h3>
  {/* Section content */}
</div>
```

**Influencer Cards (selection grid):** Replace dark selection cards with:
```tsx
className={`glass rounded-2xl p-4 cursor-pointer transition-all duration-200 ${
  selectedInfluencer === inf.id
    ? 'border-2 border-[#337AFF] shadow-glow bg-[#337AFF]/5'
    : 'border-2 border-transparent hover:border-[#337AFF]/30 hover:shadow-card-hover'
}`}
```

**Influencer name:** `text-[#1A1A1F] font-semibold text-sm`
**Influencer description:** `text-[#94A3B8] text-xs`

**Input fields (text inputs, selects, textareas):**
```tsx
className="w-full glass rounded-xl px-4 py-3 text-[#1A1A1F] text-sm placeholder:text-[#94A3B8] border-transparent focus:border-[#337AFF] focus:ring-2 focus:ring-[#337AFF]/20 outline-none transition-all"
```

**Dropdown / Select elements:** Same as input fields. Ensure `text-[#1A1A1F]` for selected value.

**Toggle / Radio buttons:** Use brand blue `#337AFF` for selected state.

**Duration selector (15s / 30s):**
```tsx
className={`px-5 py-2.5 rounded-xl font-semibold text-sm transition-all duration-200 ${
  duration === val ? 'gradient-cta text-white shadow-glow' : 'glass text-[#4A5568] hover:text-[#1A1A1F]'
}`}
```

**Cinematic Shots selector (Step 14):** Apply the same card pattern as the shot type cards in the modal.

**Cost Estimate Panel:** 
```tsx
<div className="glass rounded-2xl p-5 border border-[#337AFF]/20 bg-[#337AFF]/3">
  <div className="flex justify-between items-center">
    <span className="text-[#4A5568] text-sm font-medium">Estimated Cost</span>
    <span className="text-[#337AFF] font-bold text-lg">${cost}</span>
  </div>
</div>
```

**Submit / Generate Button:**
```tsx
className="w-full gradient-cta text-white rounded-xl py-4 font-bold text-base shadow-glow hover:shadow-glow-hover hover:-translate-y-0.5 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0"
```

**Success message:** Replace dark success banners with:
```tsx
<div className="glass rounded-2xl p-5 border border-[#10B981]/30 bg-[#10B981]/5 text-[#10B981] font-semibold text-sm">
  {successMessage}
</div>
```

### 7.6 Generate Page (`generate/page.tsx`)

This is the legacy single-video generator. Apply the same patterns as the Create page.

**Step navigation buttons:** `glass rounded-xl px-5 py-2.5 text-sm font-semibold text-[#4A5568] hover:text-[#1A1A1F] transition-all`

**"Back" button:** `glass rounded-xl px-5 py-2.5 text-sm font-semibold text-[#4A5568]`

**"Next / Generate" button:** `gradient-cta text-white rounded-xl px-6 py-2.5 text-sm font-bold shadow-glow hover:shadow-glow-hover transition-all`

### 7.7 History Page (`history/page.tsx`)

The history page shows a table of production jobs.

**Table container:** Wrap the table in `glass rounded-2xl shadow-card overflow-hidden`

**Table header row:** `bg-[#F0F4FF] border-b border-[#E8ECF4]`

**Table header cells:** `text-[#94A3B8] text-xs font-bold uppercase tracking-wider px-6 py-4`

**Table body rows:** `border-b border-[#E8ECF4] hover:bg-[#337AFF]/3 transition-colors`

**Table body cells:** `px-6 py-4 text-[#1A1A1F] text-sm`

**Job ID:** `font-mono text-[#1A1A1F] font-semibold text-sm`

**Date:** `text-[#94A3B8] text-xs`

**Status badges:** Keep the existing logic but update colours:
- `success` → `bg-[#10B981]/10 text-[#10B981] border border-[#10B981]/20 px-3 py-1 rounded-full text-xs font-bold`
- `failed` → `bg-red-500/10 text-red-500 border border-red-500/20 px-3 py-1 rounded-full text-xs font-bold`
- `processing` → `bg-[#337AFF]/10 text-[#337AFF] border border-[#337AFF]/20 px-3 py-1 rounded-full text-xs font-bold animate-pulse`

**Progress bar track:** `bg-[#E8ECF4] h-2 rounded-full`

**Progress bar fill:** `gradient-cta h-full rounded-full`

**Empty state:** `text-[#94A3B8] text-sm italic text-center py-16`

**Download / View button:** `glass rounded-xl px-4 py-2 text-xs font-semibold text-[#337AFF] hover:bg-[#337AFF]/5 transition-all`

### 7.8 Assets Page (`assets/page.tsx`)

**Tab bar:** Apply the same pill-style tab bar as the Library page (see §7.3).

**Remove all emoji** from tab labels. Replace:
- `👤 Influencers` → Lucide `<Users size={15} />` + "Influencers"
- `✍️ Scripts` → Lucide `<FileText size={15} />` + "Scripts"
- `📱 App Clips` → Lucide `<Smartphone size={15} />` + "App Clips"

**Influencer Cards:** Apply `glass rounded-2xl p-5 shadow-card hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-300`

**Influencer avatar/image:** `rounded-xl overflow-hidden w-16 h-16 bg-[#F0F4FF]`

**Influencer name:** `text-[#1A1A1F] font-semibold`

**Influencer meta (personality, style):** `text-[#94A3B8] text-xs`

**Script Cards:** `glass rounded-2xl p-5 shadow-card hover:shadow-card-hover transition-all`

**Script text preview:** `text-[#4A5568] text-sm line-clamp-3`

**Script category badge:** `badge-gradient text-white text-xs font-bold px-3 py-1 rounded-full`

**App Clip Cards:** `glass rounded-2xl overflow-hidden shadow-card hover:shadow-card-hover transition-all`

**Video preview area:** Keep existing `<video>` element. Wrap in `rounded-t-2xl overflow-hidden bg-[#1A1A1F]`

**Clip name:** `text-[#1A1A1F] font-semibold text-sm`

**Clip meta:** `text-[#94A3B8] text-xs`

### 7.9 Activity / Campaigns Pages

Apply the same universal patterns:
- All cards → `glass rounded-2xl p-5 shadow-card`
- All text → brand colour hierarchy
- All buttons → brand button patterns
- All tables → same as History page pattern

---

## 8. Video Player & Asset Viewing

Wherever a video is displayed (history page download, library preview, generate page result), apply this wrapper:

```tsx
<div className="glass rounded-2xl overflow-hidden shadow-[0_24px_64px_rgba(51,122,255,0.15)]">
  <video
    src={videoUrl}
    controls
    className="w-full aspect-video bg-[#1A1A1F]"
  />
</div>
```

For image assets (product shots, influencer photos), apply:

```tsx
<div className="glass rounded-2xl overflow-hidden shadow-card hover:shadow-card-hover transition-all">
  <img src={imageUrl} alt={alt} className="w-full object-cover" />
</div>
```

---

## 9. Iconography Rules

The brand forbids emoji in the UI. Across the entire codebase, perform a global search for emoji characters and replace every instance with the appropriate Lucide React icon. The key replacements are:

| Current Emoji | Lucide Replacement | Import |
|---|---|---|
| 👤 | `<Users />` | `import { Users } from 'lucide-react'` |
| ✍️ | `<FileText />` | `import { FileText } from 'lucide-react'` |
| 📱 | `<Smartphone />` | `import { Smartphone } from 'lucide-react'` |
| ✅ | `<CheckCircle />` | `import { CheckCircle } from 'lucide-react'` |
| ❌ | `<XCircle />` | `import { XCircle } from 'lucide-react'` |
| 🎬 | `<Film />` | `import { Film } from 'lucide-react'` |
| 📸 | `<Camera />` | `import { Camera } from 'lucide-react'` |
| 🌟 | `<Sparkles />` | `import { Sparkles } from 'lucide-react'` |

All Lucide icons in the UI must use `strokeWidth={1.75}` and `size={16}` or `size={20}` depending on context.

For icon containers (feature card icons), apply:
```tsx
<div className="w-10 h-10 rounded-xl flex items-center justify-center"
  style={{ background: 'linear-gradient(135deg, rgba(51,122,255,0.12), rgba(107,95,228,0.12))' }}>
  <Icon size={20} strokeWidth={1.75} className="text-[#337AFF]" />
</div>
```

---

## 10. Notification System

The notification strings in `Sidebar.tsx` currently use emoji (`✅`, `❌`). Replace these with plain text equivalents:

```tsx
// REMOVE:
`Video ${j.id.substring(0, 6)} completed! ✅`
`Job ${j.id.substring(0, 6)} failed. ❌`

// REPLACE WITH:
`Video ${j.id.substring(0, 6)} — Completed`
`Job ${j.id.substring(0, 6)} — Failed`
```

---

## 11. Loading & Empty States

**Loading spinners:** Replace any generic grey spinners with:
```tsx
<div className="w-6 h-6 rounded-full border-2 border-[#337AFF]/20 border-t-[#337AFF] animate-spin" />
```

**Empty state panels:**
```tsx
<div className="glass rounded-2xl p-12 text-center shadow-card">
  <div className="w-14 h-14 rounded-2xl mx-auto mb-4 flex items-center justify-center"
    style={{ background: 'linear-gradient(135deg, rgba(51,122,255,0.12), rgba(107,95,228,0.12))' }}>
    <Icon size={28} strokeWidth={1.75} className="text-[#337AFF]" />
  </div>
  <h3 className="text-[#1A1A1F] font-semibold mb-2">Nothing here yet</h3>
  <p className="text-[#94A3B8] text-sm">Descriptive empty state message.</p>
</div>
```

---

## 12. Implementation Order & Safety Protocol

Antigravity must follow this exact sequence to avoid breaking the application:

**Step 1 — `globals.css` only:** Add all CSS custom properties, glass utilities, gradient utilities, animation keyframes, and shadow utilities. Do not touch any `.tsx` files yet. Verify the app still compiles and runs.

**Step 2 — `layout.tsx`:** Add Inter font, update body className, add background mesh div. Verify the app still compiles and all pages render.

**Step 3 — `Sidebar.tsx`:** Apply all sidebar visual changes. Replace text logo with `<img>` tag for the SVG logo. Verify all navigation links still work and the active state logic functions correctly.

**Step 4 — One page at a time:** Apply visual changes to pages in this order: Dashboard → Library → Assets → History → Create → Generate. After each page, verify that all API calls, state updates, and user interactions still function identically to before.

**Step 5 — Modals:** Apply visual changes to `GenerateShotModal.tsx`, `InfluencerModal.tsx`, and `ProductShotsGallery.tsx`. Verify all modal open/close logic, form submissions, and data display work correctly.

**Step 6 — Final audit:** Search the entire codebase for any remaining `slate-`, `gray-`, `zinc-`, or emoji characters and replace with brand equivalents.

---

## 13. What Must Never Change

The following must remain completely untouched:

- All `useState`, `useEffect`, `useCallback` hooks and their logic
- All `fetch()` and `apiFetch()` calls and their URLs, headers, and body structures
- All TypeScript interfaces and type definitions
- All routing (`Link href`, `useRouter().push()`)
- All form submission handlers (`handleSubmit`, `handleGenerate`, etc.)
- All conditional rendering logic (loading states, error states, empty states — only their visual wrapper changes)
- All `supabaseClient.ts`, `utils.ts`, `types.ts` files
- All backend files (Python, SQL, etc.)
- The `vercel.json` and `tsconfig.json` configuration files
- The `package.json` dependencies (do not add or remove packages unless strictly necessary for font loading)
