import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_google_community import GooglePlacesTool

from agent_service_common import run_agent_until_response
from aztm_bootstrap import login_aztm_from_env
from message_protocol import AgentRunRequest, AgentRunResponse, WireMessage, last_ai_text, lc_to_wire, wire_to_lc

load_dotenv()

app = FastAPI()

# Initialize AZTM after FastAPI app is created so auto-hook can detect the app.
login_aztm_from_env(server_mode=True)

BASE_DIR = os.path.dirname(__file__)
with open(os.path.join(BASE_DIR, "prompts", "maps.md"), "r", encoding="utf-8") as f:
    MAPS_PROMPT = f.read()

maps_tools = [GooglePlacesTool()]


def _short(text: str, max_len: int = 180) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _last_human_text(messages: list[WireMessage]) -> str:
    for msg in reversed(messages):
        if msg.role == "human":
            return msg.content
    return ""


@app.post("/run", response_model=AgentRunResponse)
async def run_maps_agent(request: AgentRunRequest):
    print(
        f"[MAPS] <- orchestrator messages={len(request.messages)} "
        f"last_human='{_short(_last_human_text(request.messages))}'",
        flush=True,
    )
    messages = wire_to_lc(request.messages)
    updated_messages = run_agent_until_response(messages, MAPS_PROMPT, maps_tools)
    reply = last_ai_text(updated_messages)
    print(f"[MAPS] -> orchestrator reply='{_short(reply)}'", flush=True)
    return AgentRunResponse(messages=lc_to_wire(updated_messages), reply=reply)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
