import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_google_community import GooglePlacesTool

from agent_service_common import run_agent_until_response
from message_protocol import AgentRunRequest, AgentRunResponse, last_ai_text, lc_to_wire, wire_to_lc

load_dotenv()

app = FastAPI()

BASE_DIR = os.path.dirname(__file__)
with open(os.path.join(BASE_DIR, "prompts", "maps.md"), "r", encoding="utf-8") as f:
    MAPS_PROMPT = f.read()

maps_tools = [GooglePlacesTool()]


@app.post("/run", response_model=AgentRunResponse)
async def run_maps_agent(request: AgentRunRequest):
    messages = wire_to_lc(request.messages)
    updated_messages = run_agent_until_response(messages, MAPS_PROMPT, maps_tools)
    return AgentRunResponse(messages=lc_to_wire(updated_messages), reply=last_ai_text(updated_messages))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
