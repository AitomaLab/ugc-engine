# Modal Setup & Deployment

Modal is the serverless platform that runs your clipper bot 24/7. You only pay for what you use.

## Step 1: Create a Modal Account

1. Go to [modal.com](https://modal.com) and sign up
2. Free tier includes enough compute to get started

## Step 2: Install the Modal CLI

```bash
pip install modal
```

## Step 3: Authenticate

```bash
modal setup
```

This opens a browser to link your CLI to your Modal account.

## Step 4: Create Your Secret

This stores all your API keys securely in Modal. Replace the placeholder values with your real keys:

```bash
modal secret create vizard-clipper-secrets \
  VIZARD_API_KEY=your_vizard_api_key \
  TELEGRAM_BOT_TOKEN=your_telegram_bot_token \
  AIRTABLE_PAT=your_airtable_personal_access_token \
  AIRTABLE_BASE_ID=your_airtable_base_id \
  AIRTABLE_TABLE_NAME=shortsRobo \
  BLOTATO_API_KEY=your_blotato_api_key \
  BLOTATO_YOUTUBE_ACCOUNT_ID=your_blotato_youtube_account_id
```

> **Tip:** If you want to restrict the bot to your Telegram account only, add `TELEGRAM_CHAT_ID=your_chat_id` too.

## Step 5: Deploy

Navigate to the `tools/` folder and run:

```bash
modal deploy vizard_clipper.py
```

The output will show your endpoints:
```
✓ Created telegram_webhook => https://your-username--vizard-clipper-telegram-webhook.modal.run
✓ Created health => https://your-username--vizard-clipper-health.modal.run
```

**Copy the `telegram_webhook` URL** — you'll need it next.

## Step 6: Register Telegram Webhook

Open this URL in your browser (replace both values):

```
https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_WEBHOOK_URL>
```

You should see:
```json
{"ok": true, "result": true, "description": "Webhook was set"}
```

## Step 7: Test!

1. Open your bot on Telegram
2. Send `/start` — you should get a welcome message
3. Send a YouTube URL — the pipeline starts!

## Useful Commands

| Command | What It Does |
|---------|-------------|
| `modal deploy vizard_clipper.py` | Deploy (or update) the bot |
| `modal app logs vizard-clipper` | View live logs |
| `modal app list` | List your deployed apps |
| `modal secret list` | List your secrets |

## Troubleshooting

**"Secret not found" error:**
- Make sure the secret is named exactly `vizard-clipper-secrets`
- Run `modal secret list` to check

**Deploy fails with import error:**
- Make sure you're in the `tools/` directory
- Run `pip install modal` to update

**Webhook returns errors:**
- Check Modal logs: `modal app logs vizard-clipper`
- Verify all API keys in the secret are correct

---

*All set up?* Send a YouTube URL to your bot and watch the magic! 🎬
