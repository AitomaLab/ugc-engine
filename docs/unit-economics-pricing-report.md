# UGC Engine Unit Economics & Pricing Strategy Report

**Date:** June 2026  
**Target gross margin:** 70%  
**Primary retail anchor (Model A):** $0.03/credit  
**Alternate anchor (Model B):** $0.01/credit  

> **Full authoritative report:** [`unit-economics-full-report.md`](unit-economics-full-report.md) (~60-row task matrix, workflow line-items, LLM model, margin proofs, billing audit, Layer 3 infra). CSV: [`unit-economics-task-matrix.csv`](unit-economics-task-matrix.csv).

---

## Executive Summary

The codebase separates **internal COGS** (`ugc_backend/cost_config.json`) from **user-facing credits** (`ugc_backend/credit_cost_service.py`). At **$0.03/credit**, standard UGC video jobs on the **Veo 3.1 Fast** path are profitable, but **Cinematic Ads, Gemini Omni edits, Kling animation clips, and Seedance-heavy paths were materially underpriced** — some at **-50% to -63% gross margin**.

The legacy "~21 credits per $1 COGS" comment is a heuristic, not a 70% margin guarantee. At $0.03/credit, 21 credits = $0.63 revenue per $1 COGS → negative margin.

**Implemented recommendation:** Model A ($0.03/credit) for minimal UX disruption, with Model B documented for finance reporting.

---

## 1. Pricing Architecture

| Layer | Source of truth | Notes |
|-------|----------------|-------|
| COGS (USD) | `ugc_backend/cost_config.json` | WaveSpeed, Fal, ElevenLabs |
| Credit deductions | `ugc_backend/credit_cost_service.py` | Mirrored in `services/creative-os/services/credit_costs.py` |
| Subscription $ | Supabase `subscription_plans` | Fetched by `frontend/src/app/upgrade/page.tsx` |
| Top-up $ | `frontend/src/app/manage/page.tsx` | $9 / $24 / $59 / $139 |
| Credit enforcement | `POST /jobs`, `POST /api/credits/deduct` | Agent-gated ops deduct via Creative OS |

---

## 2. Margin Formula

$$\text{Required Revenue} = \frac{\text{COGS}}{0.30}$$

$$\text{Credits} = \left\lceil \frac{\text{COGS}}{0.30 \times \text{RPC}} \right\rceil$$

| Anchor | RPC | Divisor | Example: $0.30 Veo flat |
|--------|-----|---------|-------------------------|
| **Model A** | $0.03 | ÷ 0.009 | **34 credits** |
| **Model B** | $0.01 | ÷ 0.003 | **100 credits** |

---

## 3. True COGS — Workflow Breakdowns

### Production defaults vs stated assumptions

| Stated assumption | Production path |
|-------------------|-----------------|
| Digital 15s = Seedance 2.0 | Default `model_api=veo-3.1-fast` |
| Physical = 2× Nano Banana | `parallel_i2v`: **1** Nano + **2×** Veo |
| ElevenLabs on all UGC | Not used on Veo/Seedance (native audio) |
| Claude 3.5 Sonnet | Runtime: `claude-sonnet-4-6` |

### Workflow A: 15s Digital UGC

**Specified (Seedance + ElevenLabs):** Agent $0.10 + Script $0.015 + Nano $0.09 + Seedance 8s $1.00 + ElevenLabs $0.023 + Music/Processing $0.06 = **$1.29**

**Production (Veo, no ElevenLabs):** Agent/Script $0.115 + Nano $0.09 + Veo flat $0.30 + Music/Processing $0.06 = **$0.57**

### Workflow B: 15s Physical UGC

**Specified (2× Nano + 2× Veo + ElevenLabs):** **$1.00**

**Production (1 Nano + 2× Veo):** **$0.87**

**Seedance physical (4s t2v + 12s i2v):** **$2.59**

### Workflow C: 15s Cinematic Ad (storyboard + 15s hero)

**Minimal:** Agent ~$0.20 + Storyboard $0.18 + Seedance Pro 15s $4.50 = **~$4.88**

---

## 4. Current Margin Analysis (@ $0.03/credit, pre-fix)

| Workflow | Old credits | Revenue | COGS | Margin |
|----------|--------------|---------|------|--------|
| Digital 15s (Veo) | 95 | $2.85 | $0.57 | 80% |
| Digital 15s (Seedance) | 95 | $2.85 | $1.29 | 55% |
| Physical 15s (Veo) | 100 | $3.00 | $0.87 | 71% |
| Physical 15s (Seedance) | 100 | $3.00 | $2.59 | 14% |
| Cinematic 15s | 100 | $3.00 | $4.90 | **-63%** |

### Tasks that were losing money

| Task | Old credits | COGS | Margin |
|------|------------|------|--------|
| `cinematic_storyboard` | 4 | $0.18 | -50% |
| `cinematic_animate_720p_15s` | 96 | $4.50 | -56% |
| `gemini_omni_edit_720p` | 25 | $1.20 | -60% |
| `animate_image_5s` | 25 | $0.50 | 33% |

---

## 5. Proposed Credit Model (70% margin)

### Atomic unit rates

| Cost unit | COGS | Model A | Model B |
|-----------|------|---------|---------|
| Processing / video | $0.01 | 2 | 4 |
| Music / video | $0.05 | 6 | 17 |
| ElevenLabs / 1k chars | $0.18 | 20 | 60 |
| Nano Banana 1k/2k | $0.09 | 10 | 30 |
| Nano Banana 4k | $0.12 | 14 | 40 |
| Veo 3.1 Fast 720p (flat) | $0.30 | 34 | 100 |
| Seedance 720p i2v / sec | $0.125 | 14 | 42 |
| Seedance 720p t2v / sec | $0.205 | 23 | 68 |
| Kling 3 std w/ audio / sec | $0.10 | 12 | 34 |
| InfiniTalk / sec | $0.022 | 3 | 8 |
| Fal GPT Image 2 storyboard | $0.18 | 20 | 60 |
| Fal Seedance Pro 720p / sec | $0.30 | 34 | 100 |
| Gemini Omni edit 720p | $1.20 | 134 | 400 |
| Gemini Omni edit 4k | $1.80 | 200 | 600 |

### Composite workflow targets

| Workflow | COGS | Model A | Model B | Old |
|----------|------|---------|---------|-----|
| Digital 15s (Veo) | $0.57 | **67** | 200 | 95 |
| Digital 15s (Seedance) | $1.29 | **145** | 430 | 95 |
| Physical 15s (Veo) | $0.87 | **101** | 300 | 100 |
| Physical 15s (Seedance) | $2.59 | **288** | 864 | 100 |
| Cinematic 15s | $4.90 | **544** | 1,634 | 100 |
| Clone 15s | $0.47 | **53** | 157 | 90 |
| Animate image 5s | $0.50 | **56** | 167 | 25 |

---

## 6. Subscription & Top-up Restructuring (Model A)

### Top-ups (same dollar prices)

| Package | Price | Credits | ¢/credit | ~Digital 15s videos |
|---------|-------|---------|----------|---------------------|
| Small | $9 | 300 | 3.0¢ | ~4 |
| Medium | $24 | 900 | 2.67¢ | ~13 |
| Large | $59 | 2,400 | 2.46¢ | ~35 |
| XL | $139 | 6,000 | 2.32¢ | ~89 |

### Subscriptions

| Plan | Price/mo* | Credits/mo | Digital 15s* | Cinematic 15s* |
|------|-----------|------------|--------------|----------------|
| Starter | DB/Stripe | 1,000 | ~15 | ~1 |
| Creator | DB/Stripe | 3,200 | ~47 | ~5 |
| Business | DB/Stripe | 7,000 | ~104 | ~12 |

*Confirm live Stripe prices in Supabase. Migration `061_update_pricing_credits.sql` updates credit allotments.

### Model B top-ups (same dollars)

| Package | Credits |
|---------|---------|
| Small | 900 |
| Medium | 2,700 |
| Large | 7,200 |
| XL | 18,000 |

---

## 7. Implementation Notes (June 2026 — shipped)

- `resolve_job_credit_cost()` handles full UGC (15/30) and clip jobs (5–15) by `model_api`.
- `POST /jobs` and `POST /jobs/bulk` deduct credits; failures refund; `metadata.credits_deducted` persisted.
- `POST /api/credits/deduct` for Creative OS agent tools on `confirmed=true`.
- 4-view identity/product sheets: **40 credits**; alt versions: **20 credits** (charged).
- Legacy `/api/products/.../shots` and `/api/shots/{id}/animate` require auth + deduct.
- Frontend: `GET /api/credits/costs` via [`frontend/src/lib/credit-costs.ts`](frontend/src/lib/credit-costs.ts).
- Subscription/top-up: migration [`ugc_db/migrations/062_pricing_tiers.sql`](ugc_db/migrations/062_pricing_tiers.sql) — run + update Stripe Price IDs.

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| Cinematic repricing shock | Grandfather balances; communicate before deploy |
| Seedance underpricing | Premium bundle keys for Seedance `model_api` |
| Subscription $ not in repo | Run migration + verify Stripe |

**Recommendation:** Ship Model A ($0.03). Use Model B internally if 1 credit = 1¢ reporting is preferred.
