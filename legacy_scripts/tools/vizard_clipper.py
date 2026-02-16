"""
Vizard Clipper + Blotato Scheduler — Combined Modal Bot

Single Telegram bot that handles two workflows:
  • YouTube URL → Vizard AI clip generation → Airtable
  • "done reviewing" → Airtable approved clips → Blotato → mark Ready

Deploy:   modal deploy vizard_clipper.py
Register: modal run vizard_clipper.py (prints webhook setup URL)

Secrets required (Modal Secret: "vizard-clipper-secrets"):
    VIZARD_API_KEY
    TELEGRAM_BOT_TOKEN
    AIRTABLE_PAT
    AIRTABLE_BASE_ID
    AIRTABLE_TABLE_NAME
    BLOTATO_API_KEY
    BLOTATO_YOUTUBE_ACCOUNT_ID

Optional secrets:
    VIZARD_TEMPLATE_ID    — Vizard template ID for clip styling (omit for Vizard defaults)
    VIZARD_LANG           — Language code for subtitles (default: "en")
"""

import modal
import os
import time
import re
import json

# ---------------------------------------------------------------------------
# Modal App & Image
# ---------------------------------------------------------------------------
app = modal.App("vizard-clipper")

image = modal.Image.debian_slim(python_version="3.11").pip_install("requests", "fastapi[standard]")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
VIZARD_CREATE_URL = "https://elb-api.vizard.ai/hvizard-server-front/open-api/v1/project/create"
VIZARD_QUERY_URL = "https://elb-api.vizard.ai/hvizard-server-front/open-api/v1/project/query"
AIRTABLE_API_URL = "https://api.airtable.com/v0"
BLOTATO_API_URL = "https://backend.blotato.com/v2/posts"
TELEGRAM_API_URL = "https://api.telegram.org/bot"

POLL_INTERVAL = 60       # seconds between Vizard status checks
POLL_TIMEOUT = 1800      # 30 minutes max wait


# ---------------------------------------------------------------------------
# Shared Helpers
# ---------------------------------------------------------------------------

def send_telegram_message(bot_token: str, chat_id: str, text: str):
    """Send a message via Telegram Bot API."""
    import requests
    url = f"{TELEGRAM_API_URL}{bot_token}/sendMessage"
    resp = requests.post(url, json={
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    })
    result = resp.json()
    if not result.get("ok"):
        print(f"Telegram send failed: {result}")
    return result


def extract_youtube_url(text: str) -> str | None:
    """Extract a YouTube URL from message text."""
    patterns = [
        r'(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+(?:&[\w=%-]*)*)',
        r'(https?://youtu\.be/[\w-]+)',
        r'(https?://(?:www\.)?youtube\.com/shorts/[\w-]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


# ---------------------------------------------------------------------------
# Vizard Clipping Helpers
# ---------------------------------------------------------------------------

def submit_to_vizard(api_key: str, youtube_url: str, max_clips: int = None) -> dict:
    """
    Submit YouTube URL to Vizard for clipping.
    If max_clips is None, Vizard generates as many clips as it can.
    Returns dict with projectId and projectName.
    """
    import requests

    # Read optional config from environment
    template_id = os.environ.get("VIZARD_TEMPLATE_ID")
    lang = os.environ.get("VIZARD_LANG", "en")

    payload = {
        "videoUrl": youtube_url,
        "videoType": 2,          # 2 = YouTube
        "lang": lang,
    }
    if template_id:
        payload["templateId"] = int(template_id)
    if max_clips is not None:
        payload["maxClipNumber"] = max_clips

    resp = requests.post(
        VIZARD_CREATE_URL,
        headers={
            "Content-Type": "application/json",
            "VIZARDAI_API_KEY": api_key,
        },
        json=payload,
    )
    data = resp.json()
    print(f"Vizard create response: {json.dumps(data, indent=2)}")

    if "projectId" not in data:
        raise RuntimeError(f"Vizard project creation failed: {data}")

    return data


def poll_vizard_results(api_key: str, project_id: int) -> list:
    """
    Poll Vizard until clips are ready.
    Returns list of clip dicts (videoUrl, title, transcript, viralScore, viralReason).
    """
    import requests
    start = time.time()

    while time.time() - start < POLL_TIMEOUT:
        resp = requests.get(
            f"{VIZARD_QUERY_URL}/{project_id}",
            headers={"VIZARDAI_API_KEY": api_key},
        )
        data = resp.json()
        code = data.get("code")
        videos = data.get("videos", [])

        if code == 2000 and videos:
            print(f"Vizard done! {len(videos)} clips ready.")
            return videos

        elapsed = int(time.time() - start)
        print(f"Still processing... code={code}, elapsed={elapsed}s")
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"Vizard processing timed out after {POLL_TIMEOUT}s")


def save_clips_to_airtable(
    pat: str,
    base_id: str,
    table_name: str,
    clips: list,
    source_url: str,
) -> int:
    """
    Save each clip as a row in Airtable.
    Returns the number of records created.
    """
    import requests

    url = f"{AIRTABLE_API_URL}/{base_id}/{table_name}"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
    }

    records = []
    for clip in clips:
        record = {
            "fields": {
                "Video": [{"url": clip["videoUrl"]}],
                "Title": clip.get("title", "Untitled"),
                "Caption": clip.get("transcript", ""),
                "Viral Score": float(clip.get("viralScore", 0)),
                "Viral Reason": clip.get("viralReason", ""),
                "Source URL": source_url,
            }
        }
        records.append(record)

    # Airtable allows max 10 records per request
    created = 0
    for i in range(0, len(records), 10):
        batch = records[i : i + 10]
        resp = requests.post(url, headers=headers, json={"records": batch})

        if resp.status_code != 200:
            print(f"Airtable error (batch {i}): {resp.status_code} {resp.text}")
            raise RuntimeError(f"Airtable error: {resp.text[:500]}")

        created += len(batch)
        print(f"Airtable: saved {created}/{len(records)} records")

    return created


# ---------------------------------------------------------------------------
# Blotato Scheduling Helpers
# ---------------------------------------------------------------------------

def get_approved_clips(pat: str, base_id: str, table_name: str) -> list:
    """
    Query Airtable for rows where Status = "Approved".
    Returns list of record dicts with 'id' and 'fields'.
    """
    import requests

    url = f"{AIRTABLE_API_URL}/{base_id}/{table_name}"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
    }
    params = {
        "filterByFormula": '{Status} = "Approved"',
    }

    all_records = []
    offset = None

    while True:
        if offset:
            params["offset"] = offset

        resp = requests.get(url, headers=headers, params=params)
        if resp.status_code != 200:
            raise RuntimeError(f"Airtable query failed: {resp.text[:500]}")

        data = resp.json()
        all_records.extend(data.get("records", []))

        offset = data.get("offset")
        if not offset:
            break

    print(f"Found {len(all_records)} approved clips in Airtable")
    return all_records


def schedule_to_blotato(api_key: str, account_id: str, title: str, video_url: str, caption: str = "") -> dict:
    """
    Schedule a single clip as a YouTube Short via Blotato API.
    Uses useNextFreeSlot to auto-pick the next available schedule slot.
    """
    import requests

    description = title
    if caption:
        description = f"{title}\n\n{caption}"

    payload = {
        "post": {
            "accountId": account_id,
            "content": {
                "text": description,
                "mediaUrls": [video_url],
                "platform": "youtube",
            },
            "target": {
                "targetType": "youtube",
                "title": title,
                "privacyStatus": "public",
                "shouldNotifySubscribers": True,
            },
        },
        "useNextFreeSlot": True,
    }

    resp = requests.post(
        BLOTATO_API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    result = resp.json()
    print(f"Blotato response for '{title}': {resp.status_code} — {json.dumps(result)[:300]}")

    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Blotato scheduling failed ({resp.status_code}): {json.dumps(result)[:500]}")

    return result


def mark_as_ready(pat: str, base_id: str, table_name: str, record_id: str):
    """Update a single Airtable record's Status to 'Ready'."""
    import requests

    url = f"{AIRTABLE_API_URL}/{base_id}/{table_name}/{record_id}"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
    }

    resp = requests.patch(url, headers=headers, json={
        "fields": {"Status": "Ready"},
    })

    if resp.status_code != 200:
        raise RuntimeError(f"Airtable update failed: {resp.text[:500]}")

    print(f"Marked record {record_id} as Ready")


def extract_video_url(fields: dict) -> str | None:
    """Extract the video URL from an Airtable record's fields."""
    video_field = fields.get("Video") or fields.get("Clip URL")

    if not video_field:
        return None

    if isinstance(video_field, list) and len(video_field) > 0:
        return video_field[0].get("url")

    if isinstance(video_field, str):
        return video_field

    return None


# ---------------------------------------------------------------------------
# Modal Functions — Vizard Pipeline
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("vizard-clipper-secrets")],
    timeout=1800,  # 30 min — covers Vizard processing time
)
def process_video(youtube_url: str, chat_id: str, max_clips: int = None):
    """
    Long-running pipeline: Vizard → Airtable → Telegram notification.
    Called asynchronously from the webhook handler.
    """
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    vizard_key = os.environ["VIZARD_API_KEY"]
    airtable_pat = os.environ["AIRTABLE_PAT"]
    airtable_base = os.environ["AIRTABLE_BASE_ID"]
    airtable_table = os.environ["AIRTABLE_TABLE_NAME"]

    try:
        # Step 1: Submit to Vizard
        clip_note = f" (max {max_clips} clips)" if max_clips else " (all clips)"
        print(f"Submitting to Vizard: {youtube_url}{clip_note}")
        vizard_data = submit_to_vizard(vizard_key, youtube_url, max_clips)
        project_id = vizard_data["projectId"]

        send_telegram_message(
            bot_token, chat_id,
            f"🎬 Vizard project created (ID: {project_id}).\n"
            f"Polling every {POLL_INTERVAL}s... this takes 5-15 min."
        )

        # Step 2: Poll for results
        clips = poll_vizard_results(vizard_key, project_id)

        # Step 3: Save to Airtable
        count = save_clips_to_airtable(
            airtable_pat, airtable_base, airtable_table,
            clips, youtube_url,
        )

        # Step 4: Notify via Telegram
        airtable_link = f"https://airtable.com/{airtable_base}"
        send_telegram_message(
            bot_token, chat_id,
            f"✅ <b>Shorts are ready!</b>\n\n"
            f"📊 {count} clips generated\n"
            f"🔗 Review in Airtable: {airtable_link}\n\n"
            f"When you're done reviewing, send <code>done reviewing</code> "
            f"to schedule approved clips to Blotato."
        )

    except Exception as e:
        print(f"Pipeline error: {e}")
        send_telegram_message(
            bot_token, chat_id,
            f"❌ <b>Error processing video</b>\n\n"
            f"URL: {youtube_url}\n"
            f"Error: {str(e)[:500]}"
        )
        raise


# ---------------------------------------------------------------------------
# Modal Functions — Blotato Scheduling Pipeline
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("vizard-clipper-secrets")],
    timeout=300,  # 5 min
)
def process_scheduling(chat_id: str):
    """
    Scheduling pipeline: Airtable (approved) → Blotato → Airtable (Ready) → Telegram.
    Called asynchronously from the webhook handler.
    """
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    airtable_pat = os.environ["AIRTABLE_PAT"]
    airtable_base = os.environ["AIRTABLE_BASE_ID"]
    airtable_table = os.environ["AIRTABLE_TABLE_NAME"]
    blotato_key = os.environ["BLOTATO_API_KEY"]
    blotato_account = os.environ["BLOTATO_YOUTUBE_ACCOUNT_ID"]

    try:
        # Step 1: Get approved clips from Airtable
        records = get_approved_clips(airtable_pat, airtable_base, airtable_table)

        if not records:
            send_telegram_message(
                bot_token, chat_id,
                "🤷 <b>No approved clips found.</b>\n\n"
                "Make sure at least one row in Airtable has Status = \"Approved\"."
            )
            return

        send_telegram_message(
            bot_token, chat_id,
            f"📋 Found <b>{len(records)} approved clip(s)</b>. Scheduling to Blotato now..."
        )

        # Step 2 & 3: Schedule each clip and mark as Ready
        scheduled = 0
        errors = []

        for record in records:
            record_id = record["id"]
            fields = record["fields"]
            title = fields.get("Title", "Untitled Short")
            caption = fields.get("Caption", "")
            video_url = extract_video_url(fields)

            if not video_url:
                error_msg = f"⚠️ Skipped '{title}' — no video URL found"
                print(error_msg)
                errors.append(error_msg)
                continue

            try:
                schedule_to_blotato(blotato_key, blotato_account, title, video_url, caption)
                mark_as_ready(airtable_pat, airtable_base, airtable_table, record_id)
                scheduled += 1
            except Exception as e:
                error_msg = f"⚠️ Failed '{title}': {str(e)[:200]}"
                print(error_msg)
                errors.append(error_msg)

        # Step 4: Send summary
        summary = f"✅ <b>{scheduled}/{len(records)} clips scheduled to Blotato and marked Ready!</b>"

        if errors:
            error_text = "\n".join(errors)
            summary += f"\n\n<b>Issues:</b>\n{error_text}"

        send_telegram_message(bot_token, chat_id, summary)

    except Exception as e:
        print(f"Pipeline error: {e}")
        send_telegram_message(
            bot_token, chat_id,
            f"❌ <b>Error during scheduling</b>\n\nError: {str(e)[:500]}"
        )
        raise


# ---------------------------------------------------------------------------
# Unified Telegram Webhook
# ---------------------------------------------------------------------------

@app.function(
    image=image,
    secrets=[modal.Secret.from_name("vizard-clipper-secrets")],
    timeout=30,
)
@modal.web_endpoint(method="POST")
def telegram_webhook(request: dict) -> dict:
    """
    Unified Telegram webhook handler.
    Routes messages based on content:
      • YouTube URL → Vizard clipping pipeline
      • "done reviewing" → Blotato scheduling pipeline
      • /start → help message
    """
    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]

    message = request.get("message", {})
    text = message.get("text", "")
    chat_id = str(message.get("chat", {}).get("id", ""))

    if not text or not chat_id:
        return {"ok": True}

    # Security: only process messages from the authorized user
    allowed_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "")
    if allowed_chat_id and chat_id != allowed_chat_id:
        print(f"Ignoring message from unauthorized chat_id: {chat_id}")
        return {"ok": True}

    # --- /start command ---
    if text.strip() == "/start":
        send_telegram_message(
            bot_token, chat_id,
            "👋 <b>Clipper Bot</b>\n\n"
            "I handle two workflows:\n\n"
            "<b>1. Generate clips:</b>\n"
            "Send a YouTube URL → AI clips via Vizard → saved to Airtable\n"
            "  e.g. <code>https://youtube.com/watch?v=...</code>\n"
            "  or <code>5 https://youtube.com/watch?v=...</code> for max 5 clips\n\n"
            "<b>2. Schedule approved clips:</b>\n"
            "Send <code>done reviewing</code> → approved clips → Blotato → YouTube Shorts"
        )
        return {"ok": True}

    # --- "done reviewing" → Blotato scheduling ---
    if "done reviewing" in text.lower():
        send_telegram_message(
            bot_token, chat_id,
            "⏳ <b>On it!</b> Checking Airtable for approved clips..."
        )
        process_scheduling.spawn(chat_id)
        return {"ok": True}

    # --- YouTube URL → Vizard clipping ---
    youtube_url = extract_youtube_url(text)
    if youtube_url:
        max_clips = None
        numbers = re.findall(r'\b(\d{1,3})\b', text.replace(youtube_url, ''))
        if numbers:
            max_clips = int(numbers[0])

        clip_note = f" (max {max_clips} clips)" if max_clips else " (all clips)"
        send_telegram_message(
            bot_token, chat_id,
            f"⏳ <b>Processing:</b> {youtube_url}\n"
            f"🎯 Mode:{clip_note}\n\n"
            f"This typically takes 5-15 minutes. I'll ping you when the shorts are ready!"
        )
        process_video.spawn(youtube_url, chat_id, max_clips)
        return {"ok": True}

    # --- Unknown message ---
    send_telegram_message(
        bot_token, chat_id,
        "🤔 I didn't catch that. Here's what I respond to:\n\n"
        "• <b>YouTube URL</b> → generate clips\n"
        "• <code>done reviewing</code> → schedule approved clips to Blotato\n"
        "• <code>/start</code> → show help"
    )
    return {"ok": True}


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("vizard-clipper-secrets")],
)
@modal.web_endpoint(method="GET")
def health() -> dict:
    """Health check endpoint."""
    return {"status": "ok", "service": "vizard-clipper", "version": "2.0"}


# ---------------------------------------------------------------------------
# Local Entrypoint
# ---------------------------------------------------------------------------

@app.local_entrypoint()
def main():
    """
    After deploying, register the Telegram webhook:
        modal deploy vizard_clipper.py

    Then set the webhook URL with Telegram.
    """
    print("=" * 60)
    print("Vizard Clipper + Blotato Scheduler — Deployed!")
    print("=" * 60)
    print()
    print("This bot handles TWO workflows:")
    print("  • YouTube URL → Vizard clips → Airtable")
    print("  • 'done reviewing' → Airtable approved → Blotato → Ready")
    print()
    print("Next steps:")
    print("1. Run: modal deploy vizard_clipper.py")
    print("2. Copy the telegram_webhook URL from the deploy output")
    print("3. Register it with Telegram by visiting this URL in your browser:")
    print()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "<YOUR_BOT_TOKEN>")
    print(f"   https://api.telegram.org/bot{bot_token}/setWebhook?url=<WEBHOOK_URL>")
    print()
    print("Replace <WEBHOOK_URL> with the telegram_webhook URL from step 2.")
    print()
    print("4. Send a YouTube URL or 'done reviewing' to your bot — done!")
