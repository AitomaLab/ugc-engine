# Blotato Setup

Connect Blotato to auto-schedule your approved clips to YouTube Shorts.

## Step 1: Create a Blotato Account

1. Go to [blotato.com](https://blotato.com) and sign up
2. You'll need a **paid plan** that includes API access

## Step 2: Connect Your YouTube Channel

1. In Blotato, go to **Accounts** → **Connect Account**
2. Select **YouTube**
3. Authorize Blotato to post on your behalf

## Step 3: Get Your API Key

1. Go to **Settings** → **API**
2. Copy your **API key**

## Step 4: Get Your YouTube Account ID

1. Go to **Accounts** in the Blotato dashboard
2. Click on your YouTube account
3. Find the **Account ID** (it'll be in the URL or settings)
   - It looks something like: `abc123def456`

## Step 5: Set Up Schedule Slots

Blotato uses "schedule slots" to auto-pick posting times:

1. Go to **Schedule** in Blotato
2. Set up your preferred posting times
3. The pipeline uses `useNextFreeSlot: true`, which means it'll grab the next available slot

> **Important:** If you have no schedule slots configured, posts may fail to schedule.

## How Blotato Works in the Pipeline

When you send "done reviewing" to the Telegram bot:
1. It finds all **Approved** clips in Airtable
2. Schedules each one as a YouTube Short via Blotato
3. Marks each row as **Ready** in Airtable
4. Sends you a Telegram confirmation

---

*Next step:* Deploy to Modal → [modal-setup.md](modal-setup.md)
