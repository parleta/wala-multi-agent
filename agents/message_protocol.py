from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from pydantic import BaseModel, Field


class WireMessage(BaseModel):
    role: Literal["human", "ai", "system", "tool"]
    content: str
    name: str | None = None
    tool_call_id: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class AgentRunRequest(BaseModel):
    messages: list[WireMessage]


class AgentRunResponse(BaseModel):
    messages: list[WireMessage]
    reply: str


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    return str(content)


def lc_to_wire(messages: list[BaseMessage]) -> list[WireMessage]:
    out: list[WireMessage] = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            out.append(WireMessage(role="human", content=_content_to_text(msg.content)))
        elif isinstance(msg, AIMessage):
            out.append(
                WireMessage(
                    role="ai",
                    content=_content_to_text(msg.content),
                    tool_calls=getattr(msg, "tool_calls", []) or [],
                )
            )
        elif isinstance(msg, ToolMessage):
            out.append(
                WireMessage(
                    role="tool",
                    content=_content_to_text(msg.content),
                    name=msg.name,
                    tool_call_id=getattr(msg, "tool_call_id", None),
                )
            )
        elif isinstance(msg, SystemMessage):
            out.append(WireMessage(role="system", content=_content_to_text(msg.content)))
        else:
            out.append(WireMessage(role="system", content=_content_to_text(msg.content)))
    return out


def wire_to_lc(messages: list[WireMessage]) -> list[BaseMessage]:
    out: list[BaseMessage] = []
    for msg in messages:
        if msg.role == "human":
            out.append(HumanMessage(content=msg.content))
        elif msg.role == "ai":
            out.append(AIMessage(content=msg.content, tool_calls=msg.tool_calls or []))
        elif msg.role == "tool":
            out.append(
                ToolMessage(
                    content=msg.content,
                    name=msg.name,
                    tool_call_id=msg.tool_call_id or "tool_call",
                )
            )
        else:
            out.append(SystemMessage(content=msg.content))
    return out


def last_ai_text(messages: list[BaseMessage]) -> str:
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return _content_to_text(msg.content)
    return ""
