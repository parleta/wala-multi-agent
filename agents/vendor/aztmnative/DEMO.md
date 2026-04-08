# AZTM Docker Demo - HTTP over XMPP Transport

This demo showcases the revolutionary AZTM (Agentic Zero Trust Mesh) technology that allows HTTP APIs to communicate without any network ports!

## 🎯 Key Innovation

**Traditional API:** Client → HTTP Port 8080 → Server  
**AZTM API:** Client → XMPP Messages → Server (NO PORTS!)

The server has **ZERO open HTTP ports** yet provides full REST API functionality!

## 🚀 Quick Start

### 1. Build the Docker Images

```bash
docker-compose -f docker-compose.demo.yml build
```

### 2. Start the Server

```bash
docker-compose -f docker-compose.demo.yml up aztm-server
```

Wait for the server to show:
```
✅ Server connected as aztmapi@sure.im
📡 Ready to receive HTTP requests via XMPP
🔒 No HTTP ports exposed - completely invisible to port scans!
```

### 3. Run the Client Demo (in another terminal)

```bash
docker-compose -f docker-compose.demo.yml run --rm aztm-client
```

## 📊 What You'll See

### Server Output:
```
🚀 AZTM Docker Server Demo
============================================================

📝 Configuration:
  Server JID: aztmapi@sure.im
  Transport: XMPP (no HTTP ports)
  APIs: /health, /orders/create, /status

✅ Server connected as aztmapi@sure.im/...
📡 Ready to receive HTTP requests via XMPP
🔒 No HTTP ports exposed - completely invisible to port scans!

📥 Received: GET /health from aztmclient@sure.im/...
📤 Sent response: 200 (86 bytes)

📥 Received: POST /orders/create from aztmclient@sure.im/...
📤 Sent response: 200 (143 bytes)

📥 Received: GET /status from aztmclient@sure.im/...
📤 Sent response: 200 (121 bytes)
```

### Client Output:
```
🚀 AZTM Docker Client Demo
============================================================

📝 Configuration:
  Client JID: aztmclient@sure.im
  Server JID: aztmapi@sure.im

✅ Client connected as aztmclient@sure.im/...

------------------------------------------------------------
📡 Making API Calls via XMPP (No HTTP ports!)
------------------------------------------------------------

### Health Check
Request: GET /health
📤 Sent GET /health to aztmapi@sure.im
✅ Response: {
  "status": "healthy",
  "service": "AZTM Docker Server",
  "timestamp": "2024-01-11T08:50:51.123456"
}

### Create Order
Request: POST /orders/create
Payload: {
  "sku": "DOCKER-123",
  "quantity": 10,
  "customer": "Docker Demo"
}
📤 Sent POST /orders/create to aztmapi@sure.im
✅ Response: {
  "order_id": "ORD-20240111085051",
  "status": "created",
  "message": "Order received via XMPP!",
  "details": {
    "sku": "DOCKER-123",
    "quantity": 10,
    "customer": "Docker Demo"
  }
}

### Get Status
Request: GET /status
📤 Sent GET /status to aztmapi@sure.im
✅ Response: {
  "server": "AZTM Demo",
  "transport": "XMPP",
  "http_ports": "NONE - All communication via XMPP!",
  "innovation": "Zero open ports, full API functionality"
}

============================================================
✨ Demo Complete!
Key Innovation: All HTTP traffic went through XMPP messaging!
============================================================
```

## 🔍 How It Works

1. **Client Application** makes normal HTTP API calls
2. **AZTM SDK** intercepts and serializes them to JSON
3. **XMPP Transport** sends messages to server's JID
4. **Server AZTM** receives XMPP messages (no HTTP listener!)
5. **FastAPI Routes** process requests normally
6. **Response** sent back via XMPP to client

## 🛡️ Security Benefits

- **Zero Attack Surface:** No open ports to scan or attack
- **NAT/Firewall Friendly:** Only outbound XMPP connections
- **End-to-End Encrypted:** TLS + optional JOSE/OMEMO
- **Identity-Based:** XMPP JIDs instead of IP addresses

## 🔧 Customization

### Use Your Own XMPP Server

Edit `docker-compose.demo.yml`:
```yaml
environment:
  - XMPP_USER=your-client@your-server.com
  - XMPP_PASSWORD=your-password
```

### Add More API Endpoints

Edit `docker/server_demo.py` to add your FastAPI routes:
```python
@app.post("/your/endpoint")
async def your_handler(data: dict):
    return {"result": "processed"}
```

## 📚 Architecture

```
┌─────────────┐     XMPP Messages      ┌─────────────┐
│   Client    │ ───────────────────────►│   Server    │
│  Container  │                         │  Container  │
│             │◄─────────────────────── │             │
│ No HTTP     │     aztmclient@         │ No Ports    │
│ Requests    │       sure.im           │   Open!     │
└─────────────┘                         └─────────────┘
        │                                      │
        └──────────── XMPP Server ────────────┘
                    (sure.im)
```

## 🚨 Important Notes

- Both containers connect to the public XMPP server `sure.im`
- No direct network connection between client and server containers
- Server container exposes **ZERO ports** yet provides full API functionality
- All communication is authenticated and encrypted via XMPP/TLS

## 🎮 Interactive Testing

### Option 1: Interactive Client (Send Custom Messages)

Build and run the interactive client that lets you send custom API calls:

```bash
# Build interactive client
docker build -f docker/Dockerfile.interactive -t aztm-interactive .

# Run server (Terminal 1)
docker run --rm --name aztm-server aztm-server

# Run interactive client (Terminal 2)
docker run -it --rm --name aztm-interactive aztm-interactive
```

In the interactive client, try:
```
> LIST                                    # Show available endpoints
> GET /health                            # Health check
> POST /orders/create {"sku":"ABC","qty":5}  # Create order
> GET /status                            # Server status
> POST /echo {"message":"Hello AZTM!"}  # Echo test
> QUIT                                   # Exit
```

### Option 2: Automated Demo

```bash
# Terminal 1: Start server
docker-compose -f docker-compose.demo.yml run --rm aztm-server

# Terminal 2: Run client demo
docker-compose -f docker-compose.demo.yml run --rm aztm-client
```

### Option 3: Multi-Computer Demo

Run server and client on **different computers** to prove no direct connection needed!
See [MULTI_COMPUTER_DEMO.md](MULTI_COMPUTER_DEMO.md) for detailed instructions.

## 🧹 Cleanup

```bash
docker-compose -f docker-compose.demo.yml down
docker-compose -f docker-compose.demo.yml rm -f
```

## 📖 Learn More

- [AZTM Specification](WARP.md)
- [Full Documentation](README.md)
- [Python Examples](examples/)

---

**This is the future of API communication:** Zero ports, full functionality, complete security!