from __future__ import annotations

import time

from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI


def run_agent_until_response(
    messages: list[BaseMessage],
    prompt: str,
    tools: list,
    model: str = "gpt-4o",
) -> list[BaseMessage]:
    llm = ChatOpenAI(model=model, temperature=0).bind_tools(tools)

    while True:
        ai_message: AIMessage = llm.invoke([SystemMessage(content=prompt)] + messages)
        messages.append(ai_message)

        tool_calls = getattr(ai_message, "tool_calls", None) or []
        if not tool_calls:
            return messages

        for tool_call in tool_calls:
            tool = next((t for t in tools if t.name == tool_call["name"]), None)
            if tool is None:
                continue

            result = tool.invoke(tool_call)
            if isinstance(result, ToolMessage):
                tool_message = result
            else:
                tool_message = ToolMessage(
                    content=str(result),
                    name=tool_call.get("name"),
                    tool_call_id=tool_call.get("id", "tool_call"),
                )

            messages.append(tool_message)
            time.sleep(0.5)
