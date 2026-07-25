"""Live log viewer endpoints — the admin UI's /admin/logs tail.

GET /logs/recent gives an initial snapshot; GET /logs/stream is a
Server-Sent-Events poll over the same ring buffer (app/core/logging.py) so a
browser's native EventSource can tail it with automatic reconnect, no
WebSocket connection management needed for a one-way log feed.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.logging import get_recent_logs

router = APIRouter(prefix="/logs", tags=["logs"])

_POLL_INTERVAL_SECONDS = 0.3
_BUFFER_SNAPSHOT_LIMIT = 200


@router.get("/recent")
def recent_logs(limit: int = 200, since: int = 0):
    return get_recent_logs(limit=limit, since=since)


@router.get("/stream")
async def stream_logs(request: Request, since: int = 0):
    async def event_generator():
        last_seen = since
        while True:
            if await request.is_disconnected():
                break
            entries = get_recent_logs(limit=_BUFFER_SNAPSHOT_LIMIT, since=last_seen)
            for entry in entries:
                last_seen = max(last_seen, entry["seq"])
                yield f"data: {json.dumps(entry)}\n\n"
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
