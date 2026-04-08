"""
LangGraph server integration for AZTM
Enables LangGraph compiled graphs to receive HTTP-like requests via AZTM
"""

import json
import logging
import asyncio
from typing import Optional, Dict, Any, Union
from datetime import datetime
import uuid


def _to_jsonable(obj):
    """Best-effort conversion of LangGraph/LangChain results to JSON-serializable types."""
    try:
        import json as _json
        # Already json-serializable
        _json.dumps(obj)
        return obj
    except Exception:
        pass

    # Pydantic models
    if hasattr(obj, "model_dump"):
        try:
            return obj.model_dump()
        except Exception:
            pass
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass

    # LangChain messages
    # Detect BaseMessage-like objects (have 'content' attr)
    if hasattr(obj, "content"):
        role = getattr(obj, "role", None) or getattr(obj, "type", None) or "message"
        try:
            content = obj.content
        except Exception:
            content = str(obj)
        return {"role": role, "content": content}

    # Collections
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_to_jsonable(v) for v in obj]

    # Fallback to string
    try:
        return str(obj)
    except Exception:
        return "<unserializable>"

logger = logging.getLogger(__name__)


def serve_langgraph(graph, client=None, config=None):
    """
    Serve a LangGraph compiled graph over AZTM
    
    Args:
        graph: Compiled LangGraph application (from workflow.compile())
        client: AZTM XMPP client (if None, uses the global client)
        config: Optional configuration
        
    Returns:
        The running AZTM server task
    """
    from aztm.protocol.message import parse_request_envelope, create_response_envelope
    from aztm.core.auth import get_client
    
    # Get the AZTM client
    if client is None:
        client = get_client()
        if not client:
            raise RuntimeError("AZTM not initialized. Call aztm.login() first.")
    
    logger.info("Starting LangGraph AZTM server")
    
    # Store thread states (in production, use persistent storage)
    thread_store = {}
    
    async def handle_langgraph_request(msg):
        """Handle incoming AZTM message as LangGraph request"""
        try:
            # Parse the AZTM message
            from_jid = msg["from"].bare
            subject = msg.get("subject", "")
            body = msg["body"]
            msg_id = msg.get("id", "")
            
            print(f"\n📥 Incoming Request from {from_jid}")
            print(f"   Subject: {subject}")
            print(f"   Message ID: {msg_id}")
            
            # Parse request envelope
            envelope = parse_request_envelope(body)
            aztm_meta = envelope["_aztm"]
            payload = envelope.get("payload", {})
            
            # Extract request details
            method = aztm_meta["method"]
            path = aztm_meta["path"]
            headers = aztm_meta.get("headers", {})
            
            # Log the request details
            print(f"   Method: {method} {path}")
            if payload:
                import json
                try:
                    print(f"   Payload: {json.dumps(payload, indent=2)[:500]}..." if len(str(payload)) > 500 else f"   Payload: {json.dumps(payload, indent=2)}")
                except:
                    print(f"   Payload: {str(payload)[:200]}...")
            
            # Route based on path
            response_data = await route_langgraph_request(
                graph, thread_store, method, path, payload, headers
            )
            
            # Ensure response_data is not None
            if response_data is None:
                response_data = {
                    "status": 500,
                    "headers": {"Content-Type": "application/json"},
                    "body": {"error": "No response from handler"}
                }
            
            # Create response envelope
            response_envelope = create_response_envelope(
                status=response_data.get("status", 200),
                headers=response_data.get("headers", {"Content-Type": "application/json"}),
                body=response_data.get("body"),
                corr=aztm_meta["corr"]
            )
            
            # Log the response
            print(f"\n📤 Sending Response to {from_jid}")
            print(f"   Status: {response_data.get('status')}")
            response_body = response_data.get('body')
            if response_body:
                import json
                try:
                    body_str = json.dumps(response_body, indent=2)
                    print(f"   Body: {body_str[:500]}..." if len(body_str) > 500 else f"   Body: {body_str}")
                except:
                    print(f"   Body: {str(response_body)[:200]}...")
            print("-" * 40)
            
            # Send response back via AZTM
            msg = client.make_message(
                mto=from_jid,
                mbody=response_envelope,
                msubject=f"{subject}:response",
                mtype="chat"
            )
            if msg_id:
                msg['id'] = msg_id  # Set message ID for correlation
            msg.send()
            
        except Exception as e:
            print(f"\n❌ Error handling request: {e}")
            logger.error(f"Error handling LangGraph request: {e}", exc_info=True)
            
            # Send error response
            try:
                error_envelope = create_response_envelope(
                    status=500,
                    headers={"Content-Type": "application/json"},
                    body={"error": str(e)},
                    corr=aztm_meta.get("corr") if 'aztm_meta' in locals() else None
                )
                
                error_msg = client.make_message(
                    mto=from_jid,
                    mbody=error_envelope,
                    msubject=f"{subject}:error",
                    mtype="chat"
                )
                if msg_id:
                    error_msg['id'] = msg_id
                error_msg.send()
            except:
                logger.error("Failed to send error response")
    
    # Wrapper to handle async properly
    def sync_handler(msg):
        """Sync wrapper for async handler"""
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Schedule the async handler
            task = loop.create_task(handle_langgraph_request(msg))
        except Exception as e:
            logger.error(f"Error scheduling handler: {e}")
    
    # Register the sync wrapper as message handler
    client.add_event_handler("message", sync_handler)
    
    logger.info(f"LangGraph server ready on AZTM (no ports exposed)")
    logger.info(f"Listening as: {client.boundjid.bare}")
    
    return client


async def route_langgraph_request(graph, thread_store, method: str, path: str, payload: Dict, headers: Dict) -> Dict:
    """
    Route HTTP-like requests to appropriate LangGraph operations
    
    Args:
        graph: The compiled LangGraph
        thread_store: Dictionary storing thread states
        method: HTTP method
        path: Request path
        payload: Request body
        headers: Request headers
        
    Returns:
        Response dictionary with status, headers, and body
    """
    
    # Parse the path to determine the operation
    path_parts = path.strip("/").split("/")
    
    try:
        # Thread operations
        if path_parts[0] == "threads":
            if method == "POST" and len(path_parts) == 1:
                # Create new thread
                thread_id = str(uuid.uuid4())
                thread_store[thread_id] = {
                    "thread_id": thread_id,
                    "created_at": datetime.now().isoformat(),
                    "state": {}
                }
                return {
                    "status": 200,
                    "body": {"thread_id": thread_id}
                }
            
            elif method == "GET" and len(path_parts) == 2:
                # Get thread state
                thread_id = path_parts[1]
                if thread_id in thread_store:
                    return {
                        "status": 200,
                        "body": thread_store[thread_id]
                    }
                return {
                    "status": 404,
                    "body": {"error": "Thread not found"}
                }
            
            elif method == "POST" and len(path_parts) == 3 and path_parts[2] == "runs":
                # Create a run for a thread (invoke the graph)
                thread_id = path_parts[1]
                
                # Get the input from the payload
                graph_input = payload.get("input", {})
                if not graph_input:
                    # Try to get messages directly from payload
                    if "messages" in payload:
                        graph_input = {"messages": payload["messages"]}
                    else:
                        return {
                            "status": 400,
                            "body": {"error": "No input provided"}
                        }
                
                # Create config for the graph
                config = {"configurable": {"thread_id": thread_id}}
                
                # Generate run_id
                run_id = str(uuid.uuid4())
                
                # Invoke the graph
                logger.debug(f"Creating run {run_id} for thread {thread_id} with input: {graph_input}")
                
                try:
                    # Handle both sync and async graphs
                    if asyncio.iscoroutinefunction(graph.invoke):
                        result = await graph.invoke(graph_input, config=config)
                    else:
                        # Run sync function in executor
                        loop = asyncio.get_event_loop()
                        result = await loop.run_in_executor(None, graph.invoke, graph_input, config)
                    
                    # Store the result in thread state
                    if thread_id not in thread_store:
                        thread_store[thread_id] = {
                            "thread_id": thread_id,
                            "created_at": datetime.now().isoformat(),
                            "state": {}
                        }
                    
                    thread_store[thread_id]["runs"] = thread_store[thread_id].get("runs", {})
                    thread_store[thread_id]["runs"][run_id] = {
                        "run_id": run_id,
                        "status": "completed",
                        "result": _to_jsonable(result),
                        "created_at": datetime.now().isoformat()
                    }
                    
                    return {
                        "status": 200,
                        "body": {
                            "run_id": run_id,
                            "thread_id": thread_id,
                            "status": "completed",
                            "result": _to_jsonable(result)
                        }
                    }
                    
                except Exception as e:
                    logger.error(f"Error creating run: {e}", exc_info=True)
                    return {
                        "status": 500,
                        "body": {"error": str(e)}
                    }
            
            elif method == "GET" and len(path_parts) == 5 and path_parts[2] == "runs" and path_parts[4] == "join":
                # Get run result (wait for completion)
                thread_id = path_parts[1]
                run_id = path_parts[3]
                
                if thread_id in thread_store:
                    runs = thread_store[thread_id].get("runs", {})
                    if run_id in runs:
                        return {
                            "status": 200,
                            "body": runs[run_id]
                        }
                    return {
                        "status": 404,
                        "body": {"error": "Run not found"}
                    }
                return {
                    "status": 404,
                    "body": {"error": "Thread not found"}
                }
        
        # Graph invocation (the main agent endpoint)
        elif path_parts[0] == "agent" and path_parts[1] == "invoke":
            if method != "POST":
                return {
                    "status": 405,
                    "body": {"error": "Method not allowed"}
                }
            
            # Extract thread_id from payload or create new
            thread_id = payload.get("config", {}).get("configurable", {}).get("thread_id")
            if not thread_id:
                thread_id = str(uuid.uuid4())
                thread_store[thread_id] = {
                    "thread_id": thread_id,
                    "created_at": datetime.now().isoformat()
                }
            
            # Prepare the input for LangGraph
            graph_input = payload.get("input", {})
            if not graph_input:
                # Try to construct from messages if provided
                if "messages" in payload:
                    graph_input = {"messages": payload["messages"]}
                else:
                    return {
                        "status": 400,
                        "body": {"error": "No input provided"}
                    }
            
            # Create config for the graph
            config = {"configurable": {"thread_id": thread_id}}
            
            # Invoke the graph
            logger.debug(f"Invoking LangGraph with input: {graph_input}")
            
            # Handle both sync and async graphs
            if asyncio.iscoroutinefunction(graph.invoke):
                result = await graph.invoke(graph_input, config=config)
            else:
                # Run sync function in executor
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, graph.invoke, graph_input, config)
            
            # Store updated state
            thread_store[thread_id]["state"] = result
            
            return {
                "status": 200,
                "body": _to_jsonable(result)
            }
        
        # Stream endpoint
        elif path_parts[0] == "agent" and path_parts[1] == "stream":
            if method != "POST":
                return {
                    "status": 405,
                    "body": {"error": "Method not allowed"}
                }
            
            # Extract thread_id
            thread_id = payload.get("config", {}).get("configurable", {}).get("thread_id")
            if not thread_id:
                thread_id = str(uuid.uuid4())
            
            # Prepare input
            graph_input = payload.get("input", {})
            if not graph_input and "messages" in payload:
                graph_input = {"messages": payload["messages"]}
            
            config = {"configurable": {"thread_id": thread_id}}
            
            # Collect stream results
            stream_results = []
            
            # Handle streaming
            if hasattr(graph, 'astream'):
                async for chunk in graph.astream(graph_input, config=config):
                    stream_results.append(chunk)
            elif hasattr(graph, 'stream'):
                for chunk in graph.stream(graph_input, config=config):
                    stream_results.append(chunk)
            else:
                return {
                    "status": 501,
                    "body": {"error": "Streaming not supported"}
                }
            
            return {
                "status": 200,
                "body": {
                    "chunks": _to_jsonable(stream_results),
                    "thread_id": thread_id
                }
            }
        
        # Get graph state
        elif path_parts[0] == "agent" and path_parts[1] == "state":
            thread_id = payload.get("config", {}).get("configurable", {}).get("thread_id")
            
            if not thread_id:
                return {
                    "status": 400,
                    "body": {"error": "thread_id required"}
                }
            
            # Get state from graph
            config = {"configurable": {"thread_id": thread_id}}
            
            if hasattr(graph, 'get_state'):
                if asyncio.iscoroutinefunction(graph.get_state):
                    state = await graph.get_state(config)
                else:
                    loop = asyncio.get_event_loop()
                    state = await loop.run_in_executor(None, graph.get_state, config)
                
                return {
                    "status": 200,
                    "body": state
                }
            
            # Fallback to stored state
            if thread_id in thread_store:
                return {
                    "status": 200,
                    "body": thread_store[thread_id].get("state", {})
                }
            
            return {
                "status": 404,
                "body": {"error": "State not found"}
            }
        
        # Health check
        elif path_parts[0] == "health":
            return {
                "status": 200,
                "body": {"status": "healthy", "graph": "active"}
            }
        
        # Default 404
        else:
            return {
                "status": 404,
                "body": {"error": f"Path not found: {path}"}
            }
            
    except Exception as e:
        logger.error(f"Error in route handler: {e}", exc_info=True)
        return {
            "status": 500,
            "body": {"error": str(e)}
        }


def hook_langgraph_imports():
    """
    Hook into LangGraph imports to auto-detect and serve graphs
    This is called automatically when AZTM is imported with LangGraph present
    """
    import sys
    
    # Check if LangGraph is being used
    langgraph_modules = [m for m in sys.modules if 'langgraph' in m]
    
    if langgraph_modules:
        logger.debug(f"LangGraph detected: {langgraph_modules}")
        
        # Try to find compiled graphs
        for module_name, module in sys.modules.items():
            if module is None:
                continue
                
            # Skip internals
            if module_name.startswith("_"):
                continue
                
            # Look for compiled graphs (usually named 'app', 'agent', or 'graph')
            try:
                if hasattr(module, "__dict__"):
                    for name in ['app', 'agent', 'graph', 'workflow']:
                        if name in module.__dict__:
                            obj = module.__dict__[name]
                            # Check if it looks like a compiled graph
                            if hasattr(obj, 'invoke') and (hasattr(obj, 'stream') or hasattr(obj, 'astream')):
                                logger.info(f"Found LangGraph app: {module_name}.{name}")
                                # Auto-serve if we're the main module
                                if module_name == "__main__":
                                    logger.info(f"Auto-serving LangGraph app: {name}")
                                    return serve_langgraph(obj)
            except:
                continue
    
    return None