# Telegram Bot Setup

Create your clipper bot in 2 minutes.

## Step 1: Talk to BotFather

1. Open **Telegram** (app or web)
2. Search for **@BotFather** (the official bot creator)
3. Send `/start` if it's your first time
4. Send `/newbot`

## Step 2: Name Your Bot

BotFather will ask two things:

1. **Display name** — anything you want
   - Example: `My Clipper Bot`

2. **Username** — must end in `bot` and be unique
   - Example: `my_shorts_clipper_bot`

## Step 3: Save Your Token

BotFather will reply with a message like:

```
Done! Congratulations on your new bot. You will find it at t.me/my_shorts_clipper_bot.

Use this token to access the HTTP API:
1234567890:ABCdefGHIjklMNOpqrSTUvwx-YZ1234567890
```

**Copy that token** — you'll need it for the Modal secret.

> ⚠️ **Keep this token private.** Anyone with it can control your bot.

## Step 4: (Optional) Get Your Chat ID

To restrict the bot so only YOU can use it:

1. Send any message to your new bot
2. Visit: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
3. Find `"chat":{"id":123456789}` in the response
4. That number is your **Chat ID**

Add it as `TELEGRAM_CHAT_ID` in your Modal secret for security.

---

*Next step:* Get your Vizard API key → [vizard-setup.md](vizard-setup.md)
