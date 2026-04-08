import os

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from langchain_google_community import CalendarToolkit

from agent_service_common import run_agent_until_response
from aztm_bootstrap import login_aztm_from_env
from flow_log import flow_log, install_aztm_print_filter, request_correlation_id, request_sender, request_transport
from message_protocol import AgentRunRequest, AgentRunResponse, last_ai_text, lc_to_wire, wire_to_lc

load_dotenv()

app = FastAPI()

# Keep AZTM hook debug noise out of runtime logs.
install_aztm_print_filter()

# Initialize AZTM after FastAPI app is created so auto-hook can detect the app.
login_aztm_from_env(server_mode=True)

BASE_DIR = os.path.dirname(__file__)
with open(os.path.join(BASE_DIR, "prompts", "calendar.md"), "r", encoding="utf-8") as f:
    CALENDAR_PROMPT = f.read()

calendar_toolkit = CalendarToolkit()
calendar_tools = calendar_toolkit.get_tools()


@app.post("/run", response_model=AgentRunResponse)
async def run_calendar_agent(request: AgentRunRequest, http_request: Request):
    transport = request_transport(http_request)
    sender = request_sender(http_request, "orchestrator")
    corr = request_correlation_id(http_request)

    flow_log(
        sender=sender,
        destination="calendar_agent",
        transport=transport,
        path="/run",
        phase="inbound",
        corr=corr,
        extra=f"messages={len(request.messages)}",
    )

    messages = wire_to_lc(request.messages)
    updated_messages = run_agent_until_response(messages, CALENDAR_PROMPT, calendar_tools)
    reply = last_ai_text(updated_messages)

    flow_log(
        sender="calendar_agent",
        destination=sender,
        transport=transport,
        path="/run",
        phase="reply",
        corr=corr,
        status="ok",
    )

    return AgentRunResponse(messages=lc_to_wire(updated_messages), reply=reply)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
