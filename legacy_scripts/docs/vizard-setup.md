# Vizard.ai API Setup

Get your API key to enable AI video clipping.

## Step 1: Create a Vizard Account

1. Go to [vizard.ai](https://vizard.ai)
2. Sign up or log in
3. You'll need a **paid plan** that includes API access

## Step 2: Get Your API Key

1. Click your **profile icon** (top right)
2. Go to **Workspace Settings**
3. Click the **API** tab
4. Copy your **API key**

It looks something like: `a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6`

## Step 3: (Optional) Choose a Template

Vizard lets you apply styling templates to your clips. The pipeline uses a default template ID.

To use a custom template:
1. Create a template in Vizard's dashboard
2. Note the **Template ID** from the URL
3. Update `VIZARD_TEMPLATE_ID` in `tools/vizard_clipper.py`

## What Vizard Does

- Takes your YouTube URL
- AI analyzes the video for the best short-form moments
- Generates multiple clips with subtitles
- Returns download URLs for each clip

> **Credits:** Each video processed uses Vizard credits. Check your plan for limits.

---

*Next step:* Set up Airtable → [airtable-setup.md](airtable-setup.md)
