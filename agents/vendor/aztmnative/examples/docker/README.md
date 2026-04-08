# AZTM Docker Examples

This directory contains a complete Docker-based demonstration of AZTM (Agentic Zero Trust Mesh) showing how HTTP clients and servers can communicate via XMPP without any direct network connection.

## 🚀 Quick Start

```bash
# Start all containers
docker-compose up --build

# Watch the logs
docker-compose logs -f

# Stop everything
docker-compose down
```

## 📦 What's Included

### Containers

1. **XMPP Server** (`aztm-xmpp`)
   - ejabberd XMPP server
   - Pre-configured with test accounts
   - Domain: `sure.im`
   - Port 5222 for XMPP
   - Port 5280 for HTTP uploads

2. **AZTM Server** (`aztm-server`)
   - FastAPI application
   - Receives HTTP requests via XMPP
   - No inbound ports required!
   - JID: `aztmserver@sure.im`

3. **AZTM Client** (`aztm-client`)
   - Python client application
   - Sends HTTP requests via XMPP
   - No direct connection to server
   - JID: `aztmclient@sure.im`

## 🔐 Test Credentials

As requested, the demo uses these credentials:

- **Client**: `aztmclient@sure.im` / password: `12345678`
- **Server**: `aztmserver@sure.im` / password: `12345678`

## 🏗️ Architecture

```
┌─────────────┐     XMPP      ┌─────────────┐     XMPP      ┌─────────────┐
│ AZTM Client │──────────────→│ XMPP Server │←──────────────│ AZTM Server │
│             │                │  (ejabberd) │                │  (FastAPI)  │
│ HTTP Client │                │  sure.im    │                │   No Ports! │
└─────────────┘                └─────────────┘                └─────────────┘

- Client makes requests.post("https://aztmserver.api/orders/create")
- AZTM intercepts and sends as XMPP message to aztmserver@sure.im
- Server receives XMPP message and routes to FastAPI
- Response sent back via XMPP
```

## 🔥 Key Features Demonstrated

### Zero Code Change
The demo shows how existing HTTP code works unchanged:
```python
# Client code - looks like normal HTTP!
response = requests.post(
    "https://aztmserver.api/orders/create",
    json={"sku": "LAPTOP-001", "quantity": 2}
)
```

### No Inbound Ports
- Server has NO exposed ports
- Only outbound XMPP connection
- NAT/firewall friendly
- True zero-trust networking

### Security Features
- TLS encryption to XMPP server
- JOSE signing/encryption support
- Message correlation and validation
- No direct network path between client and server

## 📝 API Endpoints

The demo server provides these endpoints:

- `GET /` - Service info
- `GET /health` - Health check
- `POST /orders/create` - Create order
- `GET /orders/{order_id}` - Get order
- `GET /orders` - List all orders
- `GET /demo/echo` - Echo test
- `GET /demo/secure` - Security demo

## 🎯 Demo Flow

The client runs a continuous demo that:

1. **Basic Requests** - Tests root, health, echo endpoints
2. **Create Orders** - Posts multiple orders
3. **Retrieve Orders** - Gets individual and all orders
4. **Security Demo** - Tests JOSE signing/encryption

Each iteration shows:
- All requests sent via XMPP
- No direct server connection
- Full HTTP semantics preserved

## 🛠️ Configuration

### Environment Variables

Both client and server support:

```bash
AZTM_XMPP_HOST=xmpp         # XMPP server host
AZTM_XMPP_PORT=5222          # XMPP port
AZTM_XMPP_DOMAIN=sure.im     # XMPP domain
AZTM_JID=user@sure.im        # XMPP JID
AZTM_PASSWORD=password       # XMPP password
AZTM_LOG_LEVEL=DEBUG         # Logging level
AZTM_FEATURE_JOSE=1          # Enable JOSE
AZTM_FEATURE_TLS=1           # Enable TLS
```

## 📊 Monitoring

Watch the containers communicate:

```bash
# All logs
docker-compose logs -f

# Just client
docker-compose logs -f aztm-client

# Just server
docker-compose logs -f aztm-server

# XMPP server
docker-compose logs -f xmpp
```

## 🧪 Testing Individual Components

### Test Server Only
```bash
docker-compose up xmpp aztm-server
# Server will wait for XMPP requests
```

### Test Client Only
```bash
docker-compose up xmpp aztm-client
# Client will attempt to connect to server JID
```

### Manual Testing
```bash
# Exec into client container
docker exec -it aztm-client bash

# Run Python and test
python
>>> import aztm
>>> import requests
>>> aztm.login(userid="aztmclient@sure.im", password="12345678")
>>> response = requests.get("https://aztmserver.api/health")
>>> print(response.json())
```

## 🚨 Troubleshooting

### Containers not starting?
```bash
# Check XMPP server health
docker-compose ps
docker-compose logs xmpp

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

### Connection issues?
- Ensure XMPP server is healthy before starting client/server
- Check credentials match in docker-compose.yml
- Verify network `aztm-network` exists

### Not seeing requests?
- Check `AZTM_SERVER_JID` in client matches server's JID
- Verify both containers show "XMPP connected"
- Look for correlation IDs in logs

## 📚 Learn More

This demo shows AZTM's core capability: **HTTP over XMPP transport with zero code changes**.

Key takeaways:
- ✅ No server ports needed
- ✅ Works through NAT/firewalls
- ✅ Existing HTTP code unchanged
- ✅ Full security features
- ✅ Production-ready architecture

For more details, see the main [AZTM documentation](../../README.md).

## 🎉 Success Indicators

You'll know it's working when you see:

**Client logs:**
```
✅ AZTM client initialized successfully!
✅ Order created: abc123
All HTTP requests were sent via XMPP transport
```

**Server logs:**
```
✅ AZTM server initialized successfully!
Server is now receiving HTTP requests via XMPP
Created order: abc123 for 2x LAPTOP-001
```

No direct network connection exists between client and server - all communication flows through XMPP!