import os
from openai import OpenAI
from typing import Dict, Any, Optional

# ---------------------------------------------------------------------------
# Prompt Templates for Two-Step Persona-Driven Script Generation
# ---------------------------------------------------------------------------

PERSONA_PROMPT_TEMPLATE = """You are {{influencer_name}}, a {{influencer_age}} {{influencer_gender}} content creator.

Your personality: {{influencer_personality}}
Your speaking style: {{influencer_tone}}, {{influencer_energy}} energy
Your accent: {{influencer_accent}}

You are recording a {{duration}}-second UGC video for a physical product. The video has 2 scenes (8 seconds each). Each scene's dialogue must be approximately 7 seconds of speech (~17 words max).

**PRODUCT INFO:**
Brand: {{brand_name}}
Visual Description: {{visual_description}}
Colors: {{color_scheme}}

**OUTPUT FORMAT — exactly 2 parts separated by |||**
Part 1 (Hook): An attention-grabbing opener that creates curiosity. Max 17 words.
Part 2 (Benefits + CTA): Highlight the key benefit and end with a soft call-to-action. Max 17 words.

**AUTHENTICITY RULES:**
- Write EXACTLY how {{influencer_name}} would talk in a casual selfie video
- Use contractions naturally (it's, you're, I've, don't, gonna, wanna)
- Include natural filler words where they fit (like, literally, honestly, okay so, you guys)
- Reference personal experience ("I've been using this for...", "my skin has never...")
- Mix short punchy sentences with slightly longer ones
- Sound like you're talking to your best friend, not reading ad copy

**FORBIDDEN WORDS & PHRASES (never use these):**
revolutionary, game-changer, transform, unlock, elevate, premium, luxurious,
cutting-edge, innovative, state-of-the-art, unparalleled, exclusive,
must-have, holy grail, delve into, seamlessly, meticulously crafted,
showcasing, play a significant role, testament to,
in today's fast-paced world, it's not just about X it's about Y

**CRITICAL FORMAT RULES — the script will be spoken aloud by an AI video model:**
- Output ONLY the exact words to be spoken, separated by |||
- Do NOT include emojis, hashtags, or special symbols
- Do NOT include stage directions, actions, or annotations like [Shows product], (holds up), *smiles*, etc.
- Do NOT include scene labels like "Hook:", "Scene 1:", "Part 1:", etc.
- Do NOT use ellipsis (...). Use a comma or period instead for pauses
- Do NOT add any text before Part 1 or after Part 2"""

HUMANIZE_PROMPT_TEMPLATE = """You are a dialogue polish editor. Your only job is to make this script sound like a real person talking spontaneously on camera.

Take this script and make it sound MORE human:
- Adjust filler words to feel natural (um, like, okay so, honestly, wait)
- Make contractions more casual (it is -> it's, I have -> I've, do not -> don't)
- Vary sentence length, mix short punchy fragments with longer flowing thoughts
- Ensure it sounds like someone genuinely excited, not reading a teleprompter
- Break any remaining formal structure into casual speech patterns

RULES:
- Keep the ||| delimiter between Part 1 and Part 2
- Do NOT change the core message or product name
- Do NOT add emojis, hashtags, stage directions, or scene labels
- Do NOT exceed ~17 words per part
- Output ONLY the polished script text with |||
- Do NOT use ellipsis (...). Use a comma or period instead"""


class AIScriptClient:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            print("OPENAI_API_KEY not found. Script generation will fail.")
        self.client = OpenAI(api_key=self.api_key)

    # ------------------------------------------------------------------
    # Two-Step Persona Pipeline (Private Methods)
    # ------------------------------------------------------------------

    def _generate_raw_script(self, product_analysis: Dict[str, Any], influencer_data: Dict[str, Any], duration: int) -> str:
        """Step 1: Generate a persona-driven raw script using influencer context."""
        brand = product_analysis.get("brand_name") or "the product"
        visuals = product_analysis.get("visual_description", "A product.")
        colors = product_analysis.get("color_scheme", [])
        color_str = ", ".join(
            [c.get("name", "") for c in colors if isinstance(c, dict)]
        ) if isinstance(colors, list) else ""

        system_prompt = (
            PERSONA_PROMPT_TEMPLATE
            .replace("{{influencer_name}}", influencer_data.get("name", "the creator"))
            .replace("{{influencer_age}}", str(influencer_data.get("age", "25-year-old")))
            .replace("{{influencer_gender}}", influencer_data.get("gender", "Female").lower())
            .replace("{{influencer_personality}}", influencer_data.get("personality", "friendly and relatable"))
            .replace("{{influencer_tone}}", influencer_data.get("tone", "Enthusiastic"))
            .replace("{{influencer_energy}}", influencer_data.get("energy_level", "High"))
            .replace("{{influencer_accent}}", influencer_data.get("accent", "neutral English"))
            .replace("{{duration}}", str(duration))
            .replace("{{brand_name}}", brand)
            .replace("{{visual_description}}", str(visuals))
            .replace("{{color_scheme}}", color_str)
        )

        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": "Generate the 2-part UGC script now. Remember: sound like a real person, not an ad."}
            ],
            max_tokens=150,
            temperature=0.7,
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
                max_tokens=150,
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
        influencer_data: Optional[Dict[str, Any]] = None
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

        # === TWO-STEP PERSONA PATH (when influencer data is available) ===
        if influencer_data and influencer_data.get("name"):
            try:
                print("      [AIScript] Step 1: Generating persona-driven raw script...")
                raw_script = self._generate_raw_script(product_analysis, influencer_data, duration)
                print(f"      [AIScript] Raw: {raw_script[:80]}...")

                print("      [AIScript] Step 2: Humanizing script for authenticity...")
                humanized_script = self._humanize_script(raw_script)
                print(f"      [AIScript] Final: {humanized_script[:80]}...")

                return humanized_script
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

        words_per_scene = 17
        total_words = words_per_scene * 2

        system_prompt = f"""You are a world-class copywriter specializing in viral User-Generated Content (UGC) for social media platforms like TikTok and Instagram.

Your task is to generate a UGC script for a {duration}-second video that will be split across 2 video scenes (8 seconds each). The dialogue in each scene must last approximately 7 seconds so it finishes naturally before the scene ends.

**STRUCTURE — output exactly 2 parts separated by |||**
Part 1 (Hook): An attention-grabbing opener that creates curiosity. Max {words_per_scene} words.
Part 2 (Benefits + CTA): Highlight the product's key benefit and end with a soft call-to-action. Max {words_per_scene} words.

**Example format:**
You guys, I finally found the one product that completely changed my skin game. ||| The texture is insane, it absorbs in seconds and leaves your skin glowing. Link in bio!

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
- Do NOT add any text before Part 1 or after Part 2."""

        user_prompt = f"""**Product Analysis:**

```yaml
brand_name: {brand}
color_scheme:
{color_str}
font_style: {font}
visual_description: {visuals}
```

Generate the 2-part UGC script now."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,
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
    ) -> str:
        """
        Generates a UGC script for a digital product (app/SaaS).

        Uses dual-source analysis:
        - product_analysis: Vision analysis of the app screenshot/first frame.
        - website_content:  Scraped text from the product's website URL.

        Output format: "Scene 1 dialogue ||| Scene 2 dialogue"
        Scene 1 = Influencer hook (7s of speech max, 17 words)
        Scene 2 = App clip plays (no dialogue needed, but CTA is generated
                  for use as a subtitle overlay if desired)
        """
        if not self.api_key:
            return f"I have to show you this app. ||| It's seriously changed everything for me, link in bio!"

        # Build context from available sources
        app_description_parts = []

        if product_analysis:
            ui_desc = product_analysis.get("visual_description", "")
            app_type = product_analysis.get("app_type", "")
            key_features = product_analysis.get("key_features", [])
            if ui_desc:
                app_description_parts.append(f"App UI: {ui_desc}")
            if app_type:
                app_description_parts.append(f"App type: {app_type}")
            if key_features and isinstance(key_features, list):
                app_description_parts.append(f"Key features: {', '.join(key_features[:5])}")

        if website_content:
            # Truncate to keep prompt manageable
            app_description_parts.append(f"Website content (first 1500 chars):\n{website_content[:1500]}")

        if not app_description_parts:
            app_description_parts.append(f"A digital product called '{product_name}'.")

        app_context = "\n\n".join(app_description_parts)

        words_per_scene = 17

        system_prompt = f"""You are a viral UGC content creator writing a script for a {duration}-second social media video promoting a digital app or software product.

The video has 2 scenes:
- Scene 1 (8 seconds): An AI influencer speaks directly to camera, holding a phone/device showing the app. Your script for Scene 1 must be max {words_per_scene} words — enough for exactly 7 seconds of natural speech.
- Scene 2 (7 seconds): The actual app screen recording plays. Your script for Scene 2 is a short, punchy CTA that can be used as a subtitle overlay. Max {words_per_scene} words.

**STRUCTURE — output exactly 2 parts separated by |||**
Part 1 (Hook): Creates immediate curiosity about the app. Sounds like a real person sharing a discovery, not an ad. Max {words_per_scene} words.
Part 2 (CTA): Short, punchy call-to-action. References a specific benefit found in the website content. Max {words_per_scene} words.

**TONE RULES — this must sound like a real human, not AI:**
- Use contractions: "I've", "it's", "you're", "don't"
- Start with a conversational opener: "So,", "Okay,", "I found this app", "You guys,"
- Avoid: "game-changer", "seamlessly", "unlock", "elevate", "transform", "revolutionize"
- Avoid: "real talk", "let me tell you", "I cannot stress this enough"
- Use specific details from the website content — vague scripts do not convert

**CRITICAL FORMAT RULES:**
- Output ONLY the spoken words, separated by |||
- No emojis, hashtags, stage directions, or scene labels
- No ellipsis (...) — use commas or periods for pauses
- No text before Part 1 or after Part 2"""

        user_prompt = f"""**Product Name:** {product_name}

**Product Context:**
{app_context}

Generate the 2-part UGC script now."""

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=150,
                temperature=0.85,
                top_p=1.0,
                frequency_penalty=0.2,
                presence_penalty=0.1
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ Digital AI Script Generation Failed: {e}")
            return f"I found this app called {product_name} and honestly I can't stop using it. ||| It does everything, link is in my bio right now."
