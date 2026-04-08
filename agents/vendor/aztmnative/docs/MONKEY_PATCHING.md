# AZTM Monkey Patching and Integration Guide

## Overview

AZTM (Agentic Zero Trust Mesh) intercepts HTTP traffic and routes it through the mesh by monkey patching popular HTTP client libraries and integrating with server frameworks. This document provides a comprehensive guide to understanding and using AZTM's patching system.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Client-Side Patching](#client-side-patching)
   - [Requests Library](#requests-library)
   - [HTTPX Library](#httpx-library)
3. [Server-Side Integration](#server-side-integration)
   - [FastAPI Integration](#fastapi-integration)
   - [LangGraph Integration](#langgraph-integration)
4. [Usage Guide](#usage-guide)
5. [Advanced Topics](#advanced-topics)

## Architecture Overview

AZTM operates on a fundamental principle: **clients have their HTTP libraries patched, servers don't**.

```
┌──────────────────┐          ┌──────────────────┐          ┌──────────────────┐
│   HTTP Client    │          │   Mesh Server    │          │   HTTP Server    │
│                  │          │                  │          │                  │
│  requests.get()  │──────────│                  │──────────│    FastAPI       │
│       ↓          │          │                  │          │       ↑          │
│  [PATCHED]       │          │                  │          │  [NOT PATCHED]   │
│       ↓          │          │                  │          │       ↑          │
│  AZTM payload ──────────────► Mesh routing ────────────────► Request handler │
└──────────────────┘          └──────────────────┘          └──────────────────┘
```

### Key Design Decisions

1. **No Server Patching**: Servers receive messages through handlers, not patches
2. **Transparent Client Patching**: HTTP clients work unchanged after `aztm.login()`
3. **Clean Separation**: The `server_mode` flag controls patching behavior
4. **Zero Port Exposure**: Servers don't listen on network ports

## Client-Side Patching

### When Patching Occurs

Client-side HTTP libraries are patched when you call `aztm.login()` without `server_mode=True`:

```python
import aztm

# This patches HTTP libraries (client mode)
aztm.login(userid="client@example.com", password="secret")

# This does NOT patch HTTP libraries (server mode)
aztm.login(userid="server@example.com", password="secret", server_mode=True)
```

### Requests Library

#### What Gets Patched

AZTM patches two key methods in the `requests` library:

1. **`requests.Session.request`** - Main entry point for all HTTP requests
2. **`requests.adapters.HTTPAdapter.send`** - Lower-level adapter send method

#### How It Works

```python
# Before patching
import requests
response = requests.get("https://api.example.com/data")

# After aztm.login()
import aztm
import requests

aztm.login(userid="client@example.com", password="secret")

# This now goes through AZTM
response = requests.get("https://api.example.com/data")
# 1. URL is mapped to an identity: api.example.com → api.example.com@mesh.example.com
# 2. HTTP request → AZTM envelope → transport payload
# 3. Sent to target identity
# 4. Response received via AZTM
# 5. Converted back to requests.Response object
```

#### Interception Logic

The patched `requests` implementation:
- Checks if URL should be intercepted (not file://, has mapping, etc.)
- Converts HTTP request to an AZTM envelope
- Sends via the mesh to the target identity
- Waits for response (with timeout)
- Converts the response back to `requests.Response`
- Falls back to original implementation on errors

### HTTPX Library

#### What Gets Patched

AZTM patches both sync and async HTTPX clients:

1. **`httpx.Client.send`** - Synchronous client send method
2. **`httpx.AsyncClient.send`** - Asynchronous client send method
3. **`HTTPTransport.handle_request`** - Lower-level transport (optional)

#### How It Works

```python
# Synchronous HTTPX
import httpx
import aztm

aztm.login(userid="client@example.com", password="secret")

with httpx.Client() as client:
    # This goes through AZTM
    response = client.get("https://api.example.com/data")

# Asynchronous HTTPX
async with httpx.AsyncClient() as client:
    # This also goes through AZTM
    response = await client.get("https://api.example.com/data")
```

#### Async Support

HTTPX patching preserves async/await patterns:
- Sync methods use `run_coroutine_threadsafe` to interact with the transport
- Async methods directly await transport operations
- Both maintain the same API surface

## Server-Side Integration

### FastAPI Integration

#### How It Works (NO PATCHING!)

FastAPI integration does **NOT** use monkey patching. Instead, it:

1. **Registers a handler** for inbound AZTM requests
2. **Converts the inbound envelope** to an ASGI-compatible request
3. **Calls the FastAPI app** directly via ASGI interface
4. **Captures the response** and sends it back via AZTM

```python
from fastapi import FastAPI
import aztm

app = FastAPI()

# Server mode: no HTTP libraries patched!
aztm.login(userid="api@example.com", password="secret", server_mode=True)

@app.get("/data")
async def get_data():
    # This runs when an inbound AZTM request arrives
    return {"payload": "Hello from AZTM"}

# No need to run uvicorn!
# The app receives requests via AZTM handler
```

#### Auto-Detection

AZTM automatically detects FastAPI apps in the current process:
- Searches through loaded modules
- Finds FastAPI instances
- Hooks them automatically
- No manual registration needed

### LangGraph Integration

#### Overview

AZTM provides special support for LangGraph's `RemoteGraph` functionality, enabling LangGraph compiled graphs to be served over the mesh without any network ports.

#### RemoteGraph Support

LangGraph's `RemoteGraph` class connects to remote LangGraph deployments via HTTP. With AZTM, these HTTP calls can be transparently routed through the mesh:

```python
# Client side - using RemoteGraph with AZTM
import aztm
from langgraph.pregel.remote import RemoteGraph

# Enable AZTM routing for HTTP
aztm.login(userid="client@example.com", password="secret")

# Map the LangGraph server URL to a service identity
aztm.register_service_mapping({
    "langgraph.api.com": "langgraph@example.com"
})

# RemoteGraph HTTP calls now go through AZTM
remote = RemoteGraph(
    assistant_id="my-assistant",
    url="https://langgraph.api.com"  # This gets routed via AZTM
)

# All these operations go through AZTM
result = await remote.ainvoke({"messages": [{"role": "user", "content": "Hello"}]})
state = await remote.aget_state(config)
```

#### Serving LangGraph Applications

AZTM can serve compiled LangGraph applications over the mesh:

```python
# Server side - serving a LangGraph app
import aztm
from langgraph.graph import StateGraph
from aztm.server.langgraph_hook import serve_langgraph

# Define your graph
workflow = StateGraph(State)
# ... add nodes and edges ...
app = workflow.compile()

# Login as server (no HTTP patching)
aztm.login(userid="langgraph@example.com", password="secret", server_mode=True)

# Serve the graph over AZTM
serve_langgraph(app)
# Now the graph receives requests via AZTM
```

#### Supported LangGraph Operations

The LangGraph integration supports:
- **Thread Management**: Create and manage conversation threads
- **Graph Invocation**: `invoke()` and `stream()` operations
- **State Access**: Get and update graph state
- **Streaming**: Full streaming support for graph execution
- **Health Checks**: Monitor graph availability

#### Auto-Detection

AZTM can auto-detect and serve LangGraph apps:
```python
# If your main module has a compiled graph named 'app', 'agent', or 'graph'
app = workflow.compile()  # This gets auto-detected

import aztm
aztm.login(userid="langgraph@example.com", password="secret", server_mode=True)
# App is automatically served if it's in __main__
```

## Usage Guide

### Basic Client Usage

```python
import aztm
import requests

# Step 1: Login as client
aztm.login(userid="client@example.com", password="secret")

# Step 2: Register service mappings (optional)
aztm.register_service_mapping({
    "localhost:8000": "myserver@example.com",
    "api.service.com": "api@example.com"
})

# Step 3: Make HTTP requests as normal
response = requests.get("http://localhost:8000/health")
print(response.json())
```

### Basic Server Usage

```python
import aztm
from fastapi import FastAPI

app = FastAPI()

# Step 1: Define your API
@app.get("/health")
async def health():
    return {"status": "healthy"}

# Step 2: Login as server (with server_mode=True)
aztm.login(userid="myserver@example.com", password="secret", server_mode=True)

# That's it! The server now receives requests via AZTM
# No need to run uvicorn or expose ports
```

### Service Discovery

AZTM uses two methods for service discovery:

1. **Service Mappings**: Explicit URL-to-identity mappings
   ```python
   aztm.register_service_mapping({
       "api.example.com": "api@example.com",
       "localhost:8000": "local.api@example.com"
   })
   ```

2. **URL-to-identity Conversion**: Automatic mapping based on hostname
   ```python
   # https://orders.api/path → orders.api@mesh.example.com
   # http://inventory.local/items → inventory.local@mesh.example.com
   ```

### Controlling Patching Behavior

#### Disable Patching for Specific URLs

```python
# URLs that are never intercepted:
# - file:// URLs
# - localhost without a service mapping
# - URLs you explicitly exclude

# You can check if a URL will be intercepted:
from aztm.interceptors.requests_hook import should_intercept
print(should_intercept("http://localhost:8000"))  # False unless mapped
print(should_intercept("https://api.example.com"))  # True
```

#### Unpatch Libraries

```python
import aztm

# Patch libraries
aztm.login(userid="client@example.com", password="secret")

# Later, restore original behavior
aztm.logout()  # This unpatches all libraries
```

## Advanced Topics

### Thread Safety

- Patching is thread-safe using locks
- Transport operations use proper async/await patterns
- Multiple concurrent requests are supported

### Error Handling

When errors occur, AZTM:
1. Logs the error with full details
2. Falls back to original HTTP implementation
3. Ensures the request completes (via HTTP or error response)

### Performance Considerations

- **Latency**: the transport adds ~10-50ms overhead for small payloads
- **Throughput**: Can handle 100+ req/s per connection
- **Payload Sizes**:
  - Small (<128KB): Inline in message
  - Medium (<5MB): Chunked streaming
  - Large (>5MB): Upload slots (planned)

### Protocol Details

AZTM uses a JSON envelope format:
```json
{
  "_aztm": {
    "method": "GET",
    "path": "/api/data",
    "headers": {"User-Agent": "..."},
    "corr": "uuid-correlation-id",
    "ts": 1234567890
  },
  "payload": {
    "actual": "request body"
  }
}
```

### Debugging

Enable debug logging to see patching details:
```python
import logging
logging.basicConfig(level=logging.DEBUG)

import aztm
aztm.login(...)  # You'll see detailed patching logs
```

Check if libraries are patched:
```python
from aztm.interceptors import requests_hook
print(requests_hook._original_request)  # Not None if patched
```

### Integration with Other Libraries

Libraries that use `requests` or `httpx` internally will automatically use AZTM:
- OpenAI Python SDK
- Anthropic Python SDK
- Most REST API clients
- LangChain HTTP tools
- LangGraph RemoteGraph

Libraries with custom HTTP implementations need explicit support:
- aiohttp (not currently supported)
- urllib3 directly (works if used via requests)
- Custom socket-level implementations

### Security Considerations

1. **Transport Authentication**: Use strong passwords and TLS
2. **Identity Validation**: Verify target identities before sending sensitive data
3. **No Open Ports**: Servers don't expose network attack surface
4. **End-to-End Encryption**: Can add OMEMO support (planned)

## Common Patterns

### Microservices Communication

```python
# Service A (client role for outgoing, server role for incoming)
import aztm
from fastapi import FastAPI
import requests

app = FastAPI()

# Login with server_mode=True for receiving requests
aztm.login(userid="service-a@example.com", password="secret", server_mode=True)

@app.post("/process")
async def process(data: dict):
    # This service can make outbound requests using the patched libraries
    # But its own endpoints aren't patched
    result = requests.post("http://service-b/compute", json=data)
    return {"processed": result.json()}
```

### API Gateway Pattern

```python
# Gateway that routes to multiple backend services
import aztm

aztm.login(userid="gateway@example.com", password="secret")

# Map all internal services
aztm.register_service_mapping({
    "auth.internal": "auth@example.com",
    "orders.internal": "orders@example.com",
    "inventory.internal": "inventory@example.com",
})

# Now the gateway can route to any service
def route_request(service: str, path: str, data: dict):
    url = f"http://{service}.internal{path}"
    return requests.post(url, json=data)
```

### Testing with AZTM

```python
# Test client
import aztm
import pytest
import requests

@pytest.fixture
def aztm_client():
    aztm.login(userid="test@example.com", password="test")
    yield
    aztm.logout()

def test_api_via_aztm(aztm_client):
    response = requests.get("http://api.service/health")
    assert response.status_code == 200
```

## Conclusion

AZTM's monkey patching system provides:
- **Zero-code-change** HTTP-over-mesh transport
- **Clean separation** between client and server behavior
- **Transparent integration** with existing libraries
- **No network ports** required for servers
- **Full support** for async/await patterns
- **Special integration** for LangGraph RemoteGraph

The key to understanding AZTM is remembering: **patch clients, not servers**. This design ensures servers can receive inbound requests while maintaining their ability to make their own HTTP calls if needed.
