import os
from typing import Annotated, TypedDict, Literal, Union
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_community import CalendarToolkit, GooglePlacesTool
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

# Load environment variables
load_dotenv()

# --- 1. Tool Setup ---
# Initialize toolkits
calendar_toolkit = CalendarToolkit()
calendar_tools = calendar_toolkit.get_tools()
maps_tools = [GooglePlacesTool()]

# Combine all tools for the central ToolNode
all_tools = calendar_tools + maps_tools
tool_node = ToolNode(all_tools)

# --- 2. State & Router ---
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

class Router(BaseModel):
    """Decide which agent should act next."""
    next_agent: Literal["calendar_agent", "maps_agent", "FINISH"] = Field(
        description="The agent to transfer control to, or FINISH if the task is done."
    )

from langchain_core.messages import SystemMessage

# --- 1. THE SUPERVISOR PROMPT ---
# This ensures the supervisor understands the "mission" of each agent.
SUPERVISOR_PROMPT = """
    You are the 'Wala' Orchestrator. Your job is to route the user's request 
    to the correct specialized agent.
    - Use 'maps_agent' for finding locations, addresses, restaurants, or travel times.
    - Use 'calendar_agent' for checking, creating, or managing events/schedules.
    - Use 'FINISH' only when the user's request has been completely satisfied.
    If a user asks a complex task (e.g., 'Find a place and book it'), send it to Maps first, 
    then once you have the address in history, send it to the Calendar.
"""

def supervisor_node(state: AgentState):
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(Router)
    
    # We prepend the SystemMessage to the conversation history
    messages = [SystemMessage(content=SUPERVISOR_PROMPT)] + state["messages"]
    response = structured_llm.invoke(messages)
    
    goto = response.next_agent
    print(f"\n[Supervisor Decision] Next Step --> {goto}")
    return Command(goto=goto if goto != "FINISH" else END)


# --- 2. THE CALENDAR AGENT PROMPT ---
CALENDAR_PROMPT = """
    You are a Google Calendar expert. Your goal is to manage the user's schedule. 
    you can create, modify, delete any event
"""

def calendar_agent(state: AgentState):
    print("--- [Calendar Agent Working] ---")
    llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(calendar_tools)
    messages = [SystemMessage(content=CALENDAR_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


# --- 3. THE MAPS AGENT PROMPT ---
MAPS_PROMPT = """
    You are a Google Maps and Places expert. 
    Your goal is to find the best locations based on user preferences.
    1. Provide specific addresses and names of places.
    2. If multiple options exist, ask the user for their preference.
    3. Ensure the address is clearly stated so the Calendar agent can use it later.
"""

def maps_agent(state: AgentState):
    print("--- [Maps Agent Working] ---")
    llm = ChatOpenAI(model="gpt-4o", temperature=0).bind_tools(maps_tools)
    messages = [SystemMessage(content=MAPS_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

# --- 4. Conditional Routing Logic ---
def route_after_agent(state: AgentState):
    """Check if the agent wants to use a tool or return to supervisor."""
    last_message = state["messages"][-1]
    
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        print(f"    (Agent requested {len(last_message.tool_calls)} tool call(s))")
        return "tools"
    
    return "supervisor"

# --- 5. Graph Construction ---
builder = StateGraph(AgentState)

builder.add_node("supervisor", supervisor_node)
builder.add_node("calendar_agent", calendar_agent)
builder.add_node("maps_agent", maps_agent)
builder.add_node("tools", tool_node)

builder.add_edge(START, "supervisor")

# Agents go to 'tools' if they have tool_calls, otherwise back to 'supervisor'
builder.add_conditional_edges(
    "calendar_agent", 
    route_after_agent,
    {"tools": "tools", "supervisor": "supervisor"}
)
builder.add_conditional_edges(
    "maps_agent", 
    route_after_agent,
    {"tools": "tools", "supervisor": "supervisor"}
)

# After tools execute, always return to supervisor to evaluate the result
builder.add_edge("tools", "supervisor")

memory = MemorySaver()
graph = builder.compile(checkpointer=memory)

# --- 6. Execution Loop ---
def run_wala():
    thread_config = {"configurable": {"thread_id": "wala_final_session"}}
    print("\n=== Wala AI Orchestrator (Google Integrations) ===")
    
    while True:
        user_input = input("\nUser: ")
        if user_input.lower() in ["quit", "exit", "q"]:
            break

        input_data = {"messages": [HumanMessage(content=user_input)]}
        
        for event in graph.stream(input_data, thread_config, stream_mode="values"):
            if event["messages"]:
                last_msg = event["messages"][-1]
                
                # Only print actual text content from the AI
                if isinstance(last_msg, AIMessage) and last_msg.content:
                    print(f"Agent: {last_msg.content}")

if __name__ == "__main__":
    run_wala()