import asyncio
import os
from typing import Literal

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from aztm_bootstrap import login_aztm_from_env
from flow_log import (
    flow_log,
    install_aztm_print_filter,
    outbound_transport_for_url,
    request_correlation_id,
    request_sender,
    request_transport,
    service_from_url,
)
from message_protocol import WireMessage, last_ai_text, wire_to_lc

load_dotenv()

app = FastAPI()

# Keep AZTM hook debug noise out of runtime logs.
install_aztm_print_filter()

# Initialize AZTM after FastAPI app is created so auto-hook can detect the app.
login_aztm_from_env(server_mode=False)

BASE_DIR = os.path.dirname(__file__)
with open(os.path.join(BASE_DIR, "prompts", "supervisor.md"), "r", encoding="utf-8") as f:
    SUPERVISOR_PROMPT = f.read()

DIRECT_REPLY_PROMPT = (
    "You are the WALA supervisor agent. "
    "Answer the latest user message directly when no specialist transfer is needed. "
    "Always answer the latest user message and never repeat stale previous answers. "
    "Be concise, helpful, and context-aware."
)

CALENDAR_AGENT_URL = os.getenv("CALENDAR_AGENT_URL", "http://calendar_agent:8000/run")
MAPS_AGENT_URL = os.getenv("MAPS_AGENT_URL", "http://maps_agent:8000/run")


class ChatRequest(BaseModel):
    text: str
    sender: str


class Router(BaseModel):
    next_agent: Literal["calendar_agent", "maps_agent", "FINISH"] = Field(
        description="Transfer or FINISH."
    )


sessions: dict[str, list[WireMessage]] = {}


def _short(text: str, max_len: int = 180) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _last_role_text(messages: list[WireMessage], role: str) -> str:
    for msg in reversed(messages):
        if msg.role == role:
            return msg.content
    return ""


def _post_json(url: str, payload: dict, timeout: float) -> dict:
    response = requests.post(url, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _content_to_text(content: object) -> str:
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            elif item is not None:
                parts.append(str(item))
        return " ".join(parts).strip()

    if content is None:
        return ""

    return str(content)


def _generate_direct_reply(messages: list[WireMessage]) -> str:
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    lc_messages = wire_to_lc(messages)
    ai_response = llm.invoke([SystemMessage(content=DIRECT_REPLY_PROMPT)] + lc_messages)

    text = _content_to_text(getattr(ai_response, "content", "")).strip()
    if text:
        return text

    return "I understand. Can you share a bit more so I can help accurately?"


async def call_agent(url: str, messages: list[WireMessage], corr: str) -> list[WireMessage]:
    payload = {"messages": [m.model_dump() for m in messages]}
    destination = service_from_url(url)
    transport = outbound_transport_for_url(url)

    flow_log(
        sender="orchestrator",
        destination=destination,
        transport=transport,
        path="/run",
        phase="dispatch",
        corr=corr,
        extra=f"history_len={len(messages)}",
    )

    data = await asyncio.to_thread(_post_json, url, payload, 120.0)

    new_messages = [WireMessage(**item) for item in data["messages"]]
    flow_log(
        sender=destination,
        destination="orchestrator",
        transport=transport,
        path="/run",
        phase="response",
        corr=corr,
        status="ok",
        extra=f"last_ai='{_short(_last_role_text(new_messages, 'ai'))}'",
    )
    return new_messages


def should_force_finish_from_last_message(messages: list[WireMessage]) -> bool:
    if not messages:
        return False

    last = messages[-1]
    if last.role != "ai":
        return False

    content = last.content.lower()
    return "passing to" not in content and "handing over" not in content


def pick_last_reply(messages: list[WireMessage]) -> str:
    lc_messages = wire_to_lc(messages)
    return last_ai_text(lc_messages)


@app.post("/chat")
async def chat_endpoint(request: ChatRequest, http_request: Request):
    inbound_transport = request_transport(http_request)
    inbound_sender = request_sender(http_request, request.sender)
    corr = request_correlation_id(http_request)

    flow_log(
        sender=inbound_sender,
        destination="orchestrator",
        transport=inbound_transport,
        path="/chat",
        phase="inbound",
        corr=corr,
    )

    history = sessions.get(request.sender, []).copy()
    history.append(WireMessage(role="human", content=request.text))

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(Router)

    for _ in range(8):
        lc_messages = wire_to_lc(history)
        router_response = structured_llm.invoke([SystemMessage(content=SUPERVISOR_PROMPT)] + lc_messages)
        next_step = router_response.next_agent

        if should_force_finish_from_last_message(history):
            next_step = "FINISH"

        if next_step == "FINISH":
            if history and history[-1].role == "ai":
                reply = pick_last_reply(history)
            else:
                reply = _generate_direct_reply(history)
                history.append(WireMessage(role="ai", content=reply))

            sessions[request.sender] = history
            flow_log(
                sender="orchestrator",
                destination=inbound_sender,
                transport=inbound_transport,
                path="/chat",
                phase="reply",
                corr=corr,
                status="ok",
            )
            return {"reply": reply}

        target_url = CALENDAR_AGENT_URL if next_step == "calendar_agent" else MAPS_AGENT_URL

        try:
            history = await call_agent(target_url, history, corr)
        except requests.RequestException as exc:
            flow_log(
                sender="orchestrator",
                destination=service_from_url(target_url),
                transport=outbound_transport_for_url(target_url),
                path="/run",
                phase="response",
                corr=corr,
                status="error",
                extra=f"error='{_short(str(exc))}'",
            )
            raise HTTPException(status_code=502, detail=f"Agent call failed: {exc}") from exc

    reply = pick_last_reply(history)
    sessions[request.sender] = history
    flow_log(
        sender="orchestrator",
        destination=inbound_sender,
        transport=inbound_transport,
        path="/chat",
        phase="reply",
        corr=corr,
        status="ok",
        extra="max_iterations=true",
    )
    return {"reply": reply}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
