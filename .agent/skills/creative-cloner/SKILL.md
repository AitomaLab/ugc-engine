---
name: Creative Cloner AI Agent
description: Analyze viral videos and recreate them with new products/characters using AI (NanoBanana Pro + Kling 2.6)
---

# 🎬 Creative Cloner AI Agent Skill

Turn any viral video into YOUR branded content using AI! This skill helps you analyze viral ads and recreate them with your own products, characters, and branding.

---

## 📁 Folder Structure

| Folder | Purpose |
|--------|---------|
| `inputs/` | Your project folders with videos and images |
| `tools/` | Python scripts (don't touch these!) |
| `outputs/` | Your finished videos appear here |
| `.agent/` | Settings and this skill file |

---

## ⚠️ CRITICAL RULES — YOU MUST FOLLOW THESE

---

### 🛑 Rule 1: STOP AT EVERY CHECKPOINT — Never Auto-Proceed

> ⛔ **NEVER run multiple phases without explicit user approval!**
> 
> ⛔ **NEVER use `generate_full_ad.py` — it skips checkpoints!**

You MUST pause and wait for the user to say "yes" or "proceed" at EACH of these checkpoints:

| Checkpoint | What To Show | What To Ask |
|------------|--------------|-------------|
| 1️⃣ After analyzing video | Scene breakdown (SEALCaM) | "Does this look right? Ready to write prompts?" |
| 2️⃣ After writing prompts | Image & video prompts + costs | "Ready to generate images? This will cost $X" |
| 3️⃣ After generating images | The actual images | "Here are the images. Ready to generate videos? This will cost $X" |
| 4️⃣ After generating videos | The actual videos | "Here are the videos. Ready to add music and combine?" |

**What counts as approval?**
- ✅ "Yes", "Proceed", "Let's go", "Do it", "Generate"
- ❌ "Let's do 10 seconds" = NOT approval to run the whole pipeline, just a parameter change

**If in doubt, ASK!**

---

### 💰 Rule 2: Show Costs BEFORE Generating
Always tell the user how much things will cost BEFORE doing them:
- Images: **$0.09 each** (NanoBanana Pro)
- Videos: **$0.28 each** (Kling 2.6, 5 seconds) / **$0.56** (10 seconds)
- Music: **~$0.10** (Suno)

---

### 📂 Rule 3: Use the Right Folders
- Look for project files in `inputs/`
- Save final videos to `outputs/`
- Use scripts from `tools/`
- Load API keys from `.agent/.env`

---

### 🐍 Rule 4: Use the Python Scripts (ONE AT A TIME!)
**Available scripts in `tools/` folder:**

| Script | What It Does | When To Use |
|--------|--------------|-------------|
| `analyze_video.py` | Analyzes a video and breaks it into scenes | Checkpoint 1 |
| `generate_images.py` | Creates images from prompts (logs to Airtable) | Checkpoint 3 (after approval) |
| `generate_videos.py` | Turns images into video clips (logs to Airtable) | Checkpoint 4 (after approval) |
| `generate_music.py` | Generates background music via Suno | Checkpoint 5 (after approval) |
| `combine_all.py` | Combines clips + adds music with FFmpeg | Final step (after approval) |

---

### 📤 Rule 5: Reference Image Uploads

For reference images (product photos, character images) that need to go TO Kie.ai:
- **Use Kie.ai file upload** via `generate_images.py` → `upload_to_kie(filepath)`
- Uses the same KIE_API_KEY - no extra keys needed!
- Files are temporary (3 days) but that's fine since we use them immediately

For generated images/videos FROM Kie.ai:
- **Log directly to Airtable** using the result URL
- Airtable accepts URLs as attachments

---

### 📊 Rule 6: Log Everything to Airtable

At each step, log to the **Scenes** table:

| When | What to Log | Field |
|------|-------------|-------|
| After writing prompts | Create scene record with prompts | `start_image_prompt`, `video_prompt` |
| After generating image | Attach the generated image | `start_image` |
| After generating video | Attach the generated video | `scene_video` |

---

### 🚨 Rule 7: NEVER Auto-Retry Kie AI Errors

> ⛔ **If Kie AI (image or video generation) fails, DO NOT automatically retry!**
> 
> ⛔ **Retrying without asking can create duplicate images/videos and waste money!**

When a Kie AI error occurs (from `generate_images.py` or `generate_videos.py`):

1. **STOP immediately** — do not attempt to retry on your own
2. **Explain the error in simple terms** — translate technical errors into plain English:
   | Error Type | Simple Explanation |
   |------------|--------------------|
   | Timeout | "Kie AI is taking longer than expected. It might still be working in the background." |
   | "fail" state | "Kie AI couldn't complete this request. The prompt might need adjusting." |
   | Network/API error | "There was a connection issue with Kie AI. This is usually temporary." |
   | "unknown" state | "Kie AI is in an unusual state. The request might still be processing." |
   
3. **Give the user options** — always ask:
   > "❓ What would you like to do?"
   > 1. **Try again** — I'll send a fresh request (this will cost another generation)
   > 2. **Check Kie AI first** — Go to [kie.ai](https://kie.ai) and check your recent jobs to see if it actually worked
   > 3. **Skip this scene** — Move on to the next one

4. **Wait for explicit approval** before retrying

**Why this matters:** Sometimes Kie AI reports an error but the generation actually succeeded. By checking first, you avoid paying twice for the same image!

---

## 🎯 The SEALCaM Framework

When analyzing videos, describe each scene using these 6 elements:

| Letter | Meaning | Example |
|--------|---------|---------|
| **S** | Subject | "Cute fox cub holding a bottle" |
| **E** | Environment | "Mossy forest floor with sunlight" |
| **A** | Action | "Fox smiles at camera" |
| **L** | Lighting | "Soft golden natural light" |
| **Ca** | Camera | "Close-up, looking down at subject" |
| **M** | Metatokens | "cinematic, photorealistic, 4K" |

---

## 📋 Step-by-Step Process

### Step 1: Analyze the Video
Upload the reference video to Gemini and get a breakdown of each scene.

**🛑 CHECKPOINT: Show the scene breakdown and ask "Does this look right?"**

### Step 2: Create Prompts & Log to Airtable
Write image and video prompts for each scene, including the user's product.
**Log the prompts to Airtable (Scenes table).**

**🛑 CHECKPOINT: Show prompts and costs, ask "Ready to generate images?"**

Show: 
- ⏱️ Time: ~30-60 seconds per image
- 💰 Cost: $0.09 per image

### Step 3: Generate Images & Log to Airtable
Use NanoBanana Pro to create the starting image for each scene.
**Log the generated image to Airtable (start_image field).**

**🛑 CHECKPOINT: Show images and ask "Ready to generate videos?"**

Show:
- ⏱️ Time: ~2-4 minutes per video
- 💰 Cost: $0.28 per video

### Step 4: Generate Videos & Log to Airtable
Use Kling 2.6 to animate each image into a 5-second video clip.
**Log the generated video to Airtable (scene_video field).**

**🛑 CHECKPOINT: Show videos and ask "Ready to add music and combine?"**

### Step 5: Add Music & Combine
Generate background music with Suno, then combine everything with FFmpeg.

### Step 6: Done! 🎉
Show the user:
- Where to find their final video
- Total cost
- Total time taken

---

## 🔧 API Details

### Image Generation (NanoBanana Pro)
```json
{
  "model": "nano-banana-pro",
  "input": {
    "prompt": "<your prompt>",
    "image_input": ["<reference_image_url>"],
    "aspect_ratio": "9:16",
    "resolution": "2K"
  }
}
```

### Video Generation (Kling 2.6)
```json
{
  "model": "kling-2.6/image-to-video",
  "input": {
    "prompt": "<motion prompt>",
    "image_urls": ["<start_image_url>"],
    "duration": "5",
    "sound": false
  }
}
```

---

## 💡 Tips for Great Results

1. **Use clear reference videos** - 5-15 seconds works best
2. **High-quality product images** - The clearer, the better!
3. **Check at each step** - This saves money on bad generations
4. **Be specific** - Tell me exactly what you want changed

---

## 📝 Example Request

> "Recreate this viral cat video but replace the coffee cup with my T2 tea bottle. Keep the same cute animals and forest setting!"

I'll then:
1. Analyze the video → Show you the scenes → Wait for OK
2. Write prompts with your product → Log to Airtable → Show you → Wait for OK  
3. Generate images → Log to Airtable → Show you → Wait for OK
4. Generate videos → Log to Airtable → Combine with music → Done!

---

## 📊 Airtable Database Structure

You need an Airtable base with the **Scenes** table:

### Table: Scenes
| Field | Type | Description |
|-------|------|-------------|
| Project Name | Text | Groups scenes by project |
| scene | Text | "Scene 1 - Title" |
| start_image_prompt | Long Text | Image generation prompt |
| video_prompt | Long Text | Video motion prompt |
| start_image | Attachment | Generated starting image |
| scene_video | Attachment | Generated video clip |

---

## 🚀 Quick Start

1. Put your reference video in `inputs/your-project-name/`
2. Add your product image to the same folder
3. Tell me what you want to create!

Happy creating! 🎬
