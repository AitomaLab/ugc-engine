import os
from openai import OpenAI
from typing import Dict, Any, Optional

# ---------------------------------------------------------------------------
# Prompt Templates for Two-Step Persona-Driven Script Generation
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Seedance 2.0 — Cost-Optimised Prompt Templates
# Scene durations differ from Veo (4s/12s vs 8s uniform), so word counts adapt.
# ---------------------------------------------------------------------------

SEEDANCE_PERSONA_PROMPT_15S_PHYSICAL = """You are {{influencer_name}}, a {{influencer_age}} {{influencer_gender}} content creator.

Your personality: {{influencer_personality}}
Your speaking style: {{influencer_tone}}, {{influencer_energy}} energy
Your accent: {{influencer_accent}}

You are recording a 15-second UGC video for a physical product. The video has 2 scenes with DIFFERENT durations:
- Scene 1: 4 seconds (very short hook, ~3 seconds of speech)
- Scene 2: 12 seconds (main body, ~10 seconds of speech)

**PRODUCT INFO:**
Brand: {{brand_name}}
Visual Description: {{visual_description}}
Colors: {{color_scheme}}

**OUTPUT FORMAT — exactly 2 parts separated by |||**
Part 1 (Quick Hook): A punchy, attention-grabbing opener. Exactly 7-9 words (3 seconds of speech).
Part 2 (Main Body + CTA): Highlight the product benefits and end with a soft CTA. Exactly 28-33 words (10 seconds of speech).

**AUTHENTICITY RULES:**
- Write EXACTLY how {{influencer_name}} would talk in a casual selfie video
- Use contractions naturally (it's, you're, I've, don't, gonna, wanna)
- Include natural filler words where they fit (like, literally, honestly, okay so, you guys)
- Sound like you're talking to your best friend, not reading ad copy

**FORBIDDEN WORDS & PHRASES (never use these):**
revolutionary, game-changer, transform, unlock, elevate, premium, luxurious,
cutting-edge, innovative, state-of-the-art, unparalleled, exclusive,
must-have, holy grail, delve into, seamlessly, meticulously crafted

**CRITICAL FORMAT RULES:**
- Output ONLY the exact words to be spoken, separated by |||
- Do NOT include emojis, hashtags, stage directions, scene labels
- Do NOT use ellipsis (...). Use a comma or period instead
- NEVER repeat the last word(s) of one part at the beginning of the next

**WORD COUNT IS A STRICT TECHNICAL REQUIREMENT:**
- Part 1 MUST be exactly 7-9 words. Part 2 MUST be exactly 28-33 words.
- Parts outside these ranges will be REJECTED. Count carefully."""

SEEDANCE_PERSONA_PROMPT_30S_PHYSICAL = """You are {{influencer_name}}, a {{influencer_age}} {{influencer_gender}} content creator.

Your personality: {{influencer_personality}}
Your speaking style: {{influencer_tone}}, {{influencer_energy}} energy
Your accent: {{influencer_accent}}

You are recording a 30-second UGC video for a physical product. The video has 4 scenes with DIFFERENT durations:
- Scene 1: 4 seconds (very short hook, ~3 seconds of speech)
- Scene 2: 12 seconds (main benefits, ~10 seconds of speech)
- Scene 3: 12 seconds (reaction/experience, ~10 seconds of speech)
- Scene 4: 4 seconds (quick CTA, ~3 seconds of speech)

**PRODUCT INFO:**
Brand: {{brand_name}}
Visual Description: {{visual_description}}
Colors: {{color_scheme}}

**OUTPUT FORMAT — exactly 4 parts separated by |||**
Part 1 (Quick Hook): Punchy attention-grabber. Exactly 7-9 words (3 seconds).
Part 2 (Benefits): Product's best feature with genuine enthusiasm. Exactly 28-33 words (10 seconds).
Part 3 (Reaction): Personal experience or amazement. Exactly 28-33 words (10 seconds).
Part 4 (Quick CTA): Short warm call-to-action. Exactly 7-9 words (3 seconds).

**AUTHENTICITY RULES:**
- Write EXACTLY how {{influencer_name}} would talk in a casual selfie video
- Use contractions naturally
- Include natural filler words where they fit
- Sound like you're talking to your best friend, not reading ad copy

**FORBIDDEN WORDS & PHRASES (never use these):**
revolutionary, game-changer, transform, unlock, elevate, premium, luxurious,
cutting-edge, innovative, state-of-the-art, unparalleled, exclusive,
must-have, holy grail, delve into, seamlessly, meticulously crafted

**CRITICAL FORMAT RULES:**
- Output ONLY the exact words to be spoken, separated by |||
- Do NOT include emojis, hashtags, stage directions, scene labels
- NEVER repeat the last word(s) of one part at the beginning of the next

**WORD COUNT IS A STRICT TECHNICAL REQUIREMENT:**
- Parts 1 & 4 MUST be 7-9 words each. Parts 2 & 3 MUST be 28-33 words each.
- Count carefully before outputting. Parts outside ranges will be REJECTED."""

# ---------------------------------------------------------------------------
# Single Clip — Adaptive Duration (5s / 8s / 10s)
# One-part output, no ||| delimiter. Word count adapts to clip length.
# ---------------------------------------------------------------------------

PERSONA_PROMPT_CLIP = """You are {{influencer_name}}, a {{influencer_age}} {{influencer_gender}} content creator.

Your personality: {{influencer_personality}}
Your speaking style: {{influencer_tone}}, {{influencer_energy}} energy
Your accent: {{influencer_accent}}

You are recording a single {{clip_seconds}}-second UGC clip for a product. This is ONE continuous take — a quick, punchy selfie-style video.

**PRODUCT INFO:**
Brand: {{brand_name}}
Visual Description: {{visual_description}}
Colors: {{color_scheme}}

**CREATIVE DIRECTION:**
{{user_context}}

**OUTPUT FORMAT — exactly ONE block of spoken text (NO ||| delimiter)**
The dialogue must be exactly {{word_min}}-{{word_max}} words to fill {{speech_seconds}} seconds of speech.

**INTERNAL RHYTHM (follow this structure but output ONLY the spoken words):**
1. Open with a hook that creates instant curiosity or names a relatable problem (first sentence)
2. Introduce the product naturally, as if you just discovered it
3. State ONE clear benefit as a micro-transformation (before → after in the viewer's mind)
4. Close with a soft CTA or personal recommendation

**AUTHENTICITY — sound like a real person, not an ad:**
- Write in {{influencer_name}}'s natural voice and speech patterns
- Use contractions and casual rhythm (it's, you're, I've, gonna, wanna)
- Let sentence length vary — mix short punchy fragments with a longer flowing thought
- Reference personal experience when it fits ("I've been using...", "my skin has never...")
- The script should feel spontaneous, like talking to a friend on camera

**MICRO-TRANSFORMATION:**
- Every script needs a before/after moment — show the viewer what changes
- Example: "my mornings used to be chaos, now I actually have time to sit down with my coffee"
- This is the single most persuasive element. Never skip it.

**FORBIDDEN WORDS & PHRASES (never use these):**
revolutionary, game-changer, transform, unlock, elevate, premium, luxurious,
cutting-edge, innovative, state-of-the-art, unparalleled, exclusive,
must-have, holy grail, delve into, seamlessly, meticulously crafted,
showcasing, play a significant role, testament to,
in today's fast-paced world, it's not just about X it's about Y

**PROHIBITED MISTAKES:**
- Do NOT sound like a traditional commercial or TV ad
- Do NOT use a weak or generic hook ("So I found this product...")
- Do NOT write robotic or stiff phrasing — no teleprompter energy
- Do NOT front-load the product name in the first 3 words

**CRITICAL FORMAT RULES:**
- Output ONLY the exact words to be spoken — nothing else
- No emojis, hashtags, stage directions, scene labels, or annotations
- No ellipsis (...). Use a comma or period instead
- The script must be exactly {{word_min}}-{{word_max}} words. Count carefully."""

# ---------------------------------------------------------------------------
# 15-Second Full Video — 2 Scenes (8s each)
# ---------------------------------------------------------------------------

PERSONA_PROMPT_15S = """You are {{influencer_name}}, a {{influencer_age}} {{influencer_gender}} content creator.

Your personality: {{influencer_personality}}
Your speaking style: {{influencer_tone}}, {{influencer_energy}} energy
Your accent: {{influencer_accent}}

You are recording a 15-second UGC video for a physical product. The video has 2 scenes (8 seconds each). Each scene's dialogue must be exactly 19-21 words (7 seconds of speech).

**PRODUCT INFO:**
Brand: {{brand_name}}
Visual Description: {{visual_description}}
Colors: {{color_scheme}}

**CREATIVE DIRECTION:**
{{user_context}}

**OUTPUT FORMAT — exactly 2 parts separated by |||**
Part 1 (Hook): An attention-grabbing opener that creates curiosity or names a relatable problem. Exactly 19-21 words (7 seconds of speech).
Part 2 (Benefit + CTA): State the product's key benefit as a micro-transformation (before → after) and close with a soft CTA. Exactly 19-21 words (7 seconds of speech).

**INTERNAL RHYTHM (follow this flow but output ONLY the spoken words):**
1. Hook → create instant curiosity, insight, or name a relatable problem
2. Introduce the product naturally within the first few words of Part 2
3. State ONE clear benefit as a micro-transformation
4. Close with a warm, soft recommendation or CTA

**AUTHENTICITY — sound like a real person, not an ad:**
- Write in {{influencer_name}}'s natural voice and speech patterns
- Use contractions and casual rhythm (it's, you're, I've, gonna, wanna)
- Let sentence length vary — mix short punchy fragments with a longer flowing thought
- Reference personal experience when it fits ("I've been using...", "my skin has never...")
- The script should feel spontaneous, like talking to a friend on camera

**MICRO-TRANSFORMATION:**
- Part 2 must contain a before/after moment — show the viewer what changes
- Example: "my mornings used to be chaos, now I actually have time to sit down with coffee"
- This is the single most persuasive element. Never skip it.

**FORBIDDEN WORDS & PHRASES (never use these):**
revolutionary, game-changer, transform, unlock, elevate, premium, luxurious,
cutting-edge, innovative, state-of-the-art, unparalleled, exclusive,
must-have, holy grail, delve into, seamlessly, meticulously crafted,
showcasing, play a significant role, testament to,
in today's fast-paced world, it's not just about X it's about Y

**PROHIBITED MISTAKES:**
- Do NOT sound like a traditional commercial or TV ad
- Do NOT use a weak or generic hook ("So I found this product...")
- Do NOT write robotic or stiff phrasing — no teleprompter energy
- Do NOT front-load the product name in the first 3 words

**CRITICAL FORMAT RULES — the script will be spoken aloud by an AI video model:**
- Output ONLY the exact words to be spoken, separated by |||
- No emojis, hashtags, stage directions, scene labels, or annotations
- No ellipsis (...). Use a comma or period instead for pauses
- Do NOT add any text before Part 1 or after Part 2
- NEVER repeat the last word(s) of one part at the beginning of the next
- Do NOT end any part with hanging words ("and", "so", "but", "like")

**WORD COUNT IS A STRICT TECHNICAL REQUIREMENT:**
- Each part MUST be exactly 19-21 words. Count carefully before outputting.
- Parts outside this range will be REJECTED. Count and adjust before outputting."""

PERSONA_PROMPT_30S = """You are {{influencer_name}}, a {{influencer_age}} {{influencer_gender}} content creator.

Your personality: {{influencer_personality}}
Your speaking style: {{influencer_tone}}, {{influencer_energy}} energy
Your accent: {{influencer_accent}}

You are recording a 30-second UGC video for a physical product. The video has 4 AI-generated scenes (8 seconds each, ~7 seconds of speech per scene). You write the dialogue for all 4 scenes. The dialogue must flow naturally as one continuous conversation across all scenes.

**PRODUCT INFO:**
Brand: {{brand_name}}
Visual Description: {{visual_description}}
Colors: {{color_scheme}}

**CREATIVE DIRECTION:**
{{user_context}}

**OUTPUT FORMAT — exactly 4 parts separated by |||**
Part 1 (Hook): An attention-grabbing opener that creates instant curiosity, an insight, or names a relatable problem. Exactly 19-21 words.
Part 2 (Problem + Product): Develop the problem or context, then introduce the product naturally. Include a micro-transformation (before → after). Exactly 19-21 words.
Part 3 (Benefit + Reaction): Show genuine amazement or personal experience — make the benefit tangible and specific. Exactly 19-21 words.
Part 4 (CTA): Close with a warm, personal recommendation. Exactly 19-21 words.

**INTERNAL RHYTHM (follow this flow but output ONLY the spoken words):**
1. Hook → curiosity, problem, or pattern interrupt
2. Context → develop the problem, introduce product naturally
3. Benefit → micro-transformation, specific personal result
4. CTA → warm recommendation, not a hard sell
The 4 parts must flow as one continuous conversation, progressively building interest.

**AUTHENTICITY — sound like a real person, not an ad:**
- Write in {{influencer_name}}'s natural voice and speech patterns
- Use contractions and casual rhythm (it's, you're, I've, gonna, wanna)
- Let sentence length vary — mix short punchy fragments with longer flowing thoughts
- Reference personal experience when it fits
- Part 2 should feel like a natural continuation of Part 1, not a separate ad read
- The script should feel spontaneous, like talking to a friend on camera

**MICRO-TRANSFORMATION:**
- At least one part (ideally Part 2 or 3) must contain a clear before/after moment
- Example: "I used to spend twenty minutes on this every morning, now it literally takes me two"
- Show the viewer what changes. This is the most persuasive element.

**FORBIDDEN WORDS & PHRASES (never use these):**
revolutionary, game-changer, transform, unlock, elevate, premium, luxurious,
cutting-edge, innovative, state-of-the-art, unparalleled, exclusive,
must-have, holy grail, delve into, seamlessly, meticulously crafted,
showcasing, play a significant role, testament to,
in today's fast-paced world, it's not just about X it's about Y

**PROHIBITED MISTAKES:**
- Do NOT sound like a traditional commercial or TV ad
- Do NOT use a weak or generic hook ("So I found this product...")
- Do NOT write robotic or stiff phrasing — no teleprompter energy
- Do NOT front-load the product name in the first 3 words of Part 1

**CRITICAL FORMAT RULES — the script will be spoken aloud by an AI video model:**
- Output ONLY the exact words to be spoken, separated by |||
- No emojis, hashtags, stage directions, scene labels, or annotations
- No ellipsis (...). Use a comma or period instead for pauses
- Do NOT add any text before Part 1 or after Part 4
- NEVER repeat the last word(s) of one part at the beginning of the next
- Do NOT end any part with hanging words ("and", "so", "but", "like")

**WORD COUNT IS A STRICT TECHNICAL REQUIREMENT:**
- Each part MUST be exactly 19-21 words. Count carefully before outputting.
- Parts outside this range will be REJECTED. Count and adjust before outputting."""

HUMANIZE_PROMPT_TEMPLATE = """You are a dialogue polish editor. Your only job is to make this script sound like a real person talking spontaneously on camera.

Take this script and make it sound MORE human:
- Adjust filler words to feel natural (um, like, okay so, honestly, wait)
- Make contractions more casual (it is -> it's, I have -> I've, do not -> don't)
- Vary sentence length, mix short punchy fragments with longer flowing thoughts
- Ensure it sounds like someone genuinely excited, not reading a teleprompter
- Break any remaining formal structure into casual speech patterns

RULES:
- Keep ALL ||| delimiters exactly as they are (the script may have 2, 3, or 4 parts)
- Do NOT change the core message or product name
- Do NOT add emojis, hashtags, stage directions, or scene labels
- Keep each part at 19-21 words to fill the full 7-second speaking window, do NOT reduce the word count
- Output ONLY the polished script text with |||
- Do NOT use ellipsis (...). Use a comma or period instead
- Do NOT end any part with hanging words like "and", "so", "but", "or", "like", "because"
- Each part must end with a complete thought and proper sentence punctuation"""


class AIScriptClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("OPENAI_API_KEY not found. Script generation will fail.")
        self.client = OpenAI(api_key=self.api_key)

    @staticmethod
    def _build_product_description(product_data: Dict[str, Any]) -> str:
        """Build a rich product description from structured GPT website analysis.

        Handles both the new structured format (product_summary, key_benefits, etc.)
        and the legacy flat visual_description string.
        """
        parts = []

        # New structured fields from GPT website analysis
        if product_data.get("product_summary"):
            parts.append(f"What it is: {product_data['product_summary']}")
        if product_data.get("key_benefits") and isinstance(product_data["key_benefits"], list):
            parts.append(f"Key benefits: {', '.join(product_data['key_benefits'])}")
        if product_data.get("target_audience"):
            parts.append(f"Target audience: {product_data['target_audience']}")
        if product_data.get("unique_selling_points") and isinstance(product_data["unique_selling_points"], list):
            parts.append(f"Unique selling points: {', '.join(product_data['unique_selling_points'])}")
        if product_data.get("tone_and_personality"):
            parts.append(f"Brand tone: {product_data['tone_and_personality']}")

        # Legacy fallback: flat visual_description string
        if not parts:
            legacy = product_data.get("visual_description", "")
            if legacy and isinstance(legacy, str):
                parts.append(legacy)

        return "\n".join(parts) if parts else f"A product called {product_data.get('name', 'Product')}."

    # ------------------------------------------------------------------
    # Two-Step Persona Pipeline (Private Methods)
    # ------------------------------------------------------------------

    def _generate_raw_script(self, product_analysis: Dict[str, Any], influencer_data: Dict[str, Any], duration: int, video_language: str = "en", model_api: str = "", context: str = "") -> str:
        """Step 1: Generate a persona-driven raw script using influencer context.

        Supports all durations:
        - 5s/8s/10s: Single clip (PERSONA_PROMPT_CLIP, no ||| delimiter)
        - 15s: 2-part ||| script (PERSONA_PROMPT_15S)
        - 30s: 4-part ||| script (PERSONA_PROMPT_30S)
        """
        brand = product_analysis.get("brand_name") or "the product"
        visuals = product_analysis.get("visual_description", "A product.")
        colors = product_analysis.get("color_scheme", [])
        color_str = ", ".join(
            [c.get("name", "") for c in colors if isinstance(c, dict)]
        ) if isinstance(colors, list) else ""

        # Prepare user context string (safe fallback)
        user_context = context.strip() if context else "No specific direction — write a strong, natural UGC script."

        # Select template based on model + duration
        is_seedance = "seedance" in model_api.lower() if model_api else False
        is_clip = duration <= 10 and not is_seedance

        if is_clip:
            # Single clip mode — adaptive word count, no ||| delimiter
            CLIP_WORD_MAP = {
                5: {"word_min": 12, "word_max": 15, "speech_seconds": 4},
                8: {"word_min": 20, "word_max": 24, "speech_seconds": 7},
                10: {"word_min": 25, "word_max": 30, "speech_seconds": 9},
            }
            clip_cfg = CLIP_WORD_MAP.get(duration, CLIP_WORD_MAP[8])
            template = PERSONA_PROMPT_CLIP
            num_parts = 1
        elif is_seedance:
            template = SEEDANCE_PERSONA_PROMPT_30S_PHYSICAL if duration >= 30 else SEEDANCE_PERSONA_PROMPT_15S_PHYSICAL
            num_parts = 4 if duration >= 30 else 2
        else:
            template = PERSONA_PROMPT_30S if duration >= 30 else PERSONA_PROMPT_15S
            num_parts = 4 if duration >= 30 else 2

        # Build system prompt with all template variables
        system_prompt = (
            template
            .replace("{{influencer_name}}", influencer_data.get("name", "the creator"))
            .replace("{{influencer_age}}", str(influencer_data.get("age", "25-year-old")))
            .replace("{{influencer_gender}}", influencer_data.get("gender", "Female").lower())
            .replace("{{influencer_personality}}", influencer_data.get("personality", "friendly and relatable"))
            .replace("{{influencer_tone}}", influencer_data.get("tone", "Enthusiastic"))
            .replace("{{influencer_energy}}", influencer_data.get("energy_level", "High"))
            .replace("{{influencer_accent}}", influencer_data.get("accent", "neutral English"))
            .replace("{{brand_name}}", brand)
            .replace("{{visual_description}}", str(visuals))
            .replace("{{color_scheme}}", color_str)
            .replace("{{user_context}}", user_context)
        )

        # Clip-specific replacements
        if is_clip:
            system_prompt = (
                system_prompt
                .replace("{{clip_seconds}}", str(duration))
                .replace("{{word_min}}", str(clip_cfg["word_min"]))
                .replace("{{word_max}}", str(clip_cfg["word_max"]))
                .replace("{{speech_seconds}}", str(clip_cfg["speech_seconds"]))
            )

        # i18n: Inject language directive
        if video_language == "es":
            system_prompt += "\n\nLANGUAGE OVERRIDE: You MUST write the ENTIRE script in Spanish. Use natural Latin American or Spain Spanish. All dialogue must be in Spanish."

        # Adjust user prompt based on mode
        if is_clip:
            user_msg = f"Generate the UGC clip script now. It MUST be exactly {clip_cfg['word_min']}-{clip_cfg['word_max']} words. Sound like a real person, not an ad."
        elif is_seedance:
            if num_parts == 2:
                user_msg = f"Generate the {num_parts}-part UGC script now. Part 1 MUST be 7-9 words. Part 2 MUST be 28-33 words. Sound like a real person, not an ad."
            else:
                user_msg = f"Generate the {num_parts}-part UGC script now. Parts 1 & 4 MUST be 7-9 words. Parts 2 & 3 MUST be 28-33 words. Sound like a real person."
        else:
            user_msg = f"Generate the {num_parts}-part UGC script now. Remember: sound like a real person, not an ad. Each part MUST be exactly 19-21 words."

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg}
            ],
            max_tokens=300 if duration >= 30 else 150,
            temperature=0.85,
            top_p=1.0,
            frequency_penalty=0.2,
            presence_penalty=0.1
        )
        return response.choices[0].message.content.strip()

    def _humanize_script(self, raw_script: str) -> str:
        """Step 2: Polish the raw script to inject natural human speech patterns."""
        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-nano",
                messages=[
                    {"role": "system", "content": HUMANIZE_PROMPT_TEMPLATE},
                    {"role": "user", "content": raw_script}
                ],
                max_tokens=300,
                temperature=0.9,
                top_p=1.0,
                frequency_penalty=0.1,
                presence_penalty=0.2
            )
            result = response.choices[0].message.content.strip()
            # Validate that the ||| delimiter survived the polish pass
            if "|||" not in result:
                print("      [AIScript] Humanize step lost ||| delimiter, using raw script")
                return raw_script
            return result
        except Exception as e:
            print(f"      [AIScript] Humanize step failed: {e}, using raw script")
            return raw_script

    # ------------------------------------------------------------------
    # Public Method (Backward-Compatible)
    # ------------------------------------------------------------------

    def generate_physical_product_script(
        self,
        product_analysis: Dict[str, Any],
        duration: int,
        product_name: str = "",
        influencer_data: Optional[Dict[str, Any]] = None,
        model_api: str = "",
        video_language: str = "en",
        context: str = "",
    ) -> str:
        """
        Generates a compelling UGC script for a physical product.

        When influencer_data is provided (pipeline context), uses the two-step
        persona-driven generation. When absent (API endpoint context), falls
        back to the original single-step generic generation.

        Args:
            product_analysis: The visual description/analysis dict from the DB.
            duration: Target duration in seconds (15 or 30).
            product_name: Name of the product (optional fallback).
            influencer_data: Influencer dict with persona fields (optional).

        Returns:
            The generated script text in "Part1 ||| Part2" format.
        """
        if not self.api_key:
            return "Error: OpenAI API Key not configured."

        # Ensure brand name is available in product_analysis
        if not product_analysis.get("brand_name") and product_name:
            product_analysis = {**product_analysis, "brand_name": product_name}

        # === SINGLE-STEP PERSONA PATH (when influencer data is available) ===
        if influencer_data and influencer_data.get("name"):
            try:
                print("      [AIScript] Generating persona-driven script (single-step)...")
                raw_script = self._generate_raw_script(product_analysis, influencer_data, duration, video_language=video_language, model_api=model_api, context=context)
                try:
                    safe_raw = raw_script.encode('ascii', 'ignore').decode('ascii')
                    print(f"      [AIScript] Script: {safe_raw[:80]}...")
                except:
                    pass

                return raw_script
            except Exception as e:
                print(f"      [AIScript] Persona generation failed: {e}, falling back to generic")
                # Fall through to the original generic path below

        # === ORIGINAL GENERIC PATH (API endpoint / fallback) ===
        brand = product_analysis.get("brand_name") or product_name or "the product"
        visuals = product_analysis.get("visual_description", "A product.")
        colors = product_analysis.get("color_scheme", [])
        font = product_analysis.get("font_style", "N/A")

        color_str = ""
        if isinstance(colors, list):
            color_str = "\n".join([f"  - hex: {c.get('hex', '')}, name: {c.get('name', '')}" for c in colors if isinstance(c, dict)])

        words_per_scene = 19
        num_parts = 4 if duration >= 30 else 2
        total_words = words_per_scene * num_parts

        if num_parts == 4:
            structure_block = f"""**STRUCTURE — output exactly 4 parts separated by |||**
Part 1 (Hook): An attention-grabbing opener that creates curiosity. Exactly 19-21 words (7 seconds of speech).
Part 2 (Benefits): Highlight the product's best feature or quality. Exactly 19-21 words (7 seconds of speech).
Part 3 (Reaction): Show genuine amazement or personal experience. Exactly 19-21 words (7 seconds of speech).
Part 4 (CTA): Encourage viewers to check it out with a warm call-to-action. Exactly 19-21 words (7 seconds of speech).

**Example format:**
You guys, I finally found the one product that completely changed my skin game. ||| The texture is insane, it absorbs in like two seconds flat. ||| Honestly my skin has never looked this good, I am obsessed. ||| Seriously, check it out and thank me later. Link in bio!"""
        else:
            structure_block = f"""**STRUCTURE — output exactly 2 parts separated by |||**
Part 1 (Hook): An attention-grabbing opener that creates curiosity. Exactly 19-21 words (7 seconds of speech).
Part 2 (Benefits + CTA): Highlight the product's key benefit and end with a soft call-to-action. Exactly 19-21 words (7 seconds of speech).

**Example format:**
You guys, I finally found the one product that completely changed my skin game. ||| The texture is insane, it absorbs in seconds and leaves your skin glowing. Link in bio!"""

        system_prompt = f"""You are a world-class copywriter specializing in viral User-Generated Content (UGC) for social media platforms like TikTok and Instagram.

Your task is to generate a UGC script for a {duration}-second video that will be split across {num_parts} video scenes (8 seconds each). The dialogue in each scene must last approximately 7 seconds so it finishes naturally before the scene ends.

{structure_block}

**RULES:**
- Total script must be approximately {total_words} words. Do NOT exceed this.
- Each part must be a complete, natural-sounding sentence or two.
- Tone: conversational, enthusiastic, genuine, as if sharing a real discovery.
- Language: simple, direct, persuasive.

**CRITICAL FORMAT RULES — the script will be spoken aloud by an AI video model:**
- Output ONLY the exact words to be spoken, separated by |||
- Do NOT include emojis, hashtags, or special symbols.
- Do NOT include stage directions, actions, or annotations like [Shows product], (holds up), *smiles*, etc.
- Do NOT include scene labels like "Hook:", "Scene 1:", "Part 1:", etc.
- Do NOT use ellipsis (...). Use a comma or period instead for pauses.
- Do NOT add any text before Part 1 or after Part {num_parts}.
- NEVER repeat the last word(s) of one part at the beginning of the next part.
- Do NOT end any part with hanging words or transition noises (e.g., "uh", "um", "and", "so", "but", "like")."""

        user_prompt = f"""**Product Analysis:**

```yaml
brand_name: {brand}
color_scheme:
{color_str}
font_style: {font}
visual_description: {visuals}
```

Generate the {num_parts}-part UGC script now."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=200 if duration >= 30 else 150,
                temperature=0.8,
                top_p=1.0,
                frequency_penalty=0.1,
                presence_penalty=0.1
            )
            return response.choices[0].message.content.strip()

        except Exception as e:
            print(f"      [AIScript] Generic generation failed: {e}")
            return f"Check out {brand}! It's amazing. You have to try it."

    # ------------------------------------------------------------------
    # Digital Products (NEW)
    # ------------------------------------------------------------------

    def generate_digital_product_script(
        self,
        product_name: str,
        product_analysis: Optional[Dict[str, Any]] = None,
        website_content: Optional[str] = None,
        duration: int = 15,
        video_language: str = "en",
    ) -> str:
        """
        Generates a UGC script for a digital product (app/SaaS).

        Uses dual-source analysis:
        - product_analysis: Vision analysis of the app screenshot/first frame.
        - website_content:  Scraped text from the product's website URL.

        Output format:
        - 15s: "Hook ||| CTA" (2 parts)
        - 30s: "Hook ||| Reaction ||| CTA" (3 parts for Extend pipeline)
        """
        if not self.api_key:
            if duration >= 30:
                return f"I have to show you this app. ||| The features are honestly so good, I use it every single day. ||| Link in bio, seriously check it out."
            return f"I have to show you this app. ||| It's seriously changed everything for me, link in bio!"

        # Build context from available sources
        app_description_parts = []

        if product_analysis:
            # New structured fields from GPT website analysis
            if product_analysis.get("product_summary"):
                app_description_parts.append(f"What it is: {product_analysis['product_summary']}")
            if product_analysis.get("key_benefits") and isinstance(product_analysis["key_benefits"], list):
                app_description_parts.append(f"Key benefits: {', '.join(product_analysis['key_benefits'])}")
            if product_analysis.get("target_audience"):
                app_description_parts.append(f"Target audience: {product_analysis['target_audience']}")
            if product_analysis.get("unique_selling_points") and isinstance(product_analysis["unique_selling_points"], list):
                app_description_parts.append(f"USPs: {', '.join(product_analysis['unique_selling_points'])}")
            if product_analysis.get("tone_and_personality"):
                app_description_parts.append(f"Brand tone: {product_analysis['tone_and_personality']}")

            # Legacy fallback fields
            if not app_description_parts:
                ui_desc = product_analysis.get("visual_description", "")
                app_type = product_analysis.get("app_type", "")
                key_features = product_analysis.get("key_features", [])
                if ui_desc:
                    app_description_parts.append(f"App UI: {ui_desc}")
                if app_type:
                    app_description_parts.append(f"App type: {app_type}")
                if key_features and isinstance(key_features, list):
                    app_description_parts.append(f"Key features: {', '.join(key_features[:5])}")

        if website_content and not app_description_parts:
            app_description_parts.append(f"Website content (first 1500 chars):\n{website_content[:1500]}")

        if not app_description_parts:
            app_description_parts.append(f"A digital product called '{product_name}'.")

        app_context = "\n\n".join(app_description_parts)

        words_per_scene = 20
        num_parts = 3 if duration >= 30 else 1

        if num_parts == 3:
            scene_description = f"""The video has 3 AI-generated scenes followed by an app clip:
- Scene 1 (8 seconds): AI influencer speaks to camera about the app. Exactly 20-22 words (7 seconds of speech).
- Scene 2 (8 seconds): AI influencer continues, showing genuine reaction to a feature. Exactly 20-22 words (7 seconds of speech).
- Scene 3 (8 seconds): AI influencer delivers a warm CTA. Exactly 20-22 words (7 seconds of speech).
- Scene 4: The actual app screen recording plays (no script needed)."""

            structure_block = f"""**STRUCTURE — output exactly 3 parts separated by |||**
Part 1 (Hook): Creates immediate curiosity about the app. Exactly 20-22 words (7 seconds of speech).
Part 2 (Reaction): Shows genuine excitement about a specific feature or benefit. Exactly 20-22 words (7 seconds of speech).
Part 3 (CTA): Warm call-to-action encouraging viewers to try the app. Exactly 20-22 words (7 seconds of speech).

**Example format (notice the length — each part is 20+ words):**
Okay so I literally just found this app and honestly it changed the way I plan my entire week, like no joke. ||| The meal planning feature is insane, it gives you recipes based on what you already have in your fridge, so easy. ||| Seriously go download it right now, I put the link in my bio for you guys, you are going to love it."""
            
            format_rules = f"""**CRITICAL FORMAT RULES:**
- Output ONLY the spoken words, separated by |||
- No emojis, hashtags, stage directions, or scene labels
- No ellipsis (...) — use commas or periods for pauses
- No text before Part 1 or after Part 3
- NEVER repeat the last word(s) of one part at the beginning of the next part.
- Do NOT end any part with hanging words or transition noises (e.g., "uh", "um", "and", "so", "but", "like")"""
        else:
            scene_description = f"""The video has 1 scene followed by an app clip:
- Scene 1 (8 seconds): An AI influencer speaks directly to camera about the app. Exactly 20-{words_per_scene + 5} words (7-8 seconds of speech).
- Scene 2 (7 seconds): The actual app screen recording plays. No voiceover is needed here, only background music will play."""

            structure_block = f"""**STRUCTURE — output exactly 1 part (DO NOT use |||)**
Part 1 (Hook & CTA combined): Creates immediate curiosity and includes a quick call-to-action. Exactly 20-{words_per_scene + 5} words (7-8 seconds of speech)."""

            format_rules = f"""**CRITICAL FORMAT RULES:**
- Output ONLY the spoken words. Do NOT use the ||| symbol anywhere.
- No emojis, hashtags, stage directions, or scene labels.
- No ellipsis (...) — use commas or periods for pauses.
- Do NOT end the script with hanging words or transition noises."""

        system_prompt = f"""You are a viral UGC content creator writing a script for a {duration}-second social media video promoting a digital app or software product.

{scene_description}

{structure_block}

**AUTHENTICITY RULES — this must sound like a real person talking on camera:**
- Include natural filler words where they fit: "like", "literally", "honestly", "okay so", "you guys", "I mean", "seriously"
- Use contractions naturally: it's, you're, I've, don't, gonna, wanna
- Reference personal experience: "I've been using this for...", "it saved me..."
- Mix short punchy sentences with slightly longer flowing ones
- Sound like you're talking to your best friend, not reading ad copy

**TONE RULES:**
- Start with a conversational opener: "So,", "Okay,", "I found this app", "You guys,"
- Avoid: "game-changer", "seamlessly", "unlock", "elevate", "transform", "revolutionize"
- Avoid: "real talk", "let me tell you", "I cannot stress this enough"
- Use specific details from the website content — vague scripts do not convert

{format_rules}"""

        # i18n: Inject language directive
        if video_language == "es":
            system_prompt += "\n\nLANGUAGE OVERRIDE: You MUST write the ENTIRE script in Spanish. Use natural Latin American or Spain Spanish. All dialogue and spoken words must be in Spanish."

        user_prompt = f"""**Product Name:** {product_name}

**Product Context:**
{app_context}

Generate the {num_parts}-part UGC script now."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=300 if duration >= 30 else 150,
                temperature=0.85,
                top_p=1.0,
                frequency_penalty=0.2,
                presence_penalty=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[FAIL] Digital AI Script Generation Failed: {e}")
            if duration >= 30:
                return f"I just found this app called {product_name} and honestly I cannot stop using it, it does literally everything I need. ||| The features are genuinely so good, it handles everything I need in one place and it is super easy to use. ||| Link is in my bio right now, you seriously need to try it for yourself, you will not regret it."
            return f"I just found this app called {product_name} and honestly I cannot stop using it, it is genuinely so good. ||| It does everything you need, link is in my bio right now, go check it out."

    # ------------------------------------------------------------------
    # Three-Call Prompt Chain (v2 structured script_json output)
    # ------------------------------------------------------------------
    #
    # These methods implement the blueprint v3 prompt chaining architecture.
    # They are ADDITIVE -- the existing generate_physical_product_script
    # and generate_digital_product_script methods are untouched and serve
    # as the fallback path for the ||| pipeline.
    # ------------------------------------------------------------------

    # Supported marketing methodologies
    METHODOLOGIES = [
        "Problem/Agitate/Solve",
        "Hook/Benefit/CTA",
        "Contrarian/Shock",
        "Social Proof",
        "Aspiration/Dream",
        "Curiosity/Cliffhanger",
    ]

    # Words and phrases that are strictly forbidden in generated scripts
    FORBIDDEN_PHRASES = (
        "game-changer, level up, hack, elevate, seamless, robust, delve, "
        "it's important to note, revolutionise, revolutionize, transform your life, "
        "real talk, let me tell you, I'm obsessed, I can't live without"
    )

    def _select_strategy(
        self,
        product_data: Dict[str, Any],
        influencer_data: Dict[str, Any],
        methodology: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Call 1: Persona and Strategy Selection.

        If the user already chose a methodology, we skip the LLM selection
        and just ask it to build the persona.
        """
        product_name = product_data.get("brand_name") or product_data.get("name", "the product")
        product_desc = self._build_product_description(product_data)
        product_category = product_data.get("category", "General")

        inf_name = influencer_data.get("name", "the creator")
        inf_age = influencer_data.get("age", "25-year-old")
        inf_gender = influencer_data.get("gender", "Female")
        inf_style = influencer_data.get("personality", "friendly and relatable")

        methodology_instruction = ""
        if methodology:
            methodology_instruction = f'The user has already selected the methodology "{methodology}". Use this exact methodology. '

        system_prompt = f"""You are a creative director at a top UGC agency.

Analyse the following product and influencer combination and determine:
1. The optimal marketing framework (script structure) for this pairing.
2. A specific, granular creator persona for this script.

Product: {product_name}
Product Category: {product_category}
Product Description: {product_desc}

Influencer: {inf_name}, {inf_age} {inf_gender.lower()}
Influencer Style: {inf_style}

Available methodologies: {', '.join(self.METHODOLOGIES)}

{methodology_instruction}

Return your answer as valid JSON with exactly two keys:
- "script_structure": one of the available methodologies
- "creator_persona": a 1-2 sentence description of the specific voice and personality for this script

Return ONLY the JSON object, no explanation."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "Select the strategy now."}
                ],
                max_tokens=200,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
            import json
            result = json.loads(response.choices[0].message.content.strip())
            # If user forced a methodology, override whatever the LLM picked
            if methodology:
                result["script_structure"] = methodology
            return result
        except Exception as e:
            print(f"      [AIScript] Strategy selection failed: {e}")
            return {
                "script_structure": methodology or "Hook/Benefit/CTA",
                "creator_persona": f"A {inf_age} {inf_gender.lower()} content creator with a {inf_style} style.",
            }

    def _generate_hooks(
        self,
        product_data: Dict[str, Any],
        creator_persona: str,
        script_structure: str,
        video_language: str = "en",
    ) -> list:
        """Call 2: Hook Generation. Returns 4 diverse opening lines aligned to the methodology."""
        product_name = product_data.get("brand_name") or product_data.get("name", "the product")
        product_desc = self._build_product_description(product_data)

        # Build methodology-specific hook guidance
        methodology_hook_guidance = {
            "Problem/Agitate/Solve": """All 4 hooks MUST open with a relatable PROBLEM or PAIN POINT that the product solves.
Examples of the tone to aim for:
- "So tired of [specific problem]? Here's what actually worked."
- "I wasted so much money on [category] until I found this."
- "Why does every [product category] do [annoying thing]?"
Each hook must name a specific frustration or struggle.""",
            "Hook/Benefit/CTA": """All 4 hooks MUST lead with the product's strongest BENEFIT or a surprising claim.
Examples of the tone to aim for:
- "This [product] literally saved me [specific benefit]."
- "I found the one [product category] that actually [delivers benefit]."
- "Okay, [specific benefit] in [short time]? Let me show you."
Each hook must highlight a tangible benefit upfront.""",
            "Contrarian/Shock": """All 4 hooks MUST open with a SHOCKING or CONTRARIAN statement that challenges a common belief.
Examples of the tone to aim for:
- "Everything you know about [category] is wrong."
- "Stop buying [common product] — here's what actually works."
- "I know this sounds crazy but [counterintuitive claim]."
Each hook must provoke a strong reaction or challenge conventional wisdom.""",
            "Social Proof": """All 4 hooks MUST lead with SOCIAL PROOF — a result, a number, or a testimonial-style statement.
Examples of the tone to aim for:
- "Over [number] people switched to this, and I finally see why."
- "My friend wouldn't stop talking about this, so I tried it."
- "[Number] five-star reviews can't be wrong."
Each hook must reference other people's experience or measurable results.""",
            "Aspiration/Dream": """All 4 hooks MUST paint a DREAM OUTCOME or ASPIRATIONAL vision that the viewer desires.
Examples of the tone to aim for:
- "Imagine [dream scenario] — that's exactly what happened to me."
- "What if [ideal outcome] was actually possible?"
- "I always wanted [aspirational goal] and this is how I got there."
Each hook must make the viewer visualize their ideal outcome.""",
            "Curiosity/Cliffhanger": """All 4 hooks MUST create an OPEN LOOP or CLIFFHANGER that makes the viewer desperate to keep watching.
Examples of the tone to aim for:
- "I wasn't supposed to share this but [tease]."
- "There's one thing about [product] nobody talks about."
- "Wait until you see what happens when you [action]."
Each hook must withhold information to build curiosity.""",
        }

        hook_guidance = methodology_hook_guidance.get(script_structure, methodology_hook_guidance["Hook/Benefit/CTA"])

        system_prompt = f"""You are a hook-generation specialist for UGC ads.

Product: {product_name}
Product Description: {product_desc}
Script Methodology: {script_structure}
Creator Persona: {creator_persona}

You are generating hooks specifically for the "{script_structure}" methodology.

{hook_guidance}

Generate exactly 4 hooks that ALL follow the {script_structure} methodology's tone and approach.
Each hook should be a VARIATION of the same methodology, not 4 different methodologies.

Rules:
- Each hook must be 10-17 words maximum
- Use contractions naturally (it's, I've, don't, you're)
- Use conversational openers (So, Okay but, Honestly, Wait)
- NEVER use: {self.FORBIDDEN_PHRASES}
- No emojis, no hashtags

Return your answer as a valid JSON array of 4 strings.
Return ONLY the JSON array, no explanation.

{('LANGUAGE OVERRIDE: ALL 4 hooks MUST be written entirely in Spanish. Use natural Latin American or Spain Spanish.' if video_language == 'es' else '')}"""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Generate 4 hooks using ONLY the {script_structure} approach now."}
                ],
                max_tokens=300,
                temperature=0.9,
                response_format={"type": "json_object"},
            )
            import json
            raw = response.choices[0].message.content.strip()
            parsed = json.loads(raw)
            # Handle both {"hooks": [...]} and bare [...]
            if isinstance(parsed, dict):
                hooks = parsed.get("hooks") or list(parsed.values())[0]
            else:
                hooks = parsed
            return hooks if isinstance(hooks, list) else [str(hooks)]
        except Exception as e:
            print(f"      [AIScript] Hook generation failed: {e}")
            return [f"Okay you guys, I found {product_name} and I honestly can't believe this."]

    def _generate_full_script(
        self,
        product_data: Dict[str, Any],
        influencer_data: Dict[str, Any],
        creator_persona: str,
        script_structure: str,
        hook: str,
        video_length: int,
        video_language: str = "en",
        model_api: str = "",
        product_type: str = "physical",
    ) -> Dict[str, Any]:
        """Call 3: Full Script Generation. Returns the complete script_json object."""
        product_name = product_data.get("brand_name") or product_data.get("name", "the product")
        product_desc = self._build_product_description(product_data)
        product_category = product_data.get("category", "General")

        num_scenes = 4 if video_length >= 30 else 2
        target_duration = 30 if video_length >= 30 else 15

        # Seedance 2.0: variable durations per scene → different word counts
        is_seedance = "seedance" in model_api.lower() if model_api else False
        if is_seedance:
            import config as _cfg
            seedance_cfg = _cfg.get_seedance_durations(f"{video_length}s", product_type)
            seedance_scenes = seedance_cfg["scenes"]
            # Filter to AI scenes only (skip clips) for word count mapping
            ai_scenes = [s for s in seedance_scenes if s["has_video_input"] is not None]
            num_scenes = len(ai_scenes)
            # Build per-scene word count instructions
            scene_word_specs = []
            for idx, sc in enumerate(ai_scenes):
                dur = sc["duration"]
                if dur <= 4:
                    word_range = "7-9"
                    speech_sec = 3
                elif dur <= 8:
                    word_range = "19-21"
                    speech_sec = 7
                else:  # 12s
                    word_range = "28-33"
                    speech_sec = 10
                scene_word_specs.append((word_range, speech_sec, dur))
        else:
            scene_word_specs = [("19-21", 7, 8)] * num_scenes

        inf_name = influencer_data.get("name", "the creator")
        inf_age = influencer_data.get("age", "25-year-old")
        inf_gender = influencer_data.get("gender", "Female")

        # Build STRONG per-methodology scene instructions
        # Use Seedance-aware word counts when applicable
        def _scene_spec(idx):
            """Return 'exactly X-Y words, Z seconds' string for scene idx."""
            if idx < len(scene_word_specs):
                wr, ss, _ = scene_word_specs[idx]
                return f"exactly {wr} words, {ss} seconds"
            return "exactly 19-21 words, 7 seconds"

        if num_scenes == 2:
            methodology_scene_templates = {
                "Problem/Agitate/Solve": f"""Generate exactly 2 scenes following Problem/Agitate/Solve:
Scene 1 - Problem: Use the hook to describe a relatable problem or frustration. Agitate the pain. {_scene_spec(0)}.
Scene 2 - Solve + CTA: Show how {product_name} solves the problem, end with a soft CTA. {_scene_spec(1)}.""",
                "Hook/Benefit/CTA": f"""Generate exactly 2 scenes following Hook/Benefit/CTA:
Scene 1 - Hook/Benefit: Use the hook to highlight the product's best benefit. {_scene_spec(0)}.
Scene 2 - CTA: Reinforce the benefit and end with a warm call-to-action. {_scene_spec(1)}.""",
                "Contrarian/Shock": f"""Generate exactly 2 scenes following Contrarian/Shock:
Scene 1 - Shocking Statement: Use the hook to challenge conventional wisdom or make a bold contrarian claim. {_scene_spec(0)}.
Scene 2 - Resolution + CTA: Explain why the shocking claim is true because of {product_name}, CTA. {_scene_spec(1)}.""",
                "Social Proof": f"""Generate exactly 2 scenes following Social Proof:
Scene 1 - Proof/Result: Use the hook to share a specific result, number, or reference to other people's experience. {_scene_spec(0)}.
Scene 2 - Product + CTA: Connect the proof to {product_name} and end with a CTA. {_scene_spec(1)}.""",
                "Aspiration/Dream": f"""Generate exactly 2 scenes following Aspiration/Dream:
Scene 1 - Dream Outcome: Use the hook to paint the ideal aspirational scenario the viewer desires. {_scene_spec(0)}.
Scene 2 - Bridge + CTA: Show {product_name} as the bridge to that dream, end with CTA. {_scene_spec(1)}.""",
                "Curiosity/Cliffhanger": f"""Generate exactly 2 scenes following Curiosity/Cliffhanger:
Scene 1 - Open Loop: Use the hook to create an irresistible curiosity gap or cliffhanger. {_scene_spec(0)}.
Scene 2 - Reveal + CTA: Reveal the answer is {product_name}, end with CTA. {_scene_spec(1)}.""",
            }
            scene_instructions = methodology_scene_templates.get(script_structure, methodology_scene_templates["Hook/Benefit/CTA"])
        else:
            methodology_scene_templates = {
                "Problem/Agitate/Solve": f"""Generate exactly 4 scenes following Problem/Agitate/Solve:
Scene 1 - Problem Hook: Use the hook to present a relatable problem. {_scene_spec(0)}.
Scene 2 - Agitate: Make the problem feel urgent and unbearable. {_scene_spec(1)}.
Scene 3 - Solve: Show how {product_name} is the perfect solution. {_scene_spec(2)}.
Scene 4 - CTA: End with a warm call-to-action. {_scene_spec(3)}.""",
                "Hook/Benefit/CTA": f"""Generate exactly 4 scenes following Hook/Benefit/CTA:
Scene 1 - Hook: Use the hook to grab attention with the key benefit. {_scene_spec(0)}.
Scene 2 - Key Benefit: Detail the product's strongest selling point. {_scene_spec(1)}.
Scene 3 - Supporting Benefit: Share a second benefit or personal experience. {_scene_spec(2)}.
Scene 4 - CTA: Warm call-to-action to try {product_name}. {_scene_spec(3)}.""",
                "Contrarian/Shock": f"""Generate exactly 4 scenes following Contrarian/Shock:
Scene 1 - Shocking Statement: Use the hook to make a bold, contrarian claim. {_scene_spec(0)}.
Scene 2 - Explanation: Back up the shocking claim with reasoning. {_scene_spec(1)}.
Scene 3 - Product Resolution: Introduce {product_name} as the proof. {_scene_spec(2)}.
Scene 4 - CTA: End with a confident call-to-action. {_scene_spec(3)}.""",
                "Social Proof": f"""Generate exactly 4 scenes following Social Proof:
Scene 1 - Result/Review: Use the hook to share specific social proof or results. {_scene_spec(0)}.
Scene 2 - Product Intro: Introduce {product_name} as the reason for the results. {_scene_spec(1)}.
Scene 3 - Demo/Experience: Share personal experience using the product. {_scene_spec(2)}.
Scene 4 - CTA: End with social-proof-reinforced CTA. {_scene_spec(3)}.""",
                "Aspiration/Dream": f"""Generate exactly 4 scenes following Aspiration/Dream:
Scene 1 - Dream Outcome: Use the hook to paint the ideal aspirational scenario. {_scene_spec(0)}.
Scene 2 - Current Reality Gap: Describe the gap between where the viewer is and where they want to be. {_scene_spec(1)}.
Scene 3 - Product Bridge: Show how {product_name} bridges that gap. {_scene_spec(2)}.
Scene 4 - CTA: End with an inspiring call-to-action. {_scene_spec(3)}.""",
                "Curiosity/Cliffhanger": f"""Generate exactly 4 scenes following Curiosity/Cliffhanger:
Scene 1 - Open Loop: Use the hook to create an irresistible curiosity gap. {_scene_spec(0)}.
Scene 2 - Tension Building: Build suspense, hint at the answer without revealing. {_scene_spec(1)}.
Scene 3 - Reveal: Reveal {product_name} as the answer, show specific results. {_scene_spec(2)}.
Scene 4 - CTA: End with a curiosity-driven CTA. {_scene_spec(3)}.""",
            }
            scene_instructions = methodology_scene_templates.get(script_structure, methodology_scene_templates["Hook/Benefit/CTA"])

        # Build word count instruction for the system prompt
        if is_seedance:
            word_count_instruction = "IMPORTANT: Each scene has a DIFFERENT word count requirement based on its duration. Follow the per-scene word counts specified below EXACTLY."
            json_dialogue_example = "<spoken text, follow the word count for this scene>"
            json_word_count_example = "<integer matching scene requirement>"
            json_duration_example = "<speech seconds for this scene>"
        else:
            word_count_instruction = "Each scene's dialogue must be exactly 19-21 words long to fit within a 7-second speaking duration."
            json_dialogue_example = "<spoken text, exactly 19-21 words>"
            json_word_count_example = "<integer>"
            json_duration_example = "7.0"

        system_prompt = f"""You are writing a complete UGC video script.

Product: {product_name}
Product Category: {product_category}
Product Description: {product_desc}
Creator Persona: {creator_persona}
Marketing Framework: {script_structure}
Hook to use: "{hook}"

STRICT TECHNICAL REQUIREMENT:
You must generate dialogue for exactly {num_scenes} scenes.
{word_count_instruction}
Do not exceed the word count for any scene. This is a strict technical requirement.

{scene_instructions}

LANGUAGE RULES (non-negotiable):
- Use contractions at all times: it's, you're, I've, don't, can't
- The dialogue MUST flow as one continuous, natural spoken conversation across all scenes. 
- DO NOT start every scene with disjointed openers like "Okay but" or "Honestly" unless it naturally connects to the previous sentence.
- Use imperfect spoken grammar: sentence fragments, trailing thoughts
- When mentioning benefits, use SPECIFIC numbers and details that are relevant to THIS product. Invent realistic quantities based on the product category (e.g. time saved, money saved, steps reduced). NEVER default to generic numbers.
- NEVER use these words or phrases: {self.FORBIDDEN_PHRASES}

{'LANGUAGE OVERRIDE: The ENTIRE script (all scene dialogues, the hook, and the name) MUST be written in Spanish. Use natural Latin American or Spain Spanish. Do NOT mix languages.' if video_language == 'es' else ''}

Return your answer as valid JSON matching this EXACT schema:
{{
  "name": "A short descriptive name for this script",
  "target_duration_sec": {target_duration},
  "target_platform": "TikTok",
  "methodology": "{script_structure}",
  "hook": "<the hook line>",
  "scenes": [
    {{
      "scene_number": 1,
      "scene_title": "<title like Hook, Problem, CTA>",
      "dialogue": "{json_dialogue_example}",
      "word_count": {json_word_count_example},
      "estimated_duration_sec": {json_duration_example},
      "visual_cue": "<brief director note for the visual>",
      "on_screen_text": "<optional overlay text or empty string>"
    }}
  ]
}}

Return ONLY the JSON object, no explanation."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Write the complete {num_scenes}-scene script now. Creator: {inf_name}, {inf_age} {inf_gender.lower()}."}
                ],
                max_tokens=800,
                temperature=0.75,
                response_format={"type": "json_object"},
            )
            import json
            result = json.loads(response.choices[0].message.content.strip())

            # Set estimated_duration_sec per scene based on config
            for idx, scene in enumerate(result.get("scenes", [])):
                if idx < len(scene_word_specs):
                    _, speech_sec, _ = scene_word_specs[idx]
                    scene["estimated_duration_sec"] = float(speech_sec)
                else:
                    scene["estimated_duration_sec"] = 7.0

            return result
        except Exception as e:
            print(f"      [AIScript] Full script generation failed: {e}")
            # Return a minimal valid fallback
            fallback_scenes = []
            for i in range(num_scenes):
                if i == 0:
                    dialogue = hook
                    title = "Hook"
                elif i == num_scenes - 1:
                    dialogue = f"Check out {product_name}, link is in my bio."
                    title = "CTA"
                else:
                    dialogue = f"Honestly {product_name} is so good, I use it every single day."
                    title = "Body"
                fallback_scenes.append({
                    "scene_number": i + 1,
                    "scene_title": title,
                    "dialogue": dialogue,
                    "word_count": len(dialogue.split()),
                    "estimated_duration_sec": 7.0,
                    "visual_cue": "Influencer speaking to camera.",
                    "on_screen_text": "",
                })
            return {
                "name": f"Script for {product_name}",
                "target_duration_sec": target_duration,
                "target_platform": "TikTok",
                "methodology": script_structure,
                "hook": hook,
                "scenes": fallback_scenes,
            }

    def generate_structured_script(
        self,
        product_data: Dict[str, Any],
        influencer_data: Dict[str, Any],
        video_length: int = 15,
        methodology: Optional[str] = None,
        context: Optional[str] = None,
        video_language: str = "en",
        model_api: str = "",
        product_type: str = "physical",
    ) -> Dict[str, Any]:
        """Public entry point for the v2 three-call prompt chain.

        Returns a complete script_json dict (NOT a ||| string).
        The existing generate_physical_product_script / generate_digital_product_script
        methods are preserved and keep working for the legacy pipeline.

        Args:
            product_data: Product details (brand_name, visual_description, category, etc.)
            influencer_data: Influencer dict (name, age, gender, personality, tone, etc.)
            video_length: 15 or 30 seconds
            methodology: Optional forced methodology (user selection)
            context: Optional additional instructions from the user

        Returns:
            A dict conforming to the script_json schema (blueprint Section 3.3).
        """
        if not self.api_key:
            return {"error": "OpenAI API Key not configured."}

        # Ensure brand name
        if not product_data.get("brand_name") and product_data.get("name"):
            product_data = {**product_data, "brand_name": product_data["name"]}

        print("      [AIScript v2] Call 1/3: Selecting strategy and persona...")
        strategy = self._select_strategy(product_data, influencer_data, methodology)
        script_structure = strategy.get("script_structure", methodology or "Hook/Benefit/CTA")
        creator_persona = strategy.get("creator_persona", "A friendly content creator.")
        # i18n: Inject language into persona so all downstream calls inherit it
        if video_language == "es":
            creator_persona += " This creator speaks fluent Spanish and MUST write entirely in Spanish."
        print(f"      [AIScript v2] Strategy: {script_structure} | Persona: {creator_persona[:60]}... | Lang: {video_language}")

        print("      [AIScript v2] Call 2/3: Generating hooks...")
        hooks = self._generate_hooks(product_data, creator_persona, script_structure, video_language=video_language)
        # Randomly select from generated hooks for diversity
        import random
        selected_hook = random.choice(hooks) if hooks else "Check this out."
        print(f"      [AIScript v2] Selected hook: {selected_hook[:60]}...")

        print("      [AIScript v2] Call 3/3: Generating full script...")
        script_json = self._generate_full_script(
            product_data, influencer_data,
            creator_persona, script_structure,
            selected_hook, video_length,
            video_language=video_language,
            model_api=model_api,
            product_type=product_type,
        )
        print(f"      [AIScript v2] Script generated: {script_json.get('name', 'unnamed')}")

        # Attach all generated hooks for the frontend preview
        script_json["_generated_hooks"] = hooks

        return script_json

    @staticmethod
    def script_json_to_legacy(script_json: Dict[str, Any]) -> str:
        """Compatibility adapter: convert script_json to a ||| delimited string.

        This allows the new structured format to be consumed by the legacy
        scene_builder / physical_prompts pipeline without any changes to
        downstream code.
        """
        scenes = script_json.get("scenes", [])
        if not scenes:
            return script_json.get("hook", "Check this out.")
        dialogues = [scene.get("dialogue", "") for scene in scenes]
        return " ||| ".join(dialogues)

