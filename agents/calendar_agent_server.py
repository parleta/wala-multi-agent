import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from langchain_google_community import CalendarToolkit

from agent_service_common import run_agent_until_response
from message_protocol import AgentRunRequest, AgentRunResponse, last_ai_text, lc_to_wire, wire_to_lc

load_dotenv()

app = FastAPI()

BASE_DIR = os.path.dirname(__file__)
with open(os.path.join(BASE_DIR, "prompts", "calendar.md"), "r", encoding="utf-8") as f:
    CALENDAR_PROMPT = f.read()

calendar_toolkit = CalendarToolkit()
calendar_tools = calendar_toolkit.get_tools()


@app.post("/run", response_model=AgentRunResponse)
async def run_calendar_agent(request: AgentRunRequest):
    messages = wire_to_lc(request.messages)
    updated_messages = run_agent_until_response(messages, CALENDAR_PROMPT, calendar_tools)
    return AgentRunResponse(messages=lc_to_wire(updated_messages), reply=last_ai_text(updated_messages))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
