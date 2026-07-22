"""brand_research record store (Slice 2) — the data-integrity contract in code.

Observations = scraped facts, provenance mandatory (DB CHECK backs this up).
Interpretations = model claims, require >= MIN_SUPPORT observation refs —
the DB floors at 1, the real threshold lives here and is tested.

Numbers policy (contract rule 2): free-text payload fields written through
`insert_interpretation` are containment-checked — any digit sequence in the
text must literally appear in at least one supporting observation's text,
otherwise the write is refused. Metrics always live in typed payload keys
copied from scrapes, never inside prose.
"""
from __future__ import annotations

import os
import re
import unicodedata
from datetime import datetime, timezone

# Support floors per claim shape: a PATTERN claim (persona, "X works here")
# needs multiple observations behind it; a DIRECT-ECHO justification ("this
# hook quotes audience question Q") is fully supported by the single
# observation it quotes. Callers pass the right floor; default is the strict
# one.
MIN_SUPPORT = 3
MIN_SUPPORT_DIRECT = 1

_DIGITS_RE = re.compile(r"\d[\d.,%]*")


def _sb():
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        raise RuntimeError("missing SUPABASE_URL or service key")
    return create_client(url, key)


def canonical_subject(text: str) -> str:
    """Normalized overlap key: lowercase, accents stripped, punctuation
    collapsed. Exact-match on this is what 'near-identical' means."""
    t = unicodedata.normalize("NFKD", text or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9 ]+", " ", t.lower())
    return re.sub(r"\s+", " ", t).strip()[:120]


def digits_contained(text: str, sources: list[str]) -> bool:
    """Every digit-run in `text` must appear verbatim in some source text."""
    hay = "\n".join(sources)
    for m in _DIGITS_RE.finditer(text or ""):
        if m.group(0).rstrip(".,") not in hay:
            return False
    return True


def insert_observations(user_id: str, rows: list[dict]) -> list[str]:
    """Bulk-insert observation rows; returns their ids. Each row must carry
    insight_type, subject_text, payload, source, source_url; scraped_at and
    canonicalization are applied here."""
    if not rows:
        return []
    now = datetime.now(timezone.utc).isoformat()
    payload = []
    for r in rows:
        if not r.get("source_url"):
            raise ValueError(f"observation without source_url: {r.get('subject_text')!r}")
        payload.append(
            {
                "user_id": user_id,
                "kind": "observation",
                "insight_type": r["insight_type"],
                "subject": canonical_subject(r["subject_text"]),
                "language": r.get("language"),
                "industry": r.get("industry"),
                "source": r.get("source"),
                "source_url": r["source_url"],
                "scraped_at": r.get("scraped_at") or now,
                "dataset_id": r.get("dataset_id"),
                "payload": r.get("payload") or {},
            }
        )
    resp = _sb().table("brand_research").insert(payload).execute()
    return [row["id"] for row in (resp.data or [])]


def insert_interpretation(
    user_id: str,
    *,
    insight_type: str,
    subject_text: str,
    payload: dict,
    refs: list[str],
    supporting_texts: list[str],
    language: str | None = None,
    industry: str | None = None,
    source: str = "model",
    min_support: int = MIN_SUPPORT,
) -> str | None:
    """Insert a model claim. Refused (returns None) when under-supported or
    when its free text contains numbers absent from the supporting sources."""
    if len(refs) < max(1, min_support):
        return None
    free_text = " ".join(
        str(v) for v in payload.values() if isinstance(v, str)
    ) + " " + " ".join(
        x for v in payload.values() if isinstance(v, list) for x in v if isinstance(x, str)
    )
    if not digits_contained(free_text, supporting_texts):
        return None
    resp = (
        _sb()
        .table("brand_research")
        .insert(
            {
                "user_id": user_id,
                "kind": "interpretation",
                "insight_type": insight_type,
                "subject": canonical_subject(subject_text),
                "language": language,
                "industry": industry,
                "source": source,
                "payload": payload,
                "refs": refs,
            }
        )
        .execute()
    )
    rows = resp.data or []
    return rows[0]["id"] if rows else None


def list_records(
    user_id: str,
    *,
    insight_type: str | None = None,
    kind: str | None = None,
    limit: int = 200,
) -> list[dict]:
    q = _sb().table("brand_research").select("*").eq("user_id", user_id)
    if insight_type:
        q = q.eq("insight_type", insight_type)
    if kind:
        q = q.eq("kind", kind)
    return (q.order("created_at", desc=True).limit(limit).execute()).data or []


def delete_records(user_id: str, *, insight_type: str, source: str | None = None) -> None:
    """Replace-on-refresh semantics for a research pass."""
    q = _sb().table("brand_research").delete().eq("user_id", user_id).eq("insight_type", insight_type)
    if source:
        q = q.eq("source", source)
    q.execute()
