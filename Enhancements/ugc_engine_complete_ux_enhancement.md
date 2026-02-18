# UGC Engine: Complete Enterprise-Grade UX/UI Enhancement Strategy

**Document Version:** 1.0  
**Date:** February 18, 2026  
**Philosophy:** Inspired by Steve Jobs' principle: "Design is not just what it looks like and feels like. Design is how it works."

---

## Executive Summary

After conducting a comprehensive analysis of the UGC Engine SaaS by examining the latest GitHub codebase and user interface screenshots, this document presents a strategic roadmap to transform the platform from a functional tool into an enterprise-grade creative powerhouse. The current system is operational but suffers from fragmented workflows, inconsistent navigation, and a lack of focus on the creative user experience. This enhancement strategy addresses these fundamental issues through a complete UX/UI overhaul centered on four core principles: clarity of purpose, effortless workflow, empowerment through simplicity, and delight in every interaction.

---

## Part 1: Current State Analysis

### What the Platform Does Well

The technical foundation of the UGC Engine is solid. The platform successfully implements a distributed architecture with real-time job tracking, integrates multiple AI services (Kie.ai, ElevenLabs), and provides a clean, modern dark interface with glassmorphic design elements. The asset management system for influencers and app clips functions correctly, and the real-time polling mechanism ensures users see updates without manual refreshes.

### Critical UX/UI Gaps Identified

However, several fundamental user experience issues prevent the platform from achieving its full potential. The navigation structure is inconsistent and confusing. Screenshots reveal a "Campaigns" page that does not exist in the codebase, creating a disconnect between what users see and what developers have implemented. The distinction between "single generation" and "bulk campaigns" is artificial and forces users to make unnecessary decisions before they even begin creating content.

The most significant gap is the absence of a dedicated space for final videos. Users generate content, but there is no gallery, no visual library, and no intuitive way to browse, preview, or manage completed videos. The "Job History" page attempts to serve as both a technical log and a content browser, failing at both tasks. Additionally, the script library—a core asset type—has no management interface, forcing users to rely on whatever scripts were pre-loaded into the database.

The campaign creation workflow lacks essential features. Users cannot select which AI model to use when launching bulk campaigns, even though this option exists for single generations. There is no way to name campaigns, organize them, or apply different content strategies (such as randomizing scripts or using them sequentially). Error handling is poor, with failed jobs displaying cryptic messages in a table row rather than providing actionable troubleshooting guidance.

---

## Part 2: The Four-Pillar Redesign Strategy

To address these issues, we will restructure the entire application around four intuitive, purpose-driven pillars. This approach eliminates the fragmented navigation and creates a logical, workflow-oriented structure that mirrors how creative professionals actually work.

### The New Navigation Structure

| Current Navigation | New Navigation | Purpose |
|---|---|---|
| Dashboard | **Studio** | Command center showing what's happening now and what to do next |
| New Generation + Campaigns | **Create** | Unified portal for all content generation (single or bulk) |
| Asset Libraries + (missing) Final Videos | **Library** | Central hub for all assets and completed content |
| Job History | **Activity** | Detailed technical log for monitoring system operations |

---

## Part 3: Detailed Pillar-by-Pillar Recommendations

### Pillar 1: The Studio (Your Creative Command Center)

**Route:** `/` (Home/Dashboard)

**Purpose:** The Studio is where users start their day. It provides an at-a-glance overview of ongoing work, celebrates recent successes, and guides users toward their next action.

**Current Problems:**
- The dashboard is static and informative but not actionable.
- The "Quick Actions" section is generic and doesn't adapt to the user's current state.
- There is no visual connection to the final product (completed videos).

**Recommended Changes:**

**1. Hero Section: Personalized Welcome**

The welcome message should be dynamic and contextual. Instead of a generic "Welcome back, Creator," the system should acknowledge the user's current state. For example, if a campaign is in progress, the message could read: "Welcome back, Creator. Your Spring Campaign is 70% complete." If no work is in progress, it could say: "Your production pipeline is ready. What will you create today?"

**2. Live Campaign Tracker**

Replace the static stats cards with an interactive **Campaign Tracker**. This section should display all active campaigns as expandable cards. Each card shows:

- Campaign name (e.g., "TikTok Travel Series - Max")
- Overall progress (e.g., "7 of 10 videos complete")
- Status breakdown (e.g., "5 success, 2 processing, 1 pending, 2 failed")
- Estimated completion time based on average processing speed

Clicking a campaign card expands it to reveal the individual videos within that campaign, each with its own progress bar and status. This provides granular visibility without overwhelming the main view.

**3. Fresh from the Engine: Content Showcase**

Add a new section below the Campaign Tracker titled **"Fresh from the Engine."** This is a horizontal carousel displaying the 3-5 most recently completed videos with large thumbnail previews. Hovering over a thumbnail plays a silent preview loop. Clicking opens the video in a modal player with options to download, share, or view details.

This section serves two critical purposes: it provides immediate gratification by showcasing the user's creative output, and it creates a direct visual link between the Studio and the Library, making the final product feel accessible and celebrated.

**4. Contextual Quick Actions**

The "Quick Actions" section should be intelligent and adaptive. The system should analyze the user's current state and present the most relevant next step:

- If the user has no influencers: "Create Your First Influencer"
- If the user has influencers but no scripts: "Build Your Script Library"
- If the user has assets but no campaigns: "Launch Your First Campaign"
- If the user has active campaigns: "Create Another Campaign" and "View All Videos"

**5. System Health Indicator**

Keep the current "Status" card but enhance it with more detail. Instead of just "Online," show the health of each integrated service:

- Kie.ai API: ✓ Operational
- ElevenLabs API: ✓ Operational
- Celery Workers: 3 active
- Queue: 5 jobs pending

This provides transparency and helps users understand if delays are due to system issues or simply queue backlog.

---

### Pillar 2: Create (Unified Generation Workflow)

**Route:** `/create`

**Purpose:** The Create page is where all content generation begins. It should be a single, elegant form that adapts intelligently to the user's needs, whether they're creating one video or one hundred.

**Current Problems:**
- The distinction between "New Generation" and "Campaigns" is artificial and creates a disjointed experience.
- The 3-step wizard for single generation feels unnecessarily complex for a simple task.
- Bulk campaign creation lacks essential features like model selection and campaign naming.

**Recommended Changes:**

**1. Unified Creation Form**

Eliminate the separate "New Generation" and "Campaigns" pages. The Create page should start with a single, clean form that asks the fundamental questions:

**Section 1: What do you want to create?**

- **Influencer Selection:** A visual grid of influencer cards (same as current Step 1). Selecting an influencer reveals their category and voice settings.
- **Quantity:** A simple numeric input field, defaulting to `1`. The label should read: "How many videos?" with a subtitle: "Enter 1 for a single video, or 10+ to launch a campaign."

**Section 2: Content & Style**

- **Script Source:** A dropdown with three options:
  - `Use a specific script` → Reveals the script library dropdown
  - `Random from library (Recommended)` → System auto-selects
  - `Write custom script` → Reveals a textarea

- **AI Model:** A dropdown to select the generation model (Seedance, Kling, Veo, InfiniteTalk). This should be available for both single and bulk generation.

- **App Clip:** A dropdown with:
  - `Auto-Select (Recommended)` → System chooses based on influencer category
  - `Specific clip` → Shows the app clip library

- **Duration:** Toggle buttons for `15s` or `30s`.

**Section 3: Campaign Mode (Conditional)**

This section only appears when the quantity is greater than 1. It reveals:

- **Campaign Name:** A text input (e.g., "Spring Promo for Max"). This is essential for organization.
- **Content Strategy:** A dropdown:
  - `Random (Recommended)` → Each video gets a random script/clip pairing
  - `Sequential` → Scripts are used in order (for multi-part stories)
  - `Fixed` → All videos use the same script (for A/B testing different models)

**2. Advanced Settings Drawer**

To keep the main form clean, move less-used options into a collapsible "Advanced Settings" drawer:

- AI Hook Generation (currently in Step 2)
- Voice settings override
- Custom background music selection

**3. Smart Validation & Preview**

Before submitting, show a preview card summarizing the user's choices:

- "You're about to create 10 videos featuring Max, using random Travel scripts and Seedance 1.5 Pro. Estimated completion: 25 minutes."

This provides clarity and confidence before committing to a potentially expensive operation.

---

### Pillar 3: The Library (Your Content Universe)

**Route:** `/library`

**Purpose:** The Library is the central hub for everything the user owns: final videos, influencers, scripts, and app clips. It should feel like a curated gallery, not a database dump.

**Current Problems:**
- Final videos have no dedicated home. They're buried in the "Job History" table.
- The script library has no management interface.
- Asset management is split across multiple pages with inconsistent UI.

**Recommended Changes:**

**1. Four-Tab Structure**

The Library will have four tabs, each serving a distinct purpose:

| Tab | Purpose | Current Status |
|---|---|---|
| **Videos** | Gallery of all completed videos | **Missing** |
| **Influencers** | Manage AI influencer profiles | Exists in `/manage` |
| **Scripts** | Manage script library | **Missing** |
| **App Clips** | Manage app footage | Exists in `/manage` |

**2. The Videos Tab: A Visual Gallery**

This is the most important addition. The Videos tab should be a visual grid (3-4 columns on desktop) displaying all successfully generated videos. Each video card shows:

- A large thumbnail (extracted from the first frame)
- Video duration badge (e.g., "15s")
- Influencer name and category
- Creation date
- Hover state: Silent video preview loop

Clicking a video opens a **Video Detail Page** (modal or dedicated route) with:

- A large video player
- Download button (MP4)
- Share button (copy public URL)
- Metadata section showing:
  - Which influencer, script, and app clip were used
  - AI model used
  - Generation timestamp
- A "Schedule to Social Media" button (placeholder for Blotato.com integration)

**3. The Scripts Tab: Full CRUD Interface**

This tab is currently missing. It should mirror the structure of the Influencers and App Clips tabs:

- A form on the left to add new scripts (text input, category dropdown, tags)
- A list/grid on the right showing all existing scripts
- Each script card shows the first 60 characters, category tag, and a delete button
- An "AI Generate Script" button that uses the same hook generation API

**4. Global Search Bar**

Add a prominent search bar at the top of the Library that searches across all four tabs. Typing "Travel" should show:

- Videos featuring travel influencers
- Travel-category scripts
- Travel-related app clips
- Influencers in the Travel category

This makes the Library feel cohesive and powerful.

**5. Filters & Sorting**

Each tab should have filter and sort options:

- **Videos:** Filter by influencer, date range, model used. Sort by newest, oldest, duration.
- **Influencers:** Filter by category. Sort by name, creation date.
- **Scripts:** Filter by category, tags. Sort by length, creation date.
- **App Clips:** Filter by category. Sort by duration, name.

---

### Pillar 4: Activity (The Technical Log)

**Route:** `/activity`

**Purpose:** Activity is a detailed, technical log for power users who need to monitor system operations, debug issues, and track resource usage.

**Current Problems:**
- The "Job History" page tries to be both a progress tracker and a content gallery, failing at both.
- Error messages are cryptic and not actionable.
- No way to group jobs by campaign.

**Recommended Changes:**

**1. Enhanced Table View**

Keep the table layout but add more information:

| Column | Purpose |
|---|---|
| **Campaign** | Name of the campaign (or "Single Generation") |
| **Job ID** | Truncated UUID with copy button |
| **Influencer** | Name and category |
| **Status** | Color-coded badge (success, failed, processing, pending) |
| **Progress** | Visual progress bar |
| **Model** | Which AI model was used |
| **Created** | Timestamp |
| **Duration** | How long the job took (for completed jobs) |
| **Actions** | View Details, Retry (for failed jobs) |

**2. Expandable Error Details**

Clicking a "Failed" status badge should open a modal with:

- The full error message
- A stack trace (if available)
- **Troubleshooting suggestions** based on the error type:
  - "MissingSchema error" → "The reference image URL is invalid. Please check the influencer's image URL in the Library."
  - "API timeout" → "The Kie.ai API took too long to respond. This is usually temporary. Try again in a few minutes."

**3. Campaign Grouping**

Add a toggle at the top: "Group by Campaign." When enabled, jobs are visually grouped under their campaign name, making it easy to see all videos in a batch at once.

**4. Resource Usage Dashboard**

Add a small stats section at the top showing:

- Total videos generated (all time)
- Total API credits spent (this month)
- Average generation time per video
- Success rate (percentage of jobs that completed successfully)

This provides valuable insights for users managing large-scale operations.

---

## Part 4: Additional UX Enhancements

### 1. Onboarding Flow for New Users

The current platform assumes users know what to do. Add a guided onboarding flow that triggers on first login:

**Step 1:** "Welcome to UGC Engine. Let's create your first influencer."  
**Step 2:** "Great! Now add a script to your library."  
**Step 3:** "Upload an app clip."  
**Step 4:** "You're ready! Let's generate your first video."

This reduces the learning curve and ensures users experience success immediately.

### 2. Keyboard Shortcuts

Power users love keyboard shortcuts. Implement:

- `Cmd/Ctrl + N` → Open Create page
- `Cmd/Ctrl + L` → Open Library
- `Cmd/Ctrl + K` → Focus global search
- `Esc` → Close modals

### 3. Dark Mode Refinement

The current dark theme is good, but refine it further:

- Increase contrast on text for better readability (current slate-400 text is too dim on slate-900 backgrounds)
- Use more subtle shadows and glows (current "glow-hover" effect is too intense)
- Ensure all interactive elements have clear hover and active states

### 4. Mobile Responsiveness

While this is primarily a desktop tool, ensure the Library (especially the Videos tab) is fully responsive. Users should be able to browse and preview videos on mobile devices.

### 5. Notification System

Implement a notification bell icon in the header that shows:

- "Your campaign 'Spring Promo' is complete! View videos."
- "Job XYZ failed. View details."
- "New AI model available: Kling 2.7"

This keeps users informed without requiring them to constantly check the Activity page.

---

## Part 5: Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

1. Restructure navigation to the four-pillar system
2. Implement the unified Create page
3. Build the Videos tab in the Library

### Phase 2: Enhancement (Week 3-4)

4. Build the Scripts management tab
5. Enhance the Studio with Campaign Tracker and "Fresh from the Engine"
6. Upgrade the Activity page with error details and campaign grouping

### Phase 3: Polish (Week 5-6)

7. Add global search to the Library
8. Implement onboarding flow
9. Add keyboard shortcuts
10. Refine dark mode and mobile responsiveness

---

## Part 6: Antigravity Implementation Prompt

Here is the complete prompt to provide to Antigravity:

```
**Objective:** Perform a comprehensive UX/UI overhaul of the UGC Engine SaaS to transform it into an enterprise-grade creative tool. The redesign is inspired by Steve Jobs' principle: "Design is not just what it looks like and feels like. Design is how it works."

**Source of Truth:** The detailed enhancement strategy document and the existing codebase at `AitomaLab/ugc-engine`.

**Core Implementation Tasks:**

**Phase 1: Navigation Restructure**

1. Refactor the main application layout to implement the four-pillar navigation:
   - **Studio** (`/`) - Command center
   - **Create** (`/create`) - Unified generation workflow
   - **Library** (`/library`) - Asset and video gallery
   - **Activity** (`/activity`) - Technical log

2. Update the sidebar navigation to reflect these four pillars with appropriate icons.

**Phase 2: Studio Page**

3. Transform the current dashboard (`/app/page.tsx`) into the Studio:
   - Implement a dynamic welcome message that adapts to the user's current state
   - Build an interactive Campaign Tracker that groups jobs by campaign name
   - Add a "Fresh from the Engine" carousel showing the 3-5 most recent videos with hover-preview
   - Make Quick Actions contextual based on user's asset library state
   - Enhance the System Health indicator to show individual service status

**Phase 3: Unified Create Page**

4. Create a new `/create` page that merges single and bulk generation:
   - Build a unified form with: Influencer Selection, Quantity input, Script Source, AI Model, App Clip, Duration
   - Implement conditional "Campaign Mode" section that appears when quantity > 1
   - Add Campaign Name input and Content Strategy dropdown in Campaign Mode
   - Ensure AI Model selection is available for both single and bulk generation
   - Create an "Advanced Settings" collapsible drawer for less-used options
   - Add a smart preview summary before submission

**Phase 4: Library Implementation**

5. Create the `/library` page with four tabs:
   - **Videos Tab:** Build a visual grid gallery of all completed videos with thumbnail previews
   - **Influencers Tab:** Migrate existing influencer management from `/manage`
   - **Scripts Tab:** Build a full CRUD interface for script management (currently missing)
   - **App Clips Tab:** Migrate existing app clip management from `/manage`

6. Implement the Video Detail Page (modal or route):
   - Large video player
   - Download and Share buttons
   - Metadata section showing influencer, script, app clip, model, timestamp
   - "Schedule to Social Media" button (placeholder)

7. Add a global search bar to the Library that searches across all tabs.

8. Implement filters and sorting for each tab.

**Phase 5: Activity Page Enhancement**

9. Refactor the existing `/history` page into `/activity`:
   - Add a "Campaign" column to the jobs table
   - Add "Model" and "Duration" columns
   - Implement expandable error details modal with troubleshooting suggestions
   - Add a "Group by Campaign" toggle
   - Add a Resource Usage Dashboard section at the top

**Phase 6: Additional Enhancements**

10. Implement a notification system with a bell icon in the header.

11. Add keyboard shortcuts (Cmd/Ctrl + N for Create, Cmd/Ctrl + L for Library, Cmd/Ctrl + K for search).

12. Refine the dark mode theme for better contrast and readability.

13. Ensure mobile responsiveness for the Library.

**Technical Notes:**

- All video thumbnails should be generated from the first frame of the video.
- Hover-preview functionality should use HTML5 video with `muted` and `loop` attributes.
- The Campaign Tracker should query the backend for jobs grouped by a new `campaign_name` field (you may need to add this to the database schema).
- The global search should use client-side filtering for now (no new backend endpoint required).
- Error troubleshooting suggestions should be hardcoded based on common error patterns (MissingSchema, API timeout, etc.).

**End of Prompt**
```

---

## Conclusion

This comprehensive enhancement strategy addresses every identified UX/UI gap in the UGC Engine. By restructuring the application around four intuitive pillars, unifying the generation workflow, creating a dedicated video gallery, and enhancing the technical log, we transform the platform from a functional tool into an enterprise-grade creative powerhouse. The implementation roadmap provides a clear path forward, and the Antigravity prompt ensures all changes can be executed systematically. The result will be a platform that not only works flawlessly but delights users at every step of their creative journey.

**End of Document**
