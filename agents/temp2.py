import os
import time
from typing import Annotated, TypedDict, Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_google_community import CalendarToolkit, GooglePlacesTool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

load_dotenv()

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def load_prompt(filename: str) -> str:
    path = os.path.join("prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

SUPERVISOR_PROMPT = load_prompt("supervisor.md")
CALENDAR_PROMPT = load_prompt("calendar.md")
MAPS_PROMPT = load_prompt("maps.md")

calendar_toolkit = CalendarToolkit()
calendar_tools = calendar_toolkit.get_tools()
maps_tools = [GooglePlacesTool()]
all_tools = calendar_tools + maps_tools

def sequential_tool_node(state: AgentState):
    messages = state["messages"]
    last_message = messages[-1]
    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}
    results = []
    for tool_call in last_message.tool_calls:
        tool = next((t for t in all_tools if t.name == tool_call["name"]), None)
        if tool:
            result = tool.invoke(tool_call)
            results.append(result)
            time.sleep(0.5)
    return {"messages": results}

class Router(BaseModel):
    next_agent: Literal["calendar_agent", "maps_agent", "FINISH"] = Field(description="Transfer or FINISH.")

def supervisor_node(state: AgentState):
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(Router)
    last_message = state["messages"][-1]
    if isinstance(last_message, ToolMessage):
        return Command(goto="calendar_agent" if any(t.name == last_message.name for t in calendar_tools) else "maps_agent")
    messages = [SystemMessage(content=SUPERVISOR_PROMPT)] + state["messages"]
    response = structured_llm.invoke(messages)
    goto = response.next_agent
    if isinstance(last_message, AIMessage) and not getattr(last_message, "tool_calls", None):
        if not any(p in last_message.content.lower() for p in ["passing to", "handing over"]):
            goto = "FINISH"
    return Command(goto=goto if goto != "FINISH" else END)

def calendar_agent(state: AgentState):
    llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(calendar_tools)
    return {"messages": [llm.invoke([SystemMessage(content=CALENDAR_PROMPT)] + state["messages"])]}

def maps_agent(state: AgentState):
    llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(maps_tools)
    return {"messages": [llm.invoke([SystemMessage(content=MAPS_PROMPT)] + state["messages"])]}

def route_after_agent(state: AgentState):
    last_message = state["messages"][-1]
    return "tools" if hasattr(last_message, "tool_calls") and last_message.tool_calls else "supervisor"

builder = StateGraph(AgentState)
builder.add_node("supervisor", supervisor_node)
builder.add_node("calendar_agent", calendar_agent)
builder.add_node("maps_agent", maps_agent)
builder.add_node("tools", sequential_tool_node)
builder.add_edge(START, "supervisor")
builder.add_conditional_edges("calendar_agent", route_after_agent, {"tools": "tools", "supervisor": "supervisor"})
builder.add_conditional_edges("maps_agent", route_after_agent, {"tools": "tools", "supervisor": "supervisor"})
builder.add_edge("tools", "supervisor")

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)


service = calendar_toolkit.api_resource 
setting = service.settings().get(setting='timezone').execute()
print('timezone:', setting.get('value'))
