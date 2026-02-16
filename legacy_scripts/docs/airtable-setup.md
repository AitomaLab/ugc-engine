# Airtable Setup

Create your clip review queue in 5 minutes.

## Step 1: Create a New Base

1. Go to [airtable.com](https://airtable.com) and sign up/log in
2. Click **+ Create a base** → **Start from scratch**
3. Name it: `YouTube Shorts Automation`

## Step 2: Create the Clips Table

Rename "Table 1" to **shortsRobo** (or whatever name you prefer) and add these fields:

| Field Name | Type | Purpose |
|------------|------|---------|
| `Video` | Attachment | The clip video file from Vizard |
| `Title` | Single line text | AI-generated clip title |
| `Caption` | Long text | Transcript / caption text |
| `Viral Score` | Number | Vizard's virality score (0-100) |
| `Viral Reason` | Long text | Why Vizard thinks it'll go viral |
| `Source URL` | URL | Original YouTube video link |
| `Status` | Single select | Review status (see below) |

### Status Options

Create these single-select options:
- 🟡 **Pending Review** — clips waiting for your review
- 🟢 **Approved** — clips you want to post
- 🔴 **Rejected** — clips you don't want
- 🔵 **Ready** — clips that have been scheduled

## Step 3: Create Views (Optional but Recommended)

### 📋 Review Queue
- Type: Grid
- Filter: `Status` is `Pending Review`
- Sort: `Viral Score` → Descending

### ✅ Approved
- Type: Grid
- Filter: `Status` is `Approved`

> **Pro Tip:** Use the Gallery view on your phone for quick swipe-through reviewing!

## Step 4: Get Your API Credentials

### Personal Access Token (PAT)
1. Go to [airtable.com/create/tokens](https://airtable.com/create/tokens)
2. Click **Create new token**
3. Name: `Clipper Bot`
4. Scopes:
   - `data.records:read`
   - `data.records:write`
5. Access: Select your `YouTube Shorts Automation` base
6. Click **Create token**
7. **Copy the token** (you won't see it again!)

### Base ID
1. Open your base in Airtable
2. Look at the URL: `https://airtable.com/appXXXXXXXXXX/...`
3. The `appXXXXXXXXXX` part is your **Base ID**

---

*Next step:* Get Blotato credentials → [blotato-setup.md](blotato-setup.md)
