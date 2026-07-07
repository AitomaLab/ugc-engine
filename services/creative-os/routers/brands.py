"""Brand Studio API — scrape, ideas, Fal render."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from auth import get_current_user
from services import brand_studio

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


@router.get("/health")
async def health(user: dict = Depends(get_current_user)):
    return {
        "ok": True,
        "falKey": bool(brand_studio._fal_key()),
        "openRouterKey": bool(brand_studio._openrouter_key()),
        "ideasModel": brand_studio._ideas_model(),
        "engine": "GPT Image 2 (Fal)",
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
    try:
        result = await asyncio.to_thread(
            brand_studio.generate_images, req.prompt, req.imageUrls, req.n
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    images = result.get("images") or []
    if images and req.brand and req.postId:
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
    try:
        return brand_studio.generate_ideas(req.brand, req.direction, req.count, lang=req.lang)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


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
