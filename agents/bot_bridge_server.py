import asyncio
import os
import time
import uuid
from typing import Any

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from aztm_bootstrap import login_aztm_from_env
from flow_log import (
    flow_log,
    install_aztm_print_filter,
    outbound_transport_for_url,
    request_sender,
    request_transport,
    service_from_url,
)

load_dotenv()

app = FastAPI()

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8000/chat")
ORCHESTRATOR_TIMEOUT_SEC = float(os.getenv("ORCHESTRATOR_TIMEOUT_SEC", "120"))
RESULT_TTL_SEC = int(os.getenv("BRIDGE_RESULT_TTL_SEC", "900"))


class ChatRequest(BaseModel):
    text: str
    sender: str


# request_id -> job state
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = asyncio.Lock()


# Keep AZTM hook debug noise out of runtime logs.
install_aztm_print_filter()

# Initialize AZTM after FastAPI app is created so auto-hook can detect the app.
login_aztm_from_env(server_mode=False)


def _short(text: str, max_len: int = 180) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _now() -> float:
    return time.time()


async def _cleanup_jobs() -> None:
    cutoff = _now() - RESULT_TTL_SEC
    async with JOBS_LOCK:
        stale_ids = [request_id for request_id, job in JOBS.items() if job["updated_at"] < cutoff]
        for request_id in stale_ids:
            JOBS.pop(request_id, None)


async def _update_job(request_id: str, **fields: Any) -> None:
    async with JOBS_LOCK:
        job = JOBS.get(request_id)
        if job is None:
            return
        job.update(fields)
        job["updated_at"] = _now()


async def _process_job(request_id: str, payload: dict) -> None:
    await _update_job(request_id, status="processing")

    destination = service_from_url(ORCHESTRATOR_URL)
    transport = outbound_transport_for_url(ORCHESTRATOR_URL)
    flow_log(
        sender="bot_bridge",
        destination=destination,
        transport=transport,
        path="/chat",
        phase="dispatch",
        request_id=request_id,
    )

    try:
        data = await asyncio.to_thread(
            _post_json,
            ORCHESTRATOR_URL,
            payload,
            ORCHESTRATOR_TIMEOUT_SEC,
        )

        reply = str(data.get("reply", "")).strip()
        await _update_job(request_id, status="done", reply=reply)
        flow_log(
            sender=destination,
            destination="bot_bridge",
            transport=transport,
            path="/chat",
            phase="response",
            request_id=request_id,
            status="done",
            extra=f"reply='{_short(reply)}'",
        )
    except requests.RequestException as exc:
        error_text = f"Orchestrator call failed: {exc}"
        await _update_job(request_id, status="error", error=error_text)
        flow_log(
            sender=destination,
            destination="bot_bridge",
            transport=transport,
            path="/chat",
            phase="response",
            request_id=request_id,
            status="error",
            extra=f"error='{_short(error_text)}'",
        )
    except Exception as exc:  # noqa: BLE001
        error_text = f"Unexpected bridge error: {exc}"
        await _update_job(request_id, status="error", error=error_text)
        flow_log(
            sender=destination,
            destination="bot_bridge",
            transport=transport,
            path="/chat",
            phase="response",
            request_id=request_id,
            status="error",
            extra=f"error='{_short(error_text)}'",
        )


@app.post("/chat")
async def enqueue_chat(request: ChatRequest, http_request: Request):
    await _cleanup_jobs()

    request_id = str(uuid.uuid4())
    payload = request.model_dump()

    inbound_sender = request_sender(http_request, request.sender)
    inbound_transport = request_transport(http_request)
    flow_log(
        sender=inbound_sender,
        destination="bot_bridge",
        transport=inbound_transport,
        path="/chat",
        phase="inbound",
        request_id=request_id,
    )

    async with JOBS_LOCK:
        JOBS[request_id] = {
            "status": "queued",
            "sender": request.sender,
            "text": request.text,
            "reply": None,
            "error": None,
            "created_at": _now(),
            "updated_at": _now(),
        }

    asyncio.create_task(_process_job(request_id, payload))

    flow_log(
        sender="bot_bridge",
        destination=inbound_sender,
        transport=inbound_transport,
        path="/chat",
        phase="queued",
        request_id=request_id,
        status="queued",
    )
    return {
        "request_id": request_id,
        "status": "queued",
    }


@app.get("/chat/result/{request_id}")
async def get_chat_result(request_id: str):
    await _cleanup_jobs()

    async with JOBS_LOCK:
        job = JOBS.get(request_id)

    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown request_id: {request_id}")

    status = job["status"]
    if status == "done":
        return {
            "request_id": request_id,
            "status": "done",
            "reply": job.get("reply") or "",
        }

    if status == "error":
        return {
            "request_id": request_id,
            "status": "error",
            "error": job.get("error") or "Unknown error",
        }

    return {
        "request_id": request_id,
        "status": status,
    }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
