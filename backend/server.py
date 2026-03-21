"""
server.py — FastAPI server exposing control endpoints.

Endpoints:
  POST /call/start   — trigger a single lead call immediately
  POST /call/dtmf    — send DTMF tones to active call
  POST /batch/start  — start batch calling loop
  POST /batch/stop   — gracefully stop batch
  GET  /status       — health + current state
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import settings
from backend.lead_fetcher import fetch_next_lead
from backend.orchestrator import run_batch
from backend.session_store import SessionStore

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hindi Calling Agent",
    description="Autonomous Hindi voice calling agent for website sales",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared state
_batch_task: Optional[asyncio.Task] = None
_session_store: Optional[SessionStore] = None


from backend.call_controller import init_gateway_server

@app.on_event("startup")
async def startup() -> None:
    global _session_store
    _session_store = SessionStore()
    await _session_store.initialize()
    
    # Start WebSocket server
    await init_gateway_server(host="0.0.0.0", port=8765)
    logger.info("Server started — session store ready, WebSocket gateway listening on 8765.")


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class StartCallRequest(BaseModel):
    phone: Optional[str] = None   # if None, fetches next uncalled lead


class DtmfRequest(BaseModel):
    digits: str


class BatchStartRequest(BaseModel):
    max_calls: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/status")
async def status():
    return {
        "status": "ok",
        "batch_running": _batch_task is not None and not _batch_task.done(),
        "recording_enabled": settings.recording_enabled,
        "android_gateway": settings.android_gateway_ws_url,
    }


@app.post("/call/start")
async def call_start(req: StartCallRequest):
    global _session_store
    
    if req.phone:
        from backend.models import Lead
        lead = Lead(
            id="manual",
            company_name="Manual",
            owner_name="Unknown",
            phone=req.phone,
            city="Unknown"
        )
    else:
        lead = fetch_next_lead()
        if not lead:
            raise HTTPException(status_code=404, detail="No uncalled leads available.")

    from backend.orchestrator import _run_single_call
    asyncio.create_task(_run_single_call(lead, _session_store))
    return {"message": "Call initiated", "phone": lead.phone}


@app.post("/batch/start")
async def batch_start(req: BatchStartRequest):
    global _batch_task
    if _batch_task and not _batch_task.done():
        raise HTTPException(status_code=409, detail="Batch already running.")
    _batch_task = asyncio.create_task(run_batch(max_calls=req.max_calls))
    return {"message": "Batch started", "max_calls": req.max_calls}


@app.post("/batch/stop")
async def batch_stop():
    global _batch_task
    if _batch_task and not _batch_task.done():
        _batch_task.cancel()
        return {"message": "Batch stop requested."}
    return {"message": "No batch is currently running."}


@app.get("/leads/next")
async def leads_next():
    """Preview the next uncalled lead (does not start a call)."""
    lead = fetch_next_lead()
    if lead is None:
        return {"lead": None, "message": "No uncalled leads."}
    return {
        "lead": {
            "id": lead.id,
            "company_name": lead.company_name,
            "owner_name": lead.owner_name,
            "phone": lead.phone,
            "city": lead.city,
        }
    }
