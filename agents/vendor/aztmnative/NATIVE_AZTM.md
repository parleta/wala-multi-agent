# Native AZTM Usage Guide

AZTM (Agentic Zero Trust Mesh) provides a clean, native Python API for secure, peer-to-peer communication and RPC. This "Native Mode" allows you to build applications that communicate directly over the mesh without any "monkey patching" or interception of existing HTTP libraries.

## 1. Core Concepts

*   **Identity**: Your unique address on the mesh (e.g., `client@aztm.network`).
*   **Topic**: A routing key for your events and RPC endpoints (e.g., `orders/create`, `notifications`).
*   **Payload**: The data you send (JSON-serializable dictionaries, lists, strings, etc.).
*   **Session**: Your active connection to the mesh.

The native API completely abstracts the underlying transport layer. You interact only with `aztm.connect`, `send`, `request`, and `on`.

## 2. Connecting to the Mesh

To start, establish a session using your credentials.

### Synchronous Connection (Blocking)

Use this for scripts or standard synchronous applications.

```python
import aztm

# Connects and blocks until session is established
session = aztm.connect(
    identity="my-service@aztm.network",
    password="my-secure-password"
)

print(f"Connected as: {session.identity}")
```

### Asynchronous Connection (Async/Await)

Use this for `asyncio` applications (like FastAPI, Quart, or async scripts).

```python
import aztm
import asyncio

async def main():
    session = await aztm.connect_async(
        identity="my-service@aztm.network",
        password="my-secure-password"
    )
    print(f"Connected as: {session.identity}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 3. Communication Patterns

AZTM supports two primary patterns: **Fire-and-Forget** (Events) and **Request-Response** (RPC).

### Pattern A: Fire-and-Forget (Events)

Use this when you want to send data without waiting for a reply (e.g., event notifications, logging, status updates).

#### Sender

```python
# Send an event to a specific topic
session.send(
    identity="logger@aztm.network",
    topic="app/logs",
    data={
        "level": "INFO",
        "content": "User logged in",
        "timestamp": 1234567890
    }
)
```

#### Receiver

Register a handler function for the topic.

```python
def log_handler(context, payload):
    sender = context['identity']
    print(f"Log received from {sender}: {payload}")

# Listen for messages on "app/logs"
session.on("app/logs", log_handler)
```

### Pattern B: Request-Response (RPC)

Use this when you need a result back from the remote service (e.g., database queries, calculations, actions that return status). AZTM handles the correlation automatically.

#### Caller (Client)

Use `session.request()` to send data and wait for the response.

```python
try:
    # Sends request and waits up to 5 seconds for a reply
    result = session.request(
        identity="calculator@aztm.network",
        topic="math/add",
        data={"a": 10, "b": 5},
        timeout=5.0
    )
    print(f"Result: {result}")  # Output: 15
except TimeoutError:
    print("Request timed out!")
```

#### Handler (Server)

The handler function simply returns a value. AZTM automatically routes this return value back to the caller.

```python
def add_handler(context, payload):
    print(f"Request from {context['identity']}")
    a = payload.get("a", 0)
    b = payload.get("b", 0)
    
    # The return value is sent back to the caller
    return a + b

session.on("math/add", add_handler)
```

---

## 4. Advanced Usage

### Context Object
The `context` dictionary passed to your handler contains metadata about the incoming event/RPC:

*   `identity`: The identity of the sender.
*   `topic`: The topic the message was sent to.
*   `correlation_id`: (Optional) internal ID used for RPC tracking.

### Wildcard Subscriptions
You can subscribe to all topics using `*` (implementation dependent on mesh configuration, but generally supported for "catch-all" debugging).

```python
session.on("*", lambda ctx, data: print(f"Spying on {ctx['topic']}: {data}"))
```

### Configuration
You can pass additional configuration options to `connect`:

```python
session = aztm.connect(
    identity="user@aztm.network",
    password="...",
    host="mesh.example.com",   # Mesh host
    port=443,                   # Mesh port
    secure=True,                # Enable transport security
    verify=True,                # Validate server certificate
    route_weight=100            # Load balancing hint (higher values are preferred)
)
```

#### Load balancing / multiple server replicas
If you run multiple server processes under the same `identity` (horizontal scaling), the mesh can route incoming events/RPC calls to any available replica.

When multiple replicas might respond, AZTM uses the first matching response it receives for an RPC call. If you want to prefer one replica (for example, during debugging or blue/green rollout), set a higher `route_weight` on that server.

Accepted parameter names:
- `route_weight` (preferred)
- `load_balancing_weight` (alias)

Alternatively, use environment variables:
*   `AZTM_HOST`
*   `AZTM_PORT`
*   `AZTM_DOMAIN`
*   `AZTM_ROUTE_WEIGHT`

#### Ensure zero HTTP interception in native apps
Native apps do not rely on HTTP interception, but the package may auto-enable HTTP interception on import unless you disable it. To force a fully-native runtime, set:

```bash
AZTM_DISABLE_AUTO_PATCH=1
```

before importing `aztm`.

## 5. Summary Checklist

1.  **Import** `aztm`.
2.  **Connect** via `aztm.connect()` or `aztm.connect_async()`.
3.  **Receive** by registering handlers with `session.on("topic", handler)`.
4.  **Send** using `session.send(...)` for events.
5.  **Call** using `session.request(...)` for RPC.
6.  **Disconnect** using `aztm.disconnect()` when done.

This native API provides a robust, protocol-agnostic way to build distributed systems without worrying about the underlying transport mechanics.
