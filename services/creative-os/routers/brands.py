"""Brand Studio API — scrape, ideas, Fal render."""
from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from auth import get_current_user
from core_api_client import CoreAPIClient
from services import brand_studio
from services.credit_costs import (
    get_brand_studio_ideas_credit_cost,
    get_brand_studio_slide_credit_cost,
)

router = APIRouter(prefix="/brands", tags=["brands"])


class ScrapeRequest(BaseModel):
    url: str


class SaveRequest(BaseModel):
    brand: dict = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    prompt: str
    n: int = 1
    imageUrls: list[str] = Field(default_factory=list)
    brand: str = ""
    postId: str = ""
    slide: str = ""
    role: str = ""


class IdeasRequest(BaseModel):
    brand: dict = Field(default_factory=dict)
    direction: str = ""
    count: int = 3
    lang: str = "en"


class StoreImageRequest(BaseModel):
    url: str
    brand: str = "brand"
    postId: str = "0"
    slide: str = "0"
    role: str = ""


class SessionSaveRequest(BaseModel):
    session: dict = Field(default_factory=dict)


class PickLogoRequest(BaseModel):
    logos: list = Field(default_factory=list)
    role: str = ""
    layout: str = ""
    colors: list = Field(default_factory=list)
    slideIndex: int = 0
    hasProductRef: bool = False


def _http_error_detail(exc: httpx.HTTPStatusError) -> str:
    detail = str(exc)
    if exc.response is not None:
        try:
            body = exc.response.json()
            if isinstance(body, dict) and body.get("detail"):
                detail = str(body["detail"])
        except Exception:
            pass
    return detail


async def _ensure_wallet_balance(client: CoreAPIClient, amount: int) -> None:
    if amount <= 0:
        return
    wallet = await client.get_wallet()
    balance = int(wallet.get("balance") or 0)
    if balance < amount:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits. Balance: {balance}, Required: {amount}",
        )


async def _deduct_credits(client: CoreAPIClient, amount: int, metadata: dict) -> dict:
    if amount <= 0:
        return {}
    try:
        return await client.deduct_credits(amount, metadata)
    except httpx.HTTPStatusError as exc:
        detail = _http_error_detail(exc)
        if exc.response is not None and exc.response.status_code == 402:
            raise HTTPException(status_code=402, detail=detail) from exc
        raise HTTPException(status_code=502, detail=f"credit deduction failed: {detail}") from exc


async def _refund_credits(client: CoreAPIClient, amount: int, metadata: dict) -> None:
    if amount <= 0:
        return
    try:
        await client.refund_credits(amount, metadata)
    except Exception as exc:
        print(f"[brand_studio] credit refund failed ({amount} cr): {exc}")


@router.get("/health")
async def health(user: dict = Depends(get_current_user)):
    return {
        "ok": True,
        "falKey": bool(brand_studio._fal_key()),
        "openRouterKey": bool(brand_studio._openrouter_key()),
        "ideasModel": brand_studio._ideas_model(),
        "engine": "GPT Image 2 (Fal)",
        "billingEnabled": True,
    }


@router.get("/credits")
async def brand_credit_costs(user: dict = Depends(get_current_user)):
    """Brand Studio credit rates for UI estimates."""
    _ = user
    return {
        "ideasPerIdea": 2,
        "ideasMin": 6,
        "slideRender": get_brand_studio_slide_credit_cost(),
    }


@router.get("/brand")
async def get_brand(user: dict = Depends(get_current_user)):
    return {"brand": brand_studio.read_brand_state(user["id"])}


@router.get("/session")
async def get_session(user: dict = Depends(get_current_user)):
    return {"session": brand_studio.read_studio_session(user["id"])}


@router.post("/session")
async def save_session(req: SessionSaveRequest, user: dict = Depends(get_current_user)):
    brand_studio.write_studio_session(user["id"], req.session or {})
    return {"ok": True}


@router.get("/renders/{rel_path:path}")
async def get_render(rel_path: str, user: dict = Depends(get_current_user)):
    full = brand_studio.render_file_path(user["id"], rel_path)
    if not full:
        raise HTTPException(status_code=404, detail="render not found")
    return FileResponse(full, media_type="image/png")


@router.post("/scrape")
async def scrape(req: ScrapeRequest, user: dict = Depends(get_current_user)):
    url = (req.url or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="no url")
    try:
        brand = await asyncio.to_thread(brand_studio.scrape_brand, url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"scrape failed: {e}") from e
    brand_studio.write_brand_state(user["id"], brand)
    return {"brand": brand}


@router.post("/save")
async def save(req: SaveRequest, user: dict = Depends(get_current_user)):
    brand_studio.write_brand_state(user["id"], req.brand or {})
    return {"ok": True}


@router.get("/stored-renders")
async def stored_renders(brand: str = "", user: dict = Depends(get_current_user)):
    name = (brand or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="brand name required")
    renders = await asyncio.to_thread(brand_studio.list_stored_renders, user["id"], name)
    return {"renders": renders, "brand": name}


@router.post("/generate")
async def generate(req: GenerateRequest, user: dict = Depends(get_current_user)):
    client = CoreAPIClient(token=user["token"], skip_project_scope=True)
    slide_credits = get_brand_studio_slide_credit_cost()
    await _ensure_wallet_balance(client, slide_credits)

    refs = [u for u in (req.imageUrls or []) if u][:3]
    mode = "edit" if refs else "text"
    charge_meta = {
        "operation": "brand_studio_slide_render",
        "brand": req.brand,
        "post_id": req.postId,
        "slide": req.slide,
        "role": req.role,
        "mode": mode,
        "refs": len(refs),
    }

    try:
        result = await asyncio.to_thread(
            brand_studio.generate_images, req.prompt, req.imageUrls, req.n
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    images = result.get("images") or []
    if not images:
        raise HTTPException(status_code=502, detail="no images returned")

    wallet = await _deduct_credits(client, slide_credits, charge_meta)
    result["creditsCharged"] = slide_credits
    if wallet.get("balance") is not None:
        result["balance"] = wallet["balance"]
    print(
        f"[brand_studio] charged {slide_credits} credits for slide render "
        f"(brand={req.brand!r} post={req.postId} slide={req.slide}), "
        f"balance={wallet.get('balance')}"
    )

    if req.brand and req.postId:
        try:
            stored = await asyncio.to_thread(
                brand_studio.store_image,
                images[0],
                brand=req.brand,
                post_id=req.postId,
                slide=req.slide or "1",
                role=req.role,
                user_id=user["id"],
            )
            if stored.get("url"):
                result["images"] = [stored["url"]]
            if stored.get("path"):
                result["savedPath"] = stored["path"]
            result["persisted"] = True
        except Exception as exc:
            print(f"[brand_studio] auto-persist after generate failed: {exc}")
            result["persistWarning"] = str(exc)

    return result


@router.post("/pick-logo")
async def pick_logo(req: PickLogoRequest, user: dict = Depends(get_current_user)):
    _ = user
    picked = brand_studio.select_logo(
        req.logos or [],
        role_tag=req.role,
        layout=req.layout,
        palette=req.colors,
        slide_index=req.slideIndex,
        has_product_ref=req.hasProductRef,
    )
    return picked or {}


@router.post("/ideas")
async def ideas(req: IdeasRequest, user: dict = Depends(get_current_user)):
    client = CoreAPIClient(token=user["token"], skip_project_scope=True)
    idea_count = max(1, min(8, int(req.count or 3)))
    credits = get_brand_studio_ideas_credit_cost(idea_count)
    charge_meta = {
        "operation": "brand_studio_ideas",
        "idea_count": idea_count,
        "brand": (req.brand or {}).get("name", ""),
    }

    await _ensure_wallet_balance(client, credits)
    wallet = await _deduct_credits(client, credits, charge_meta)

    try:
        result = await asyncio.to_thread(
            brand_studio.generate_ideas,
            req.brand,
            req.direction,
            idea_count,
            lang=req.lang,
        )
    except RuntimeError as e:
        await _refund_credits(client, credits, {**charge_meta, "reason": "ideas_generation_failed"})
        raise HTTPException(status_code=502, detail=str(e)) from e

    result["creditsCharged"] = credits
    if wallet.get("balance") is not None:
        result["balance"] = wallet["balance"]
    print(
        f"[brand_studio] charged {credits} credits for ideas batch "
        f"(count={idea_count} brand={charge_meta.get('brand')!r}), "
        f"balance={wallet.get('balance')}"
    )
    return result


@router.post("/store-image")
async def store_image(req: StoreImageRequest, user: dict = Depends(get_current_user)):
    try:
        return await asyncio.to_thread(
            brand_studio.store_image,
            req.url,
            brand=req.brand,
            post_id=req.postId,
            slide=req.slide,
            role=req.role,
            user_id=user["id"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"download failed: {e}") from e
