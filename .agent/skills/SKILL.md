---
name: Modal Serverless Deployment
description: Deploy Python functions to Modal.com as serverless apps — supports cron schedules, webhooks, persistent state, and secrets management
---

# Modal.com Serverless Deployment Skill

When tasked with deploying automation, background jobs, scheduled tasks, or serverless APIs, use Modal.com as the cloud compute platform. Modal runs Python functions in the cloud with zero infrastructure management.

## Why Modal

- **No server management** — just write Python, deploy, done
- **Pay per use** — only charged while your code runs (~$0.01/run for lightweight jobs)
- **Built-in cron** — schedule functions with `modal.Cron("0 10 * * *")`
- **Persistent storage** — `modal.Volume` survives between runs
- **Secrets management** — API keys stored securely in Modal's vault
- **No always-on cost** — unlike a VPS, it sleeps when idle

## Prerequisites

The Modal CLI must be installed and authenticated before deployment:

```powershell
# Install
pip install modal

# Authenticate (opens browser — user must approve)
python -m modal setup
```

> **Note:** On Windows, `modal` may not be on PATH. Always use `python -m modal` instead of bare `modal`.

After auth, credentials are saved to `~/.modal.toml`. Check the active workspace:
```powershell
python -m modal profile current
```

---

## Core Concepts

### 1. App Structure

Every Modal deployment starts with an `app` and a container `image`:

```python
import modal

app = modal.App("my-app-name")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("requests", "feedparser")  # Add pip packages
    .apt_install("ffmpeg")                   # Add system packages (if needed)
)
```

### 2. Functions

Decorate Python functions to run in the cloud:

```python
@app.function(image=image, timeout=300)
def my_task(input_data):
    """This runs in Modal's cloud, not on your machine."""
    import requests
    result = requests.get(input_data["url"])
    return {"status": "done", "length": len(result.text)}
```

### 3. Secrets

**Never hardcode API keys.** Store them as Modal Secrets:

```powershell
# Create a secret group
python -m modal secret create my-app-secrets `
  API_KEY=your_key_here `
  OTHER_KEY=another_key

# List existing secrets
python -m modal secret list
```

Reference in code:
```python
secret = modal.Secret.from_name("my-app-secrets")

@app.function(image=image, secrets=[secret])
def my_task():
    import os
    key = os.environ["API_KEY"]  # Available as env vars
```

### 4. Persistent Volumes (State Between Runs)

Use a Volume to remember things across executions (e.g., "which videos have I already processed?"):

```python
volume = modal.Volume.from_name("my-app-state", create_if_missing=True)

@app.function(image=image, volumes={"/state": volume})
def my_task():
    import json
    
    # Read previous state
    try:
        with open("/state/processed.json", "r") as f:
            processed = json.load(f)
    except FileNotFoundError:
        processed = []
    
    # Do work...
    processed.append("new_item_id")
    
    # Save state
    with open("/state/processed.json", "w") as f:
        json.dump(processed, f)
    
    volume.commit()  # IMPORTANT: must commit to persist
```

> **Critical:** Always call `volume.commit()` after writing files, or changes will be lost.

### 5. Cron Scheduling

Run functions on a schedule — the most common pattern for automation:

```python
@app.function(
    image=image,
    secrets=[secret],
    volumes={"/state": volume},
    schedule=modal.Cron("0 10 * * *"),  # 10:00 AM UTC daily
    timeout=600,
)
def scheduled_run():
    """Runs automatically every day."""
    return my_task.local()  # Call other functions with .local()
```

**Common cron expressions:**
| Expression | Schedule |
|-----------|----------|
| `0 10 * * *` | Daily at 10:00 AM UTC |
| `0 */6 * * *` | Every 6 hours |
| `0 9 * * 1` | Every Monday at 9 AM UTC |
| `*/30 * * * *` | Every 30 minutes |
| `0 22 * * *` | Daily at 10 PM UTC (9 AM AEDT) |

### 6. Web Endpoints (Webhooks)

Expose HTTP endpoints for external triggers:

```python
@app.function(image=image)
@modal.web_endpoint(method="POST")
def webhook(data: dict):
    """Callable via HTTP POST from n8n, Zapier, or any HTTP client."""
    result = my_task.remote(data)
    return {"status": "ok", "result": result}
```

### 7. Local Entrypoint (Manual Testing)

Always include a way to manually trigger the pipeline:

```python
@app.local_entrypoint()
def main():
    """Run manually: python -m modal run my_app.py"""
    result = my_task.remote()
    print(f"Result: {result}")
```

---

## Deployment Commands

| Command | What It Does |
|---------|-------------|
| `python -m modal deploy my_app.py` | **Deploy** (creates/updates the cloud app + starts cron) |
| `python -m modal run my_app.py` | **Test run** (executes the `@app.local_entrypoint()` once) |
| `python -m modal app logs my-app-name` | **View logs** (live tail of executions) |
| `python -m modal app list` | **List** all deployed apps |
| `python -m modal app stop my-app-name` | **Stop/pause** the app (disables cron) |
| `python -m modal secret list` | **List** stored secrets |
| `python -m modal secret create name K=V` | **Create** a new secret |

---

## Deployment Checklist

Before deploying any Modal app, verify:

1. ☐ `python -m modal` works (installed + authenticated)
2. ☐ All API keys are stored in a Modal Secret (never in code)
3. ☐ The `image` has all required `pip_install` and `apt_install` packages
4. ☐ Functions that need state use a `Volume` with `volume.commit()`
5. ☐ A `@app.local_entrypoint()` exists for manual testing
6. ☐ The cron expression matches the desired schedule + timezone
7. ☐ `timeout` is set high enough for the longest expected execution

---

## Common Patterns

### Pattern: Daily Content Pipeline
```python
@app.function(image=image, secrets=[secret], volumes={"/state": volume},
              schedule=modal.Cron("0 10 * * *"), timeout=600)
def daily_pipeline():
    # 1. Check source for new content (RSS, API, etc.)
    # 2. Skip if already processed (check Volume state)
    # 3. Process content (transcript, summarize, generate)
    # 4. Publish (Blotato, API call, webhook)
    # 5. Save state (Volume commit)
    pass
```

### Pattern: Webhook Trigger (from n8n or external)
```python
@app.function(image=image, secrets=[secret])
@modal.web_endpoint(method="POST")
def trigger(payload: dict):
    video_url = payload["url"]
    result = process_video.remote(video_url)
    return {"status": "ok", "result_url": result}
```

### Pattern: Heavy Compute (GPU / Video Processing)
```python
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")
    .pip_install("yt-dlp")
)

@app.function(image=image, gpu="T4", timeout=1800)
def process_video(url):
    # Runs on a GPU-enabled machine
    pass
```

---

## Error Handling Best Practices

1. **Always wrap API calls in try/except** — Modal retries on crash, so make functions idempotent
2. **Use the Volume as a checkpoint** — if a 5-step pipeline fails at step 3, save progress so the next run can resume
3. **Set reasonable timeouts** — default is 300s, but video processing may need 600-1800s
4. **Log generously** — `print()` statements show up in `modal app logs`

---

## Cost Reference

| Resource | Cost |
|----------|------|
| CPU (per second) | ~$0.000036 |
| Memory (per GB/s) | ~$0.000005 |
| Typical 2-min pipeline run | ~$0.01 |
| Typical 30-day daily automation | ~$0.30/month |
| GPU (T4, per second) | ~$0.00059 |
