# Creative Cloner AI Agent (R54)
## By Jay E from RoboNuggets
https://robonuggets.com

Turn any video into your branded content using AI (NanoBanana Pro + Kling 2.6).

---

## Getting Started
TIP: Just ask Antigravity to "Initiate the agent" and it will guide you on these steps.

### Step 1: Set Up Your API Keys

1. Copy `.agent/.env.example` to `.agent/.env`
2. Add your API keys to the `.env` file

**Need help finding your API keys?**  
→ [Go to the our central page on how to set up your API keys and credential for the tools we'll use](https://www.skool.com/robonuggets/classroom/7e984827?md=ad0801c685cd4e168253d659dbbfc3dd)

### Step 2: Set Up Airtable

Create an Airtable base with a **Scenes** table containing these fields:
- `Project Name` (Text)
- `scene` (Text)
- `start_image_prompt` (Long Text)
- `video_prompt` (Long Text)
- `start_image` (Attachment)
- `scene_video` (Attachment)

### Step 3: Create Your Project

1. Create a new folder inside `inputs/` (e.g., `inputs/my-first-ad/`)
2. Add your reference video (the viral video you want to recreate)
3. Add your product or character images
4. Tell Antigravity what you want to create!

Antigravity will handle the rest — installing packages, running scripts, and generating your video.

---

## Need Help?

→ [Visit the "Where to Get Help" page in our community](https://www.skool.com/robonuggets/classroom/7e5732ad?md=8980dd65bda84367806a0ba6047d3ddf)
