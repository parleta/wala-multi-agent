# Issue: FastAPI Handler Registration Not Working

## Problem
The FastAPI message handler isn't being registered properly with the XMPP client when the server starts. Messages sent to the server are not being received by the FastAPI hook.

## Root Cause
The XMPP event loop runs in a background thread (started in `auth.py`), but the FastAPI hook is called from the main thread after the loop has started. The `client.add_event_handler("message", handle_xmpp_request)` call in `hook_fastapi()` doesn't take effect because:

1. The event loop is already running in a background thread
2. Event handler registration happens after the loop has started
3. There's no mechanism to add handlers to a running event loop from another thread

## Current Code Flow
1. `aztm.login()` is called
2. XMPP client connects and starts event loop in background thread
3. `hook_fastapi()` is called from main thread
4. `add_event_handler()` is called but doesn't affect the running loop
5. Messages arrive but no handler processes them

## Solution Options

### Option 1: Register handlers before loop starts
Move the FastAPI hook call to happen before the background thread starts in `auth.py`.

### Option 2: Thread-safe handler registration
Implement a thread-safe way to add handlers to the running event loop.

### Option 3: Run everything in main thread
Don't use a background thread for the XMPP event loop.

## Test Case
```python
# This should work but currently doesn't:
aztm.login(userid="server@xmpp.example", password="pass", server_mode=True)
from aztm.server.fastapi_hook import hook_fastapi
hook_fastapi(app, get_client(), {})
# FastAPI handler never receives messages!
```

## Workaround
Currently none - the server can connect to XMPP but can't receive messages through the FastAPI hook.