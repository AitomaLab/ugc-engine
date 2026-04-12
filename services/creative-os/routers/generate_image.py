"""
Creative OS — Image Generation Router

Two-step flow:
1. POST /generate/image/enhance → Returns 3 enhanced prompt options
2. POST /generate/image/execute → Executes the selected prompt via core API or NanoBanana directly

Supports:
- Product + Influencer → Core API composite (NanoBanana via worker)
- Product only → Core API product shot
- Influencer only → NanoBanana direct call
- Direct upload → NanoBanana with uploaded image as reference
- Prompt only → NanoBanana with no reference images
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from auth import get_current_user
from core_api_client import CoreAPIClient
from services.prompt_enhancer import enhance_prompt
from services.model_router import get_image_mode

router = APIRouter(prefix="/generate/image", tags=["image-generation"])


class EnhanceRequest(BaseModel):
    prompt: str
    mode: str  # "cinematic", "iphone_look", "luxury", or "ugc"
    language: str = "en"
    project_id: Optional[str] = None
    product_id: Optional[str] = None
    influencer_id: Optional[str] = None


class ExecuteRequest(BaseModel):
    prompt: str  # The selected enhanced prompt
    mode: str
    project_id: str
    product_id: Optional[str] = None
    influencer_id: Optional[str] = None
    reference_image_url: Optional[str] = None  # Direct upload or pre-selected image
    aspect_ratio: str = "9:16"
    quality: str = "4k"  # 2k, 4k
    quick_action: bool = False  # True when triggered from modal quick actions


@router.post("/enhance")
async def enhance_image_prompt(data: EnhanceRequest, user: dict = Depends(get_current_user)):
    """Step 1: Enhance user prompt into 3 professional options."""
    mode_config = get_image_mode(data.mode)

    # Build context from references
    context = {}
    if data.product_id and data.project_id:
        client = CoreAPIClient(token=user["token"], project_id=data.project_id)
        product = await client.get_product(data.product_id)
        if product:
            context["product_name"] = product.get("name", "")
            context["product_description"] = product.get("description", "")

    if data.influencer_id and data.project_id:
        client = CoreAPIClient(token=user["token"], project_id=data.project_id)
        influencers = await client.list_influencers()
        influencer = next((i for i in influencers if i["id"] == data.influencer_id), None)
        if influencer:
            context["influencer_name"] = influencer.get("name", "")

    try:
        options = await enhance_prompt(
            user_prompt=data.prompt,
            mode=mode_config["system_prompt"],
            language=data.language,
            context=context if context else None,
        )
        return {
            "options": options,
            "mode": data.mode,
            "model": mode_config["model"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Prompt enhancement failed: {str(e)}")


@router.post("/execute")
async def execute_image_generation(data: ExecuteRequest, user: dict = Depends(get_current_user)):
    """Step 2: Execute the selected enhanced prompt.

    Routes to one of three paths based on available inputs:
    - Path A: Product + optional Influencer → Core API (NanoBanana via worker)
    - Path B: Influencer only → NanoBanana direct call
    - Path C: Upload / prompt only → NanoBanana direct call

    Stores influencer_id in shot metadata so re-generation can maintain
    character consistency by looking up the original influencer reference.
    """
    mode_config = get_image_mode(data.mode)
    client = CoreAPIClient(token=user["token"], project_id=data.project_id)

    try:
        # Look up influencer image if a model/influencer is selected
        influencer_image_url = None
        influencer = None
        if data.influencer_id:
            influencers = await client.list_influencers()
            influencer = next((i for i in influencers if i["id"] == data.influencer_id), None)
            if influencer:
                influencer_image_url = influencer.get("image_url")

        # ── Path UGC: Build composite prompt from template builders ──
        if data.mode == "ugc":
            if not data.product_id:
                raise HTTPException(status_code=400, detail="UGC mode requires a product selection.")

            product = await client.get_product(data.product_id)
            if not product:
                raise HTTPException(status_code=404, detail="Product not found.")

            # Determine product type
            product_type = product.get("product_type", "physical")
            is_digital = product_type == "digital" or product.get("website_url")

            # Build influencer context for the template builder
            if influencer:
                from scene_builder import _extract_visual_appearance
                ctx = {
                    "age": influencer.get("age", "25-year-old"),
                    "gender": influencer.get("gender", "Female"),
                    "visuals": _extract_visual_appearance(influencer),
                    "setting": (influencer.get("setting") or "").strip()
                        or "natural environment matching the background visible in the reference image",
                    "product": product,
                }
            else:
                ctx = {
                    "age": "25-year-old",
                    "gender": "Female",
                    "visuals": "casual style",
                    "setting": "natural environment matching the background visible in the reference image",
                    "product": product,
                }

            # The user's enhanced prompt (from the enhance step) is the scene description
            scene_description = data.prompt

            if is_digital:
                # Digital product: build device-holding composite prompt
                visual_desc = product.get("visual_description") or {}
                app_type = visual_desc.get("app_type", "mobile").lower() if isinstance(visual_desc, dict) else "mobile"
                is_mobile = "desktop" not in app_type and "web" not in app_type
                device_str = "iPhone" if is_mobile else "laptop screen"
                product_name = product.get("name") or "the app"

                device_action = (
                    f"standing naturally in front of the camera, holding an iPhone in one hand with the FRONT screen facing directly toward the camera and viewer, "
                    f"pointing at the phone screen with the other hand"
                    if is_mobile else
                    f"sitting at a desk, pointing at a laptop screen facing the camera"
                )

                composite_prompt = (
                    f"action: character {scene_description}, {device_action}, maintaining eye contact with camera\n"
                    f"anatomy: exactly one person with exactly two arms and two hands, accurate hands with realistic proportions, "
                    f"one hand holds {device_str}, other hand points at the screen or rests naturally AT THE PERSON'S SIDE\n"
                    f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
                    f"natural skin texture with visible pores and subtle grain, fine lines, skin imperfections, unretouched complexion, not airbrushed, natural highlight roll-off on skin\n"
                    f"device: the {device_str} FRONT screen faces the camera, the screen is fully visible to the viewer "
                    f"showing the {product_name} app interface from the provided product image, "
                    f"the viewer can clearly read and see the screen content, "
                    f"the back of the phone is NOT visible, only the front glass screen faces outward\n"
                    f"setting: {ctx['setting']}, tidy and clean with premium casual art direction\n"
                    f"lighting: soft directional natural window light, subtle shadows for depth, natural highlight roll-off on skin\n"
                    f"camera: iPhone 1x aesthetic, stationary POV camera, character does NOT hold the filming camera, "
                    f"clean but slightly organic composition, naturally blurred background\n"
                    f"style: candid UGC look, no filters, realism, high detail, skin texture, visible pores, micro skin texture, raw unedited photo quality\n"
                    f"negative: no smooth skin, no poreless skin, no plastic skin, no waxy skin, no beauty filter, no skin retouching, "
                    f"no third arm, no third hand, no extra limbs, no extra fingers, "
                    f"no airbrushed skin, no studio backdrop, no geometric distortion, "
                    f"no back of phone, no phone case visible, no rear camera lenses visible, "
                    f"no phone held backwards, no screen facing away from camera, "
                    f"no mutated hands, no floating limbs, no disconnected limbs, "
                    f"no arm crossing screen, no unnatural arm position, no character holding the filming camera, "
                    f"no flat lighting, no overexposed lighting, no blown highlights"
                )
            else:
                # Physical product: build product-holding composite prompt
                va = product.get("visual_description") or product.get("visual_analysis") or {}
                if isinstance(va, str):
                    visual_desc_str = va
                else:
                    visual_desc_str = va.get("visual_description", "the product")

                composite_prompt = (
                    f"action: character {scene_description}, casually presenting the product\n"
                    f"anatomy: exactly one person with exactly two arms and two hands, accurate hands with realistic proportions, "
                    f"one hand explicitly holds the product, other arm rests naturally TO THE PERSON'S SIDE\n"
                    f"character: infer exact appearance from reference image, preserve facial features and skin tone, "
                    f"natural skin texture with visible pores and subtle grain, fine lines, skin imperfections, unretouched complexion, not airbrushed, natural highlight roll-off on skin\n"
                    f"product: the {visual_desc_str} is clearly visible, "
                    f"preserve all visible text and logos exactly as in reference image, "
                    f"preserve exact product proportions, do not redesign or reinterpret the product\n"
                    f"setting: {ctx['setting']}, tidy and clean with premium casual art direction\n"
                    f"lighting: soft directional natural window light, subtle shadows for depth, natural highlight roll-off on skin\n"
                    f"camera: iPhone 1x aesthetic, clean but slightly organic composition, naturally blurred background, slightly uneven framing\n"
                    f"style: candid UGC look, no filters, realism, high detail, skin texture, visible pores, micro skin texture, raw unedited photo quality\n"
                    f"negative: no smooth skin, no poreless skin, no plastic skin, no waxy skin, no beauty filter, no skin retouching, "
                    f"no third arm, no third hand, no extra limbs, no extra fingers, "
                    f"no airbrushed skin, no studio backdrop, no geometric distortion, "
                    f"no mutated hands, no floating limbs, disconnected limbs, mutation, "
                    f"no arm crossing screen, no unnatural arm position, "
                    f"no flat lighting, no overexposed lighting, no blown highlights"
                )

            print(f"[Image Gen] UGC composite prompt built ({len(composite_prompt)} chars)")

            # Build reference images: influencer + product
            image_input = []
            if influencer_image_url:
                image_input.append(influencer_image_url)
            product_image = product.get("image_url")
            if product_image:
                image_input.append(product_image)

            # Create a "processing" shot record FIRST so the frontend
            # can immediately show the generating card with estimated time.
            shot_data = {
                "shot_type": "ugc",
                "status": "processing",
                "prompt": composite_prompt,
                "analysis_json": {
                    "mode": "ugc",
                    "scene_description": scene_description,
                },
            }
            if data.product_id:
                shot_data["product_id"] = data.product_id
            if data.influencer_id:
                shot_data["analysis_json"]["influencer_id"] = data.influencer_id
            if influencer_image_url:
                shot_data["analysis_json"]["influencer_image_url"] = influencer_image_url

            try:
                shot = await client.create_standalone_shot(shot_data)
                shot_id = shot.get("id")
                print(f"[Image Gen] UGC processing shot created: {shot_id}")
            except Exception as e:
                print(f"[Image Gen] WARN: Could not create processing shot: {e}")
                shot = {"id": None}
                shot_id = None

            # Spawn background task to generate the image and update the shot
            import asyncio

            async def _ugc_background_task(
                shot_id: str,
                composite_prompt: str,
                image_input: list,
                has_influencer: bool,
                aspect_ratio: str,
                quality: str,
                token: str,
                project_id: str,
            ):
                try:
                    image_url = await _generate_nanobanana_direct(
                        prompt=composite_prompt,
                        image_input=image_input,
                        has_influencer=has_influencer,
                        aspect_ratio=aspect_ratio,
                        quality=quality,
                    )
                    # Update the shot record with the completed image
                    if shot_id:
                        update_client = CoreAPIClient(token=token, project_id=project_id)
                        await update_client.update_shot(shot_id, {
                            "status": "image_completed",
                            "image_url": image_url,
                        })
                        print(f"[Image Gen] UGC shot {shot_id} completed: {image_url[:80]}...")
                except Exception as e:
                    print(f"[Image Gen] UGC background task failed: {e}")
                    if shot_id:
                        try:
                            update_client = CoreAPIClient(token=token, project_id=project_id)
                            await update_client.update_shot(shot_id, {"status": "failed"})
                        except Exception:
                            pass

            asyncio.create_task(_ugc_background_task(
                shot_id=shot_id,
                composite_prompt=composite_prompt,
                image_input=image_input,
                has_influencer=bool(influencer_image_url),
                aspect_ratio=data.aspect_ratio,
                quality=data.quality,
                token=user["token"],
                project_id=data.project_id,
            ))

            # Return immediately — the frontend will see the "processing" shot
            return {
                "status": "generating",
                "shots": [shot],
                "prompt": composite_prompt,
                "mode": data.mode,
            }

        # ── Path QA: Quick actions — always async via background task ──
        if data.quick_action:
            # Build reference images
            image_input = []
            if influencer_image_url:
                image_input.append(influencer_image_url)
            if data.reference_image_url:
                image_input.append(data.reference_image_url)
            # If we have a product, use its image as reference too
            if data.product_id:
                product = await client.get_product(data.product_id)
                product_image = product.get("image_url") if product else None
                if product_image and product_image not in image_input:
                    image_input.append(product_image)

            # Create processing shot immediately
            shot_data = {
                "shot_type": data.mode,
                "status": "processing",
                "prompt": data.prompt,
                "project_id": data.project_id,
                "analysis_json": {"quick_action": True},
            }
            if data.product_id:
                shot_data["product_id"] = data.product_id
            if data.influencer_id:
                shot_data["analysis_json"]["influencer_id"] = data.influencer_id

            try:
                shot = await client.create_standalone_shot(shot_data)
                shot_id = shot.get("id")
                print(f"[Image Gen] Quick action processing shot created: {shot_id}")
            except Exception as e:
                print(f"[Image Gen] WARN: Could not create QA shot: {e}")
                shot = {"id": None}
                shot_id = None

            # Background task
            import asyncio

            async def _qa_background(shot_id, prompt, image_input, has_inf, ar, q, token, pid):
                try:
                    image_url = await _generate_nanobanana_direct(
                        prompt=prompt, image_input=image_input,
                        has_influencer=has_inf, aspect_ratio=ar, quality=q,
                    )
                    if shot_id:
                        c = CoreAPIClient(token=token, project_id=pid)
                        await c.update_shot(shot_id, {"status": "image_completed", "image_url": image_url})
                        print(f"[Image Gen] QA shot {shot_id} completed")
                except Exception as e:
                    print(f"[Image Gen] QA background failed: {e}")
                    if shot_id:
                        try:
                            c = CoreAPIClient(token=token, project_id=pid)
                            await c.update_shot(shot_id, {"status": "failed"})
                        except Exception:
                            pass

            asyncio.create_task(_qa_background(
                shot_id=shot_id, prompt=data.prompt, image_input=image_input,
                has_inf=bool(influencer_image_url), ar=data.aspect_ratio, q=data.quality,
                token=user["token"], pid=data.project_id,
            ))

            return {
                "status": "generating",
                "shots": [shot],
                "prompt": data.prompt,
                "mode": data.mode,
            }

        # ── Path A: Product is present → use core API shotgeneration ──
        if data.product_id:
            # Core API only recognises "cinematic" or "iphone_look" as worker types,
            # but we preserve the real mode (e.g. "luxury") in analysis_json for filtering.
            shot_type = "cinematic" if data.mode == "cinematic" else "iphone_look"

            result = await client.generate_product_shot(
                product_id=data.product_id,
                shot_type=shot_type,
                variations=1,
                prompt=data.prompt,
                influencer_image_url=influencer_image_url,
            )

            # Always enrich analysis_json with real mode + influencer_id
            if result:
                for shot in result:
                    shot_id = shot.get("id")
                    if shot_id:
                        try:
                            existing_json = shot.get("analysis_json") or {}
                            existing_json["mode"] = data.mode
                            if data.influencer_id:
                                existing_json["influencer_id"] = data.influencer_id
                            await client.update_shot(shot_id, {"analysis_json": existing_json})
                        except Exception as e:
                            print(f"[WARN] Could not store metadata on shot {shot_id}: {e}")

            return {
                "status": "generating",
                "shots": result,
                "prompt": data.prompt,
                "mode": data.mode,
            }

        # ── Path B/C: No product — async NanoBanana direct ──
        # Build reference images list
        image_input = []
        if influencer_image_url:
            image_input.append(influencer_image_url)
        if data.reference_image_url:
            image_input.append(data.reference_image_url)

        # Create processing shot immediately — use actual mode for shot_type
        shot_data = {
            "shot_type": data.mode,
            "status": "processing",
            "prompt": data.prompt,
            "project_id": data.project_id,
            "analysis_json": {"mode": data.mode},
        }
        if data.influencer_id:
            shot_data["analysis_json"]["influencer_id"] = data.influencer_id
        if influencer_image_url:
            shot_data["analysis_json"]["influencer_image_url"] = influencer_image_url

        try:
            shot = await client.create_standalone_shot(shot_data)
            shot_id = shot.get("id")
            print(f"[Image Gen] Standalone processing shot created: {shot_id}")
        except Exception as e:
            print(f"[Image Gen] WARN: Could not create shot record: {e}")
            shot = {"id": None}
            shot_id = None

        # Background task
        import asyncio

        async def _direct_background(shot_id, prompt, image_input, has_inf, ar, q, token, pid):
            try:
                image_url = await _generate_nanobanana_direct(
                    prompt=prompt, image_input=image_input,
                    has_influencer=has_inf, aspect_ratio=ar, quality=q,
                )
                if shot_id:
                    c = CoreAPIClient(token=token, project_id=pid)
                    await c.update_shot(shot_id, {"status": "image_completed", "image_url": image_url})
                    print(f"[Image Gen] Shot {shot_id} completed")
            except Exception as e:
                print(f"[Image Gen] Background gen failed: {e}")
                if shot_id:
                    try:
                        c = CoreAPIClient(token=token, project_id=pid)
                        await c.update_shot(shot_id, {"status": "failed"})
                    except Exception:
                        pass

        asyncio.create_task(_direct_background(
            shot_id=shot_id, prompt=data.prompt, image_input=image_input,
            has_inf=bool(influencer_image_url), ar=data.aspect_ratio, q=data.quality,
            token=user["token"], pid=data.project_id,
        ))

        return {
            "status": "generating",
            "shots": [shot],
            "prompt": data.prompt,
            "mode": data.mode,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image generation failed: {str(e)}")


async def _generate_nanobanana_direct(
    prompt: str,
    image_input: list,
    has_influencer: bool = False,
    aspect_ratio: str = "9:16",
    quality: str = "4k",
) -> str:
    """Call NanoBanana Pro API directly (not via core API worker).

    Used for influencer-only, upload-only, and prompt-only generation
    where there's no product_id to route through the core API.

    Returns the generated image URL.
    """
    import os
    import json
    import httpx
    from pathlib import Path
    from dotenv import load_dotenv

    from env_loader import load_env
    load_env(Path(__file__))

    kie_url = os.getenv("KIE_API_URL", "https://api.kie.ai")
    kie_key = os.getenv("KIE_API_KEY", "")

    # Build negative prompt based on whether an influencer is present
    if has_influencer:
        negative_prompt = (
            "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, "
            "(extra limb:1.5), (third arm:1.5), (extra hand:1.5), missing limb, floating limbs, "
            "(mutated hands and fingers:1.4), disconnected limbs, mutation, mutated, ugly, "
            "disgusting, blurry, amputation, different person, extra fingers"
        )
    else:
        negative_prompt = (
            "(deformed, distorted, disfigured:1.3), poorly drawn, bad anatomy, wrong anatomy, "
            "extra limb, missing limb, floating limbs, (mutated hands and fingers:1.4), "
            "disconnected limbs, mutation, mutated, ugly, disgusting, blurry, amputation, "
            "extra fingers"
        )

    resolution = "4K" if quality == "4k" else "2K"

    payload = {
        "model": "nano-banana-pro",
        "input": {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "aspect_ratio": aspect_ratio,
            "resolution": resolution,
        },
    }

    # Only include image_input if we have reference images
    if image_input:
        payload["input"]["image_input"] = image_input

    headers = {
        "Authorization": f"Bearer {kie_key}",
        "Content-Type": "application/json",
    }

    print(f"[NanoBanana Direct] Prompt: {prompt[:80]}...")
    print(f"[NanoBanana Direct] Images: {len(image_input)}, Aspect: {aspect_ratio}")

    async with httpx.AsyncClient(timeout=30.0) as http_client:
        endpoint = f"{kie_url}/api/v1/jobs/createTask"
        resp = await http_client.post(endpoint, headers=headers, json=payload)

        if resp.status_code != 200:
            raise RuntimeError(f"NanoBanana API error ({resp.status_code}): {resp.text[:500]}")

        result = resp.json()
        if result.get("code") != 200:
            raise RuntimeError(f"NanoBanana API error: {result.get('msg', str(result))}")

        task_id = result["data"]["taskId"]
        print(f"[NanoBanana Direct] Task: {task_id}")

    # Poll for completion
    import asyncio
    poll_endpoint = f"{kie_url}/api/v1/jobs/recordInfo"

    for i in range(60):  # 10 minutes max
        await asyncio.sleep(10)

        try:
            async with httpx.AsyncClient(timeout=15.0) as http_client:
                resp = await http_client.get(
                    poll_endpoint,
                    headers=headers,
                    params={"taskId": task_id},
                )
                result = resp.json()
        except Exception as e:
            print(f"[NanoBanana Direct] Poll error: {e}")
            continue

        if result.get("code") != 200:
            continue

        data = result.get("data", {})
        state = data.get("state", "processing").lower()

        if state == "success":
            result_json = data.get("resultJson", "{}")
            if isinstance(result_json, str):
                result_json = json.loads(result_json)
            image_url = result_json.get("resultUrls", [None])[0]
            if image_url:
                print(f"[NanoBanana Direct] Image ready! ({i * 10}s)")
                return image_url
        elif state == "fail":
            fail_msg = data.get("failMsg", "Unknown error")
            raise RuntimeError(f"NanoBanana generation failed: {fail_msg}")

        print(f"[NanoBanana Direct] Generating... ({i * 10}s)")

    raise RuntimeError("NanoBanana generation timed out after 10 minutes")


# ---------------------------------------------------------------------------
# Generate AI Influencer — persona + profile photo in one shot
# ---------------------------------------------------------------------------

GENERATE_INFLUENCER_SYSTEM_PROMPT = """You are an AI character designer for a UGC (User-Generated Content) video platform.

Your job is to invent a NEW, unique, fictional influencer persona and produce a NanoBanana Pro image-generation prompt that will create their ultra-realistic profile photo.

**PERSONA REQUIREMENTS:**
- Age range: 21–35 years old
- Ensure DIVERSITY across: ethnicity, gender, facial structure, hair texture, skin tone
- Give them a realistic, culturally appropriate first name (no surnames)
- Do NOT reproduce any real or copyrighted person
- Include a 1-2 sentence personality/description suitable for a content creator bio

**IMAGE PROMPT REQUIREMENTS — follow NanoBanana Pro specifications exactly:**
The image prompt MUST produce a STRAIGHT-ON, EYE-LEVEL portrait photo — NOT a selfie.

Structure the prompt as a single paragraph in this order:
1. Aspect ratio: 9:16
2. Camera position: ALWAYS straight-on, eye-level, camera at the same height as the subject's face, lens pointing directly at the face
3. Character description: age, gender, detailed physical traits (skin tone, eye color, hair color/texture/style, brow shape, lip shape)
4. Face orientation: face centered in frame, symmetrical composition, chin level (not tilted), both eyes fully visible and looking directly into the camera lens
5. Expression: subtle, natural, relaxed (no exaggerated smile)
6. Arms and hands: arms relaxed at sides or resting naturally, hands NOT holding a phone or camera, NOT visible in frame
7. Skin details (CRITICAL): natural skin texture with visible pores, fine peach fuzz, slight imperfections, not airbrushed
8. Setting: a realistic casual environment (apartment, coffee shop, park, car, kitchen — pick one)
9. Camera style: eye-level portrait photo, slight amateur quality, shot on iPhone 15 Pro, the subject is NOT holding the camera
10. Lighting: be extremely specific (e.g. "warm golden hour light from side window", "soft diffused north-facing window light")
11. Style keywords: candid UGC realism, no filters, realism, high detail, skin texture, portrait photography
12. Negative constraints: no tilted camera angle, no overhead angle, no selfie angle, no arm reaching toward camera, no hand holding phone, no visible phone or camera in frame, no looking up at camera from below, no chin-up pose, no studio lighting, no airbrushed skin, no professional camera, no text overlays, no watermarks, no geometric distortion, no extra fingers

**OUTPUT FORMAT — return ONLY valid JSON with these exact keys:**
{
  "name": "Sofia",
  "gender": "Female",
  "age": "26-year-old",
  "description": "Warm and relatable beauty creator who shares honest product reviews with her followers.",
  "nano_banana_prompt": "9:16. Straight-on eye-level portrait. A 26-year-old woman with warm olive skin, dark brown eyes, and long wavy chestnut hair, face centered in frame, looking directly into the camera lens at eye level..."
}

RULES:
- Return ONLY the JSON object, no explanation or markdown
- The nano_banana_prompt must be one continuous paragraph (no line breaks inside)
- Be extremely specific with physical traits — vague prompts produce unrealistic results
- CRITICAL: The camera MUST be at eye level, pointing straight at the face. No overhead selfie angles. No arm visible holding a phone.
- The prompt must NOT use the word "selfie" — use "portrait" or "portrait photo" instead
- Every prompt must pass: face centered, both eyes visible, eye-level camera, natural expression, visible skin texture, real-world environment"""


@router.post("/generate-influencer")
async def generate_influencer(user: dict = Depends(get_current_user)):
    """Generate a random AI influencer persona + NanoBanana Pro profile photo.

    Flow:
    1. GPT-4o generates persona (name, gender, description) + NanoBanana prompt
    2. NanoBanana Pro generates the profile photo from the prompt
    3. Returns all data for the frontend to auto-fill the influencer form
    """
    import openai
    import json
    import os
    from pathlib import Path
    from dotenv import load_dotenv

    from env_loader import load_env
    load_env(Path(__file__))

    # ── Step 1: Generate persona + image prompt via GPT ──
    print("[Generate Influencer] Step 1/2: Generating persona via GPT-4o...")
    try:
        client = openai.OpenAI()
        resp = client.chat.completions.create(
            model="gpt-4o",
            temperature=1.0,  # High temperature for diverse outputs
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": GENERATE_INFLUENCER_SYSTEM_PROMPT},
                {"role": "user", "content": "Generate a new, unique AI influencer now. Make them diverse and interesting."},
            ],
            max_tokens=600,
        )
        raw = resp.choices[0].message.content.strip()
        persona = json.loads(raw)

        name = persona.get("name", "Creator")
        gender = persona.get("gender", "Female")
        age = persona.get("age", "25-year-old")
        description = persona.get("description", "")
        nano_prompt = persona.get("nano_banana_prompt", "")

        if not nano_prompt:
            raise ValueError("GPT returned empty nano_banana_prompt")

        print(f"[Generate Influencer] Persona: {name} ({gender}, {age})")
        print(f"[Generate Influencer] Prompt: {nano_prompt[:100]}...")

    except Exception as e:
        print(f"[Generate Influencer] GPT failed: {e}")
        raise HTTPException(status_code=500, detail=f"Persona generation failed: {str(e)}")

    # ── Step 2: Generate profile photo via NanoBanana Pro ──
    print("[Generate Influencer] Step 2/2: Generating profile photo via NanoBanana Pro...")
    try:
        image_url = await _generate_nanobanana_direct(
            prompt=nano_prompt,
            image_input=[],       # No reference images — pure text-to-image
            has_influencer=False,  # No face reference to preserve
            aspect_ratio="9:16",
            quality="4k",
        )
        print(f"[Generate Influencer] Photo generated: {image_url[:80]}...")
    except Exception as e:
        print(f"[Generate Influencer] NanoBanana failed: {e}")
        raise HTTPException(status_code=500, detail=f"Profile photo generation failed: {str(e)}")

    return {
        "name": name,
        "gender": gender,
        "age": age,
        "description": description,
        "image_url": image_url,
        "nano_banana_prompt": nano_prompt,
    }


# ---------------------------------------------------------------------------
# Shared: Smart-split 21:9 sheet into 4 views + upload to Supabase
# ---------------------------------------------------------------------------

async def _smart_split_and_upload(
    sheet_url: str,
    *,
    storage_bucket: str = "influencer-images",
    path_prefix: str = "identity",
    view_labels: list[str] | None = None,
    log_prefix: str = "[Smart Split]",
) -> list[str]:
    """Download a 21:9 composite sheet, detect gaps, split into 4 views, upload each.

    Returns a list of 4 public URLs for the individual views.
    Used by both character identity and product shots pipelines.
    """
    import io
    import os
    import uuid
    import httpx
    import numpy as np
    from PIL import Image
    from supabase import create_client

    if view_labels is None:
        view_labels = ["view_1", "view_2", "view_3", "view_4"]

    # Download the sheet
    async with httpx.AsyncClient(timeout=30.0) as http_client:
        img_resp = await http_client.get(sheet_url)
        img_resp.raise_for_status()
        img_bytes = img_resp.content

    img = Image.open(io.BytesIO(img_bytes))
    width, height = img.size
    print(f"{log_prefix} Sheet dimensions: {width}x{height}")

    # Convert to grayscale numpy array for analysis
    gray = np.array(img.convert('L'))

    # ── Step A: Detect and crop text/label strip at the bottom ──
    row_stds = gray.std(axis=1)
    content_bottom = height
    for y in range(height - 1, height // 2, -1):
        if row_stds[y] > 35:
            content_bottom = min(y + 2, height)
            break

    if content_bottom < height:
        print(f"{log_prefix} Detected text strip: cropping bottom {height - content_bottom}px (keeping {content_bottom}px)")

    # ── Step B: Detect vertical gaps between views ──
    content_area = gray[:content_bottom, :]
    col_means = content_area.mean(axis=0)
    col_stds = content_area.std(axis=0)

    # Separator columns: high brightness (near-white background) AND low variance (uniform)
    is_separator = (col_means > 220) & (col_stds < 25)

    # Find groups of consecutive separator columns (minimum 8px wide to avoid noise)
    gaps = []
    in_gap = False
    gap_start = 0
    min_gap_width = 8

    for x in range(width):
        if is_separator[x] and not in_gap:
            gap_start = x
            in_gap = True
        elif (not is_separator[x] or x == width - 1) and in_gap:
            gap_end = x
            if gap_end - gap_start >= min_gap_width:
                gaps.append((gap_start, gap_end))
            in_gap = False

    print(f"{log_prefix} Detected {len(gaps)} gaps: {[(g[0], g[1], g[1]-g[0]) for g in gaps]}")

    # We need exactly 3 internal gaps to get 4 views
    margin = int(width * 0.05)
    internal_gaps = [g for g in gaps if g[0] > margin and g[1] < width - margin]
    print(f"{log_prefix} Internal gaps (excluding margins): {len(internal_gaps)}")

    if len(internal_gaps) >= 3:
        sorted_gaps = sorted(internal_gaps, key=lambda g: g[1] - g[0], reverse=True)[:3]
        sorted_gaps.sort(key=lambda g: g[0])
        split_points = [0] + [(g[0] + g[1]) // 2 for g in sorted_gaps] + [width]
        print(f"{log_prefix} Smart split points: {split_points}")
    else:
        print(f"{log_prefix} Gap detection insufficient ({len(internal_gaps)} gaps), falling back to equal split")
        col_w = width // 4
        split_points = [0, col_w, col_w * 2, col_w * 3, width]

    # ── Step C: Crop, upload each view ──
    views = []
    sb = create_client(
        os.getenv("SUPABASE_URL"),
        os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY"),
    )

    for i in range(4):
        left = split_points[i]
        right = split_points[i + 1]
        crop = img.crop((left, 0, right, content_bottom))

        buf = io.BytesIO()
        crop.save(buf, format="PNG", quality=95)
        buf.seek(0)
        crop_bytes = buf.read()

        label = view_labels[i] if i < len(view_labels) else f"view_{i+1}"
        filename = f"{path_prefix}/{uuid.uuid4().hex[:12]}_{label}.png"
        sb.storage.from_(storage_bucket).upload(
            filename, crop_bytes,
            file_options={"content-type": "image/png", "upsert": "true"},
        )
        view_url = sb.storage.from_(storage_bucket).get_public_url(filename)
        views.append(view_url)
        crop_w, crop_h = crop.size
        print(f"{log_prefix} View {i+1}/4 ({label}): {crop_w}x{crop_h} uploaded")

    print(f"{log_prefix} All 4 views uploaded successfully")
    return views


# ---------------------------------------------------------------------------
# Generate Identity — character description + character sheet from profile
# ---------------------------------------------------------------------------

CASTING_DIRECTOR_SYSTEM_PROMPT = """You are an International Casting Director specialized in creating ultra-realistic character sheets in the style of an IMG agency.

You will receive a reference profile photo of a character. Your job is to:

1. ANALYZE the reference photo and produce a detailed character description covering: age estimate, gender, ethnicity, height/build estimate, skin tone and texture details, facial geometry (jaw, cheekbones, nose, lips, eye shape and color, eyebrows), hair (color, texture, style, length), any visible accessories (glasses, earrings, piercings), and approximate BMI/body type.

2. GENERATE a technically precise NanoBanana Pro prompt to create a character sheet in 21:9 horizontal format composed of 4 views in a single image:
   - CLOSEUP (front headshot)
   - Front medium shot
   - 90° profile medium shot
   - Full body front

All 4 views must maintain absolute 1:1 identity with the reference photo.

VISUAL INTEGRITY RULES (CRITICAL):
- The four views must appear complete, fully visible, and without any cropping
- No view may be out of frame, partially visible, or cut off by the canvas edges
- Cropping the head, ears, limbs, feet, or any anatomical part is strictly forbidden
- Each view must be centered within its column
- ABSOLUTELY NO TEXT of any kind in the image: no labels, no captions, no titles, no view names (like "HEADSHOT", "FRONT MEDIUM"), no measurements, no stats, no height/weight/body fat text, no typography, no watermarks, no numbering, no letters. The image must contain ONLY the four photographic views and nothing else.

HUMAN IDENTITY RULES:
- Maintain exact anatomical fidelity: 1:1 facial geometry, bone structure, jawline, cheekbones, nose, lips, eyes (shape and color), eyebrows, real skin texture, freckles, moles, scars
- Body proportions must be consistent with the facial identity
- If accessories are visible in reference (glasses, earrings, piercings), maintain them faithfully
- NO beautifying, NO stylizing, NO slimming, NO smoothing skin, NO CGI look, NO beauty filters, NO artificial symmetry

MANDATORY VISUAL FORMAT:
A single horizontal image composed of 4 columns: front closeup, front medium shot, exact 90° profile, and full body front. Clean composition with uniform compact spacing. Minimal negative space. No overlap. The horizontal format must fit all four views completely within the frame.

CLOTHING AND FOOTWEAR:
Clothing must be consistent across all views. If any view is not full body, the character must still wear footwear consistent with the outfit.

MANDATORY LIGHTING:
Diffuse frontal light similar to a north-facing window. Uniform lighting. No harsh shadows. No dramatic lighting. No rim light. No gradients. Natural rectangular catchlights. Low clinical contrast.

BACKGROUND:
Seamless uniform light gray background #F7F7F7. No texture, no gradient, no vignette, no depth.

CAMERA:
Professional full-frame camera, 85mm lens, f/8, ISO 100, clinical sharpness, both eyes in focus, no angular distortion. Absolute photographic realism.

SKIN DETAIL:
Real texture with visible pores, micro detail, natural fine hair. No plastic effect, no glow, no HDR, no exaggerated grain. Must look like a real professional test photograph.

MEASUREMENTS:
Include clear character measurements: height, weight, approximate body fat percentage, coherent key body measurements.

AESTHETIC TONE:
International agency digitals. Clean model test. Professional casting. Neutral. Clinical. Objective.

NEGATIVE RESTRICTIONS:
No CGI, no illustration, no 3D render, no plastic skin, no glow, no filters, no dramatic makeup, no fashion stylization, no cinematic color grading, no deep shadows, no artificial symmetry. ABSOLUTELY NO TEXT, NO LABELS, NO CAPTIONS, NO MEASUREMENTS TEXT, NO TYPOGRAPHY of any kind anywhere in the image. The image must be purely photographic with zero text elements.

OUTPUT FORMAT — return ONLY valid JSON with these exact keys:
{
  "description": "Detailed multi-sentence character description covering all physical traits, measurements, and distinctive features...",
  "nano_banana_prompt": "21:9. Professional character sheet of [detailed character description]. Four views arranged horizontally: front closeup headshot, front medium shot, exact 90-degree profile medium shot, and full body front view..."
}

RULES:
- Return ONLY the JSON object, no explanation, no markdown
- The description must be detailed and cover ALL physical traits visible in the reference
- The nano_banana_prompt must be one continuous paragraph
- The prompt must reference "Using input image 1 for face identity" and "Keep facial features exactly consistent with reference"
- Include the instruction "four views in a single horizontal image" explicitly in the prompt
- Include scale/measurements in the description field, NOT as text in the image
- CRITICAL: The nano_banana_prompt must include "no text, no labels, no captions, no typography, no measurements text" in the negative constraints
- The generated image must contain ONLY the 4 photographic views — zero text elements"""


class GenerateIdentityRequest(BaseModel):
    image_url: str


@router.post("/generate-identity")
async def generate_identity(
    data: GenerateIdentityRequest,
    user: dict = Depends(get_current_user),
):
    """Generate character description + 4-view character sheet from a profile photo.

    Flow:
    1. GPT-4o Vision analyzes the profile photo → description + NanoBanana prompt
    2. NanoBanana Pro generates 21:9 character sheet (4 views in one image)
    3. Pillow splits the image into 4 equal columns
    4. Each view is uploaded to Supabase storage
    5. Returns description + 4 view URLs
    """
    import openai
    import json
    import uuid
    import io
    from pathlib import Path
    from dotenv import load_dotenv

    from env_loader import load_env
    load_env(Path(__file__))

    # ── Step 1: GPT-4o Vision → description + character sheet prompt ──
    print(f"[Generate Identity] Step 1/3: Analyzing profile via GPT-4o Vision...")
    print(f"[Generate Identity] Image URL: {data.image_url[:100]}...")
    try:
        client = openai.OpenAI()

        _identity_messages = [
            {"role": "system", "content": CASTING_DIRECTOR_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this character reference photo and generate the character description and NanoBanana Pro character sheet prompt. Return valid JSON."},
                    {"type": "image_url", "image_url": {"url": data.image_url}},
                ],
            },
        ]

        # Attempt 1: with json_object mode
        resp = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=_identity_messages,
            max_tokens=1500,
        )
        raw = resp.choices[0].message.content
        finish_reason = resp.choices[0].finish_reason
        refusal = getattr(resp.choices[0].message, 'refusal', None)
        print(f"[Generate Identity] GPT attempt 1 — finish_reason={finish_reason}, refusal={refusal}, content={'None' if raw is None else f'{len(raw)} chars'}")

        if not raw:
            # Attempt 2: drop json_object mode (known issue with Vision + JSON mode)
            print("[Generate Identity] Retrying WITHOUT response_format (Vision + JSON mode quirk)...")
            import asyncio as _aio
            await _aio.sleep(2)
            resp = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.4,
                messages=_identity_messages,
                max_tokens=1500,
            )
            raw = resp.choices[0].message.content
            finish_reason = resp.choices[0].finish_reason
            print(f"[Generate Identity] GPT attempt 2 — finish_reason={finish_reason}, content={'None' if raw is None else f'{len(raw)} chars'}")
            if not raw:
                raise ValueError(f"GPT returned empty response twice (finish_reason={finish_reason})")

        # Extract JSON (may be wrapped in markdown fences when not using json_object mode)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            # Strip ```json ... ``` wrapper
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(cleaned)

        description = result.get("description", "")
        nano_prompt = result.get("nano_banana_prompt", "")

        if not nano_prompt:
            raise ValueError("GPT returned empty nano_banana_prompt")

        print(f"[Generate Identity] Description: {description[:100]}...")
        print(f"[Generate Identity] Prompt: {nano_prompt[:100]}...")

    except Exception as e:
        print(f"[Generate Identity] GPT failed: {e}")
        raise HTTPException(status_code=500, detail=f"Character analysis failed: {str(e)}")

    # ── Step 2: NanoBanana Pro → 21:9 character sheet (with retry) ──
    import asyncio
    max_retries = 2
    sheet_url = None
    last_error = None

    for attempt in range(1, max_retries + 2):  # 1, 2, 3 = original + 2 retries
        print(f"[Generate Identity] Step 2/3: NanoBanana attempt {attempt}/{max_retries + 1}...")
        try:
            sheet_url = await _generate_nanobanana_direct(
                prompt=nano_prompt,
                image_input=[data.image_url],  # Reference image for face identity
                has_influencer=True,            # Preserve face from reference
                aspect_ratio="21:9",
                quality="4k",
            )
            print(f"[Generate Identity] Character sheet generated: {sheet_url[:80]}...")
            break  # Success — exit retry loop
        except Exception as e:
            last_error = e
            print(f"[Generate Identity] NanoBanana attempt {attempt} failed: {e}")
            if attempt <= max_retries:
                delay = 5 * attempt  # 5s, 10s
                print(f"[Generate Identity] Retrying in {delay}s...")
                await asyncio.sleep(delay)

    if not sheet_url:
        raise HTTPException(status_code=500, detail=f"Character sheet generation failed after {max_retries + 1} attempts: {str(last_error)}")

    # ── Step 3: Smart-split 21:9 image into 4 views + upload ──
    print("[Generate Identity] Step 3/3: Splitting character sheet into 4 views...")
    try:
        views = await _smart_split_and_upload(
            sheet_url,
            storage_bucket="influencer-images",
            path_prefix="identity",
            view_labels=["closeup", "front_medium", "profile_90", "full_body"],
            log_prefix="[Generate Identity]",
        )
    except Exception as e:
        print(f"[Generate Identity] Image split failed: {e}")
        import traceback; traceback.print_exc()
        # Return description even if splitting fails, with the full sheet URL
        return {
            "description": description,
            "character_sheet_url": sheet_url,
            "views": [sheet_url],  # Fallback: just the full sheet
        }

    return {
        "description": description,
        "character_sheet_url": sheet_url,
        "views": views,
    }


# ---------------------------------------------------------------------------
# Generate Product Shots — 4-view product sheet from a product image
# ---------------------------------------------------------------------------

PRODUCT_IMAGING_DIRECTOR_PROMPT = """You are an International Product Imaging Director specialized in creating ultra-realistic product sheets in the style of high-end commercial catalog photography.

You will receive a reference product image. Your job is to:

1. ANALYZE the product reference image and identify its exact form factor, materials, colors, labeling, and functional components.

2. GENERATE a technically precise NanoBanana Pro prompt to create a product sheet in 21:9 horizontal format composed of 4 views in a single image:
   - CLOSED PRODUCT (hero front view)
   - OPEN PRODUCT (functional/open state if applicable)
   - DETAIL VIEW (close-up of texture, brush, mechanism, or material)
   - ALTERNATIVE ANGLE (side view, 45°, or back view)

All 4 views must maintain absolute 1:1 product identity.

VISUAL INTEGRITY RULE (CRITICAL):
The four views must appear complete, fully visible, and without any cropping. No view may be out of frame, partially visible, or cut off by the canvas edges. The canvas must automatically adjust to perfectly contain the four columns. Cropping any part of the product is strictly forbidden. Each view must be centered within its column.

It is strictly forbidden to generate text, letters, logos reinterpretation, typographic marks, labels, captions, watermarks, numbering, or any graphic element not physically present on the original product.

PRODUCT FIDELITY MODE (CRITICAL):
The product must maintain exact visual fidelity across all views: identical shape, proportions, materials, finishes, colors, reflections, engravings, labels, and branding placement. No redesign, no reinterpretation, no simplification.

All physical details visible in the reference must be preserved, including micro details such as texture, seams, joints, engravings, printing, and wear if present.

If the product includes moving parts or functional states (such as caps, brushes, lids, applicators), they must be shown accurately in the open view without altering proportions or design.

MATERIAL AND TEXTURE ACCURACY:
Materials must appear physically correct and realistic: metal, plastic, glass, rubber, fabric, or composite materials must reflect light accurately. Surface finish must match the reference exactly (matte, satin, glossy, metallic, brushed, etc.).

No CGI look, no plastic rendering, no exaggerated reflections, no artificial smoothing.

MANDATORY VISUAL FORMAT:
A single horizontal image composed of 4 columns: closed hero view, open/functional view, macro detail view, and alternative angle. The composition must be clean with uniform but compact spacing. The negative space between the four views must be minimal and controlled. No overlap. Each view must occupy its column correctly without invading others or being cropped. The format must adapt to ensure all four views fit perfectly within frame.

LIGHTING (MANDATORY):
Soft frontal diffused lighting similar to a professional product studio. Uniform illumination. No harsh shadows. No dramatic lighting. No rim light. No gradients. Subtle natural reflections consistent with material. Low contrast, clean commercial lighting.

BACKGROUND:
Seamless uniform light gray background #F7F7F7 with no texture, no gradient, no vignette, and no depth.

CAMERA:
Professional full-frame camera, 85mm lens equivalent, f/8, ISO 100, high sharpness, no distortion, no perspective exaggeration. True-to-life product proportions.

SCALE AND PROPORTION (MANDATORY):
The product must maintain realistic scale and proportions consistent with real-world manufacturing. Relative dimensions between components must remain accurate. No distortion or resizing between views.

AESTHETIC TONE:
High-end commercial product photography. Clean catalog style. Neutral. Clinical. Objective. No artistic direction. No lifestyle context.

GLOBAL NEGATIVE RESTRICTIONS:
No CGI, no illustration, no 3D render look, no glow, no filters, no dramatic reflections, no cinematic grading, no exaggerated shadows, no stylization. ABSOLUTELY NO TEXT, NO LABELS, NO CAPTIONS, NO TYPOGRAPHY of any kind. The image must contain ONLY the four photographic product views.

It must look like a real product photographed in a professional studio.

OUTPUT FORMAT — return ONLY valid JSON with these exact keys:
{
  "nano_banana_prompt": "21:9. Professional product sheet of [detailed product description]. Four views arranged horizontally: closed hero front view, open/functional state, macro detail close-up, and alternative angle view..."
}

RULES:
- Return ONLY the JSON object, no explanation, no markdown
- The nano_banana_prompt must be one continuous paragraph
- The prompt must reference "Using input image 1 for product identity" and "Keep product appearance exactly consistent with reference"
- Include the instruction "four views in a single horizontal image" explicitly in the prompt
- CRITICAL: The nano_banana_prompt must include "no text, no labels, no captions, no typography" in the negative constraints
- The generated image must contain ONLY the 4 photographic product views — zero text elements"""


class GenerateProductShotsRequest(BaseModel):
    image_url: str


@router.post("/generate-product-shots")
async def generate_product_shots(
    data: GenerateProductShotsRequest,
    user: dict = Depends(get_current_user),
):
    """Generate a 4-view product sheet from a product image.

    Flow:
    1. GPT-4o Vision analyzes the product → generates NanoBanana prompt
    2. NanoBanana Pro generates 21:9 product sheet (4 views)
    3. Smart-split into 4 individual views + upload to Supabase
    4. Returns 4 view URLs
    """
    import openai
    import json
    from pathlib import Path
    from dotenv import load_dotenv

    from env_loader import load_env
    load_env(Path(__file__))

    # ── Step 1: GPT-4o Vision → NanoBanana prompt ──
    print(f"[Generate Product Shots] Step 1/3: Analyzing product via GPT-4o Vision...")
    print(f"[Generate Product Shots] Image URL: {data.image_url[:100]}...")
    try:
        client = openai.OpenAI()

        _product_messages = [
            {"role": "system", "content": PRODUCT_IMAGING_DIRECTOR_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this product reference image and generate the NanoBanana Pro product sheet prompt. Return valid JSON."},
                    {"type": "image_url", "image_url": {"url": data.image_url}},
                ],
            },
        ]

        # Attempt 1: with json_object mode
        resp = client.chat.completions.create(
            model="gpt-4o",
            temperature=0.4,
            response_format={"type": "json_object"},
            messages=_product_messages,
            max_tokens=1500,
        )
        raw = resp.choices[0].message.content
        finish_reason = resp.choices[0].finish_reason
        print(f"[Generate Product Shots] GPT attempt 1 — finish_reason={finish_reason}, content={'None' if raw is None else f'{len(raw)} chars'}")

        if not raw:
            # Attempt 2: drop json_object mode (Vision + JSON mode quirk)
            print("[Generate Product Shots] Retrying WITHOUT response_format...")
            import asyncio as _aio
            await _aio.sleep(2)
            resp = client.chat.completions.create(
                model="gpt-4o",
                temperature=0.4,
                messages=_product_messages,
                max_tokens=1500,
            )
            raw = resp.choices[0].message.content
            finish_reason = resp.choices[0].finish_reason
            print(f"[Generate Product Shots] GPT attempt 2 — finish_reason={finish_reason}, content={'None' if raw is None else f'{len(raw)} chars'}")
            if not raw:
                raise ValueError(f"GPT returned empty response twice (finish_reason={finish_reason})")

        # Extract JSON (may be wrapped in markdown fences)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        result = json.loads(cleaned)

        nano_prompt = result.get("nano_banana_prompt", "")
        if not nano_prompt:
            raise ValueError("GPT returned empty nano_banana_prompt")

        print(f"[Generate Product Shots] Prompt: {nano_prompt[:120]}...")

    except Exception as e:
        print(f"[Generate Product Shots] GPT failed: {e}")
        raise HTTPException(status_code=500, detail=f"Product analysis failed: {str(e)}")

    # ── Step 2: NanoBanana Pro → 21:9 product sheet (with retry) ──
    import asyncio
    max_retries = 2
    sheet_url = None
    last_error = None

    for attempt in range(1, max_retries + 2):
        print(f"[Generate Product Shots] Step 2/3: NanoBanana attempt {attempt}/{max_retries + 1}...")
        try:
            sheet_url = await _generate_nanobanana_direct(
                prompt=nano_prompt,
                image_input=[data.image_url],
                has_influencer=False,
                aspect_ratio="21:9",
                quality="4k",
            )
            print(f"[Generate Product Shots] Product sheet generated: {sheet_url[:80]}...")
            break
        except Exception as e:
            last_error = e
            print(f"[Generate Product Shots] NanoBanana attempt {attempt} failed: {e}")
            if attempt <= max_retries:
                delay = 5 * attempt
                print(f"[Generate Product Shots] Retrying in {delay}s...")
                await asyncio.sleep(delay)

    if not sheet_url:
        raise HTTPException(status_code=500, detail=f"Product sheet generation failed after {max_retries + 1} attempts: {str(last_error)}")

    # ── Step 3: Smart-split 21:9 image into 4 views + upload ──
    print("[Generate Product Shots] Step 3/3: Splitting product sheet into 4 views...")
    try:
        views = await _smart_split_and_upload(
            sheet_url,
            storage_bucket="product-images",
            path_prefix="product_shots",
            view_labels=["hero_front", "open_functional", "detail_macro", "alt_angle"],
            log_prefix="[Generate Product Shots]",
        )
    except Exception as e:
        print(f"[Generate Product Shots] Image split failed: {e}")
        import traceback; traceback.print_exc()
        return {
            "product_sheet_url": sheet_url,
            "views": [sheet_url],
        }

    return {
        "product_sheet_url": sheet_url,
        "views": views,
    }
