#!/usr/bin/env python3
"""Example showing how to use LangGraph RemoteGraph with AZTM.

This example demonstrates how AZTM transparently routes LangGraph
RemoteGraph HTTP calls through XMPP, enabling agent-to-agent communication
without exposed network ports.
"""

import asyncio
import aztm
from typing import Any, Dict

# Example 1: Client using RemoteGraph with AZTM
async def client_example():
    """Client that connects to a remote LangGraph via AZTM."""
    
    # Step 1: Login to AZTM (patches HTTP libraries)
    aztm.login(
        userid="langgraph_client@xmpp.example",
        password="client_secret"
    )
    
    # Step 2: Register the LangGraph server mapping
    aztm.register_service_mapping({
        # Map the URL hostname to XMPP JID
        "langgraph.api.local": "langgraph_server@xmpp.example",
        "my-langgraph-deployment.com": "langgraph_prod@xmpp.example",
    })
    
    # Step 3: Use RemoteGraph normally - HTTP calls go through XMPP!
    from langgraph.pregel.remote import RemoteGraph
    
    # Connect to remote graph - this HTTP connection goes via XMPP
    remote = RemoteGraph(
        assistant_id="my-assistant",
        url="https://langgraph.api.local",  # This gets routed to XMPP JID
        # api_key="your-api-key",  # Optional: still works with auth
    )
    
    # All these operations now go through XMPP transport!
    
    # Invoke the graph
    result = await remote.ainvoke({
        "messages": [
            {"role": "user", "content": "Hello from AZTM!"}
        ]
    })
    print(f"Result: {result}")
    
    # Stream responses
    async for chunk in remote.astream({
        "messages": [
            {"role": "user", "content": "Tell me a story"}
        ]
    }):
        print(f"Chunk: {chunk}")
    
    # Get state
    state = await remote.aget_state({"thread_id": "thread-123"})
    print(f"State: {state}")
    
    # Update state
    await remote.aupdate_state(
        {"thread_id": "thread-123"},
        {"messages": [{"role": "assistant", "content": "Updated!"}]}
    )


# Example 2: Server hosting a LangGraph via AZTM
def server_example():
    """Server that hosts a LangGraph application via AZTM."""
    
    from langgraph.graph import StateGraph, MessagesState
    from langgraph.prebuilt import ToolNode
    from langchain_core.messages import AIMessage
    import aztm
    from aztm.server.langgraph_hook import serve_langgraph
    
    # Step 1: Define your LangGraph application
    def chatbot(state: MessagesState) -> Dict[str, Any]:
        """Simple chatbot node."""
        return {
            "messages": [
                AIMessage(content="Hello! I'm running via AZTM/XMPP!")
            ]
        }
    
    # Build the graph
    workflow = StateGraph(MessagesState)
    workflow.add_node("chatbot", chatbot)
    workflow.set_entry_point("chatbot")
    workflow.set_finish_point("chatbot")
    
    # Compile the graph
    app = workflow.compile()
    
    # Step 2: Login to AZTM as a server (no HTTP patching)
    aztm.login(
        userid="langgraph_server@xmpp.example",
        password="server_secret",
        server_mode=True  # Important: don't patch HTTP libs on server
    )
    
    # Step 3: Serve the LangGraph app via AZTM
    serve_langgraph(app)
    
    print("LangGraph server running via AZTM/XMPP...")
    print("No network ports exposed!")
    print("Clients can connect using RemoteGraph with the URL:")
    print("  https://langgraph.api.local")
    print("Which will be routed to JID: langgraph_server@xmpp.example")
    
    # Keep running
    import time
    while True:
        time.sleep(1)


# Example 3: Using RemoteGraph as a subgraph in another graph
async def subgraph_example():
    """Example using RemoteGraph as a node in another graph."""
    
    from langgraph.graph import StateGraph, MessagesState
    from langgraph.pregel.remote import RemoteGraph
    import aztm
    
    # Login to AZTM
    aztm.login(
        userid="orchestrator@xmpp.example",
        password="orchestrator_secret"
    )
    
    # Register mappings for remote services
    aztm.register_service_mapping({
        "research.agent": "research@xmpp.example",
        "writer.agent": "writer@xmpp.example",
    })
    
    # Create RemoteGraph instances for remote agents
    research_agent = RemoteGraph(
        assistant_id="research-assistant",
        url="https://research.agent",
        name="researcher"  # Name for the node
    )
    
    writer_agent = RemoteGraph(
        assistant_id="writer-assistant",
        url="https://writer.agent",
        name="writer"
    )
    
    # Build orchestrator graph with remote subgraphs
    workflow = StateGraph(MessagesState)
    
    # Add remote graphs as nodes - they communicate via XMPP!
    workflow.add_node(research_agent)  # Uses the 'name' as node ID
    workflow.add_node(writer_agent)
    
    # Define flow
    workflow.set_entry_point("researcher")
    workflow.add_edge("researcher", "writer")
    workflow.set_finish_point("writer")
    
    # Compile and run
    app = workflow.compile()
    
    result = await app.ainvoke({
        "messages": [
            {"role": "user", "content": "Write a blog post about AZTM"}
        ]
    })
    
    print(f"Orchestrated result: {result}")


# Example 4: Complete multi-agent system
async def complete_system_example():
    """Complete example of a multi-agent system using AZTM."""
    
    import asyncio
    from concurrent.futures import ProcessPoolExecutor
    
    async def run_agent_server(agent_id: str, jid: str, password: str):
        """Run an agent server in a separate process."""
        from langgraph.graph import StateGraph, MessagesState
        from langchain_core.messages import AIMessage
        import aztm
        from aztm.server.langgraph_hook import serve_langgraph
        
        # Create agent-specific graph
        def agent_node(state: MessagesState) -> Dict[str, Any]:
            return {
                "messages": [
                    AIMessage(content=f"Response from {agent_id}")
                ]
            }
        
        workflow = StateGraph(MessagesState)
        workflow.add_node("agent", agent_node)
        workflow.set_entry_point("agent")
        workflow.set_finish_point("agent")
        app = workflow.compile()
        
        # Login and serve
        aztm.login(userid=jid, password=password, server_mode=True)
        serve_langgraph(app)
        
        # Keep running
        while True:
            await asyncio.sleep(1)
    
    # Start multiple agent servers (in production, these would be separate services)
    executor = ProcessPoolExecutor(max_workers=3)
    
    # Start agent servers
    agents = [
        ("research-agent", "research@xmpp.example", "pass1"),
        ("writer-agent", "writer@xmpp.example", "pass2"),
        ("reviewer-agent", "reviewer@xmpp.example", "pass3"),
    ]
    
    futures = []
    for agent_id, jid, password in agents:
        future = executor.submit(
            asyncio.run,
            run_agent_server(agent_id, jid, password)
        )
        futures.append(future)
    
    # Give servers time to start
    await asyncio.sleep(2)
    
    # Now run the orchestrator client
    aztm.login(
        userid="orchestrator@xmpp.example",
        password="orchestrator_pass"
    )
    
    aztm.register_service_mapping({
        "research.local": "research@xmpp.example",
        "writer.local": "writer@xmpp.example",
        "reviewer.local": "reviewer@xmpp.example",
    })
    
    # Create remote connections to all agents
    from langgraph.pregel.remote import RemoteGraph
    
    research = RemoteGraph(
        assistant_id="research",
        url="https://research.local",
        name="research"
    )
    
    writer = RemoteGraph(
        assistant_id="writer",
        url="https://writer.local",
        name="writer"
    )
    
    reviewer = RemoteGraph(
        assistant_id="reviewer",
        url="https://reviewer.local",
        name="reviewer"
    )
    
    # Build complex workflow
    workflow = StateGraph(MessagesState)
    workflow.add_node(research)
    workflow.add_node(writer)
    workflow.add_node(reviewer)
    
    workflow.set_entry_point("research")
    workflow.add_edge("research", "writer")
    workflow.add_edge("writer", "reviewer")
    workflow.set_finish_point("reviewer")
    
    app = workflow.compile()
    
    # Run the complete workflow - all communication via XMPP!
    result = await app.ainvoke({
        "messages": [
            {"role": "user", "content": "Create a technical article"}
        ]
    })
    
    print(f"Complete workflow result: {result}")
    
    # Cleanup
    for future in futures:
        future.cancel()
    executor.shutdown()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python langgraph_remote_example.py [client|server|subgraph|complete]")
        sys.exit(1)
    
    mode = sys.argv[1]
    
    if mode == "client":
        asyncio.run(client_example())
    elif mode == "server":
        server_example()
    elif mode == "subgraph":
        asyncio.run(subgraph_example())
    elif mode == "complete":
        asyncio.run(complete_system_example())
    else:
        print(f"Unknown mode: {mode}")
        print("Use: client, server, subgraph, or complete")
        sys.exit(1)