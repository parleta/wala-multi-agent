import asyncio
import os
from typing import Literal

import requests
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from langchain_core.messages import SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from aztm_bootstrap import login_aztm_from_env
from message_protocol import WireMessage, last_ai_text, wire_to_lc

load_dotenv()

app = FastAPI()

# Initialize AZTM after FastAPI app is created so auto-hook can detect the app.
login_aztm_from_env(server_mode=True)

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


def _debug(msg: str) -> None:
    print(f"[ORCH] {msg}", flush=True)


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


async def call_agent(url: str, agent_name: str, messages: list[WireMessage]) -> list[WireMessage]:
    payload = {"messages": [m.model_dump() for m in messages]}
    _debug(
        f"-> {agent_name} url={url} "
        f"last_human='{_short(_last_role_text(messages, 'human'))}' "
        f"history_len={len(messages)}"
    )
    data = await asyncio.to_thread(_post_json, url, payload, 120.0)

    new_messages = [WireMessage(**item) for item in data["messages"]]
    _debug(
        f"<- {agent_name} "
        f"last_ai='{_short(_last_role_text(new_messages, 'ai'))}' "
        f"history_len={len(new_messages)}"
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
async def chat_endpoint(request: ChatRequest):
    _debug(f"<- bot sender={request.sender} text='{_short(request.text)}'")
    history = sessions.get(request.sender, []).copy()
    history.append(WireMessage(role="human", content=request.text))

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(Router)

    for _ in range(8):
        lc_messages = wire_to_lc(history)
        router_response = structured_llm.invoke([SystemMessage(content=SUPERVISOR_PROMPT)] + lc_messages)
        next_step = router_response.next_agent
        _debug(f"router next_agent={next_step}")

        if should_force_finish_from_last_message(history):
            next_step = "FINISH"
            _debug("forcing FINISH due to final AI response in history")

        if next_step == "FINISH":
            if history and history[-1].role == "ai":
                reply = pick_last_reply(history)
            else:
                reply = _generate_direct_reply(history)
                history.append(WireMessage(role="ai", content=reply))
                _debug("generated fresh FINISH reply for latest human turn")

            sessions[request.sender] = history
            _debug(f"-> bot reply='{_short(reply)}'")
            return {"reply": reply}

        target_url = CALENDAR_AGENT_URL if next_step == "calendar_agent" else MAPS_AGENT_URL

        try:
            history = await call_agent(target_url, next_step, history)
        except requests.RequestException as exc:
            _debug(f"agent call failed next_agent={next_step} error={exc}")
            raise HTTPException(status_code=502, detail=f"Agent call failed: {exc}") from exc

    reply = pick_last_reply(history)
    sessions[request.sender] = history
    _debug(f"-> bot reply(max-iterations)='{_short(reply)}'")
    return {"reply": reply}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
