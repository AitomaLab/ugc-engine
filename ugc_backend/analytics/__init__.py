"""UGC Engine — Analytics Module.

Self-contained module that adds a second tab to the Publish page:
post performance scraping (BrightData) + per-video AI breakdowns (Gemini via
KIE / FAL / direct routing).

Public surface:
    from ugc_backend.analytics.router import router as analytics_router

The router is mounted in ugc_backend/main.py near the other include_router
calls. Everything else lives inside this package so partner branches can be
developed and reviewed in isolation.
"""
