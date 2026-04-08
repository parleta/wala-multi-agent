import asyncio
import os

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from aztm_bootstrap import login_aztm_from_env

load_dotenv()

app = FastAPI()

ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://orchestrator:8000/chat")


class ChatRequest(BaseModel):
    text: str
    sender: str


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


@app.post("/chat")
async def chat_proxy(request: ChatRequest):
    print(
        f"[BRIDGE] <- bot sender={request.sender} text='{_short(request.text)}'",
        flush=True,
    )
    payload = request.model_dump()

    try:
        print(f"[BRIDGE] -> orchestrator url={ORCHESTRATOR_URL}", flush=True)
        data = await asyncio.to_thread(_post_json, ORCHESTRATOR_URL, payload, 120.0)
        print(
            f"[BRIDGE] <- orchestrator reply='{_short(str(data.get('reply', '')))}'",
            flush=True,
        )
        print("[BRIDGE] -> bot reply forwarded", flush=True)
        return data
    except requests.RequestException as exc:
        print(f"[BRIDGE] orchestrator call failed: {exc}", flush=True)
        raise HTTPException(status_code=502, detail=f"Orchestrator call failed: {exc}") from exc


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
