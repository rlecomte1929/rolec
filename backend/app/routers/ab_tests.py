"""
ab_tests.py — PRODUCT-6F
──────────────────────────────────────────────────────────────────────────────
A/B test management endpoints.

  POST /api/ab-tests/promote  — Promote a winning variant to 100% traffic
  POST /api/ab-tests/rollback — Reset a flag to 100% control

Both endpoints PATCH the Vercel Edge Config store to update traffic_split,
then write an event to the public.events table for audit / downstream analysis.

Environment variables required:
  VERCEL_API_TOKEN        — Vercel personal access token (with Edge Config write scope)
  VERCEL_EDGE_CONFIG_ID   — e.g. ecfg_mzuckpdlwwqizdoscycqre6qxrkb
  SUPABASE_URL            — Supabase project URL
  SUPABASE_SERVICE_ROLE_KEY — Service role key (for writing audit events)

The Vite proxy forwards /api/ → FastAPI, so these routes are reachable from
the browser as /api/ab-tests/promote and /api/ab-tests/rollback.
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/ab-tests", tags=["ab-tests"])
logger = logging.getLogger(__name__)

# ─── Vercel Edge Config constants ────────────────────────────────────────────

VERCEL_API_BASE = "https://api.vercel.com/v1/edge-config"

def _edge_config_id() -> str:
    cid = os.getenv("VERCEL_EDGE_CONFIG_ID", "ecfg_mzuckpdlwwqizdoscycqre6qxrkb")
    return cid

def _vercel_token() -> str:
    token = os.getenv("VERCEL_API_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="VERCEL_API_TOKEN not configured")
    return token


# ─── Schemas ─────────────────────────────────────────────────────────────────

class PromoteRequest(BaseModel):
    flag_name: str
    variant: str  # the variant to promote to 100%


class RollbackRequest(BaseModel):
    flag_name: str


# ─── Helpers ─────────────────────────────────────────────────────────────────

async def _get_flags() -> dict:
    """Fetch current flags object from Edge Config."""
    token = _vercel_token()
    edge_config_id = _edge_config_id()
    url = f"{VERCEL_API_BASE}/{edge_config_id}/item/flags"
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(url, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code == 404:
        return {}
    if not resp.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"Edge Config read failed ({resp.status_code}): {resp.text}",
        )
    return resp.json() or {}


async def _patch_flags(flags: dict) -> None:
    """Write the full flags object back to Edge Config via PATCH items API."""
    token = _vercel_token()
    edge_config_id = _edge_config_id()
    url = f"{VERCEL_API_BASE}/{edge_config_id}/items"
    payload = {"items": [{"operation": "upsert", "key": "flags", "value": flags}]}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.patch(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            content=json.dumps(payload),
        )
    if not resp.is_success:
        raise HTTPException(
            status_code=502,
            detail=f"Edge Config write failed ({resp.status_code}): {resp.text}",
        )


async def _write_audit_event(event_type: str, properties: dict) -> None:
    """Fire-and-forget: write an audit event to Supabase events table."""
    supabase_url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not service_key:
        logger.warning("Supabase env vars not set — skipping audit event write")
        return
    url = f"{supabase_url}/rest/v1/events"
    payload = {
        "event_type": event_type,
        "properties": properties,
        "source": "admin_api",
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                url,
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=minimal",
                },
                content=json.dumps(payload),
            )
    except Exception as exc:
        logger.warning("Failed to write audit event: %s", exc)


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/promote")
async def promote_variant(body: PromoteRequest):
    """
    Promote a variant to 100% traffic.

    Sets traffic_split to [0, 100] for control/variant_a (or the named variant).
    The flag stays `enabled: true` so analytics keep flowing.
    """
    flags = await _get_flags()

    flag = flags.get(body.flag_name)
    if flag is None:
        raise HTTPException(status_code=404, detail=f"Flag '{body.flag_name}' not found in Edge Config")

    variants: list[str] = flag.get("variants", [])
    if body.variant not in variants:
        raise HTTPException(
            status_code=400,
            detail=f"Variant '{body.variant}' not in flag variants {variants}",
        )

    # Build new traffic_split: 0% to everything except the winning variant
    new_split = [0] * len(variants)
    winner_idx = variants.index(body.variant)
    new_split[winner_idx] = 100

    old_split = flag.get("traffic_split", [])
    flags[body.flag_name]["traffic_split"] = new_split

    await _patch_flags(flags)

    logger.info(
        "Promoted %s/%s: traffic_split %s → %s",
        body.flag_name, body.variant, old_split, new_split,
    )

    await _write_audit_event(
        "ab_test_promoted",
        {
            "flag_name": body.flag_name,
            "variant": body.variant,
            "old_traffic_split": old_split,
            "new_traffic_split": new_split,
        },
    )

    return {
        "ok": True,
        "flag_name": body.flag_name,
        "variant": body.variant,
        "new_traffic_split": new_split,
    }


@router.post("/rollback")
async def rollback_flag(body: RollbackRequest):
    """
    Rollback a flag to 100% control.

    Sets traffic_split to [100, 0, ...] so all users get 'control'.
    Keeps the flag enabled so it can be re-tested later.
    """
    flags = await _get_flags()

    flag = flags.get(body.flag_name)
    if flag is None:
        raise HTTPException(status_code=404, detail=f"Flag '{body.flag_name}' not found in Edge Config")

    variants: list[str] = flag.get("variants", [])
    old_split = flag.get("traffic_split", [])

    # control is always the first variant by convention
    new_split = [0] * len(variants)
    if variants:
        new_split[0] = 100  # 100% to 'control'

    flags[body.flag_name]["traffic_split"] = new_split

    await _patch_flags(flags)

    logger.info(
        "Rolled back %s: traffic_split %s → %s",
        body.flag_name, old_split, new_split,
    )

    await _write_audit_event(
        "ab_test_rolled_back",
        {
            "flag_name": body.flag_name,
            "old_traffic_split": old_split,
            "new_traffic_split": new_split,
        },
    )

    return {
        "ok": True,
        "flag_name": body.flag_name,
        "new_traffic_split": new_split,
        "message": "Flag reset to 100% control.",
    }
