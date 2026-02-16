# R55 Clipper — YouTube Shorts Automation

Turn your YouTube videos into Shorts automatically. Review them. Schedule to all platforms. All from your phone.

## 🎯 How It Works

```
┌─────────────────────── WORKFLOW 1: GENERATE ───────────────────────┐
│                                                                     │
│  📱 Send YouTube URL    →  🤖 Vizard AI clips it  →  📋 Airtable  │
│     to Telegram bot          (5-15 min)               review queue  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────── WORKFLOW 2: SCHEDULE ───────────────────────┐
│                                                                     │
│  📱 Send "done reviewing"  →  ✅ Approved clips  →  📅 Blotato    │
│     to Telegram bot             from Airtable        auto-schedule  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 📦 What's Inside

| File | Purpose |
|------|---------|
| `AGENT.md` | **Start here!** Open in Antigravity and ask the agent to set it up |
| `tools/vizard_clipper.py` | The pipeline — deploys to Modal as a serverless bot |
| `.env.example` | All the API keys you'll need (with instructions) |
| `docs/` | Step-by-step guides for each service |

## ⚡ Quick Start

1. Open this folder in **Antigravity** (or your preferred agent platform)
2. Tell the agent: **"Help me set this up"**
3. Follow the guided steps — the agent walks you through everything

## 🔧 Services You'll Need

| Service | What It Does | Cost |
|---------|-------------|------|
| **Vizard.ai** | AI clipping | Paid (API access) |
| **Telegram** | Bot interface | Free |
| **Airtable** | Review queue | Free tier works |
| **Modal** | Serverless hosting | Free tier works |
| **Blotato** | Multi-platform scheduling | Paid (API access) |

## 📱 Daily Workflow (After Setup)

1. Upload a video to YouTube
2. Send the URL to your Telegram bot
3. Wait ~10 min — clips appear in Airtable
4. Review on your phone — approve the good ones
5. Send "done reviewing" — approved clips auto-schedule!

---

*Built with ❤️ and [Antigravity](https://antigravity.dev)*
