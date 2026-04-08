# WARP.md - AZTM (Agentic Zero Trust Mesh) Development Guide

This file provides complete context and guidance for WARP (warp.dev) or any AI agent to develop the AZTM Python SDK. All necessary information is contained here so development can begin immediately after cloning this repository.

## Project Overview

**AZTM** is a Python SDK that transparently replaces HTTP transport with XMPP-based messaging while keeping existing client and server code unchanged. The only required changes are:
1. `import aztm`
2. `aztm.login(userid="...", password="...")`

### Key Innovation
- **Zero code change** beyond import and login
- HTTP requests are intercepted and sent as XMPP messages to service JIDs
- FastAPI servers automatically receive and process XMPP messages as HTTP requests
- No inbound ports required on API servers (NAT/firewall friendly)

## Complete PRD (Product Requirements Document)

### Executive Summary
AZTM allows existing Python HTTP clients and FastAPI servers to communicate over XMPP users instead of IP addresses. Both sides log in to a Jabber server. Client HTTP requests are intercepted and serialized into XMPP messages addressed to the service username. The server auto hooks FastAPI and dispatches messages to routes.

### Technical Architecture

```
Client App                    XMPP Plane                    Server App
┌─────────────┐              ┌─────────┐                  ┌─────────────┐
│ HTTP Client │──────────────│ XMPP    │──────────────────│ FastAPI App │
│   Code      │              │ Server  │                  │             │
│             │              │(Openfire)│                 │             │
│ aztm.login()│──[intercept]─│         │─[auto-hook]──────│aztm.login() │
└─────────────┘              └─────────┘                  └─────────────┘
```

### Core Design Principles

1. **Address Mapping**
   - URL host → XMPP JID (e.g., `https://orders.api/...` → `orders.api@xmpp.example`)
   - HTTP path → XMPP subject (e.g., `/orders/create` → `orders/create`)
   - Domain derived from caller's JID

2. **Wire Protocol**
   - XMPP message stanzas with JSON body
   - `_aztm` control block with HTTP metadata
   - Application payload preserved as-is
   - Correlation via message ID + UUID

3. **Payload Classes**
   - **Small** (<128KB): Inline in message body
   - **Medium** (<5MB): Chunked streaming with reassembly
   - **Large** (>5MB): HTTP upload slots, no inbound ports needed

4. **Security Model**
   - TLS to XMPP server
   - SASL authentication
   - Optional JOSE signing/encryption
   - Optional OMEMO for E2E encryption
   - Bearer tokens preserved in headers

## Development Task List

The following tasks should be added to the TODO list when starting development. They are organized in dependency order.

### Phase 1: Foundation (Tasks 1-3)

#### Task 1: Project Setup and Infrastructure
**Description**: Initialize the Python package structure and development environment

**Detailed Steps**:
1. Create package structure:
   ```
   aztm/
   ├── __init__.py
   ├── core/
   │   ├── __init__.py
   │   ├── xmpp_client.py
   │   ├── auth.py
   │   ├── config.py
   │   └── mapping.py
   ├── interceptors/
   │   ├── __init__.py
   │   ├── requests_hook.py
   │   └── httpx_hook.py
   ├── server/
   │   ├── __init__.py
   │   ├── fastapi_hook.py
   │   ├── request_handler.py
   │   └── response_publisher.py
   ├── protocol/
   │   ├── __init__.py
   │   ├── message.py
   │   ├── payload.py
   │   └── errors.py
   ├── security/
   │   ├── __init__.py
   │   ├── tls.py
   │   ├── jose.py
   │   └── omemo.py
   ├── observability/
   │   ├── __init__.py
   │   ├── metrics.py
   │   ├── logging.py
   │   └── tracing.py
   └── tools/
       ├── __init__.py
       └── cli.py
   ```

2. Create `pyproject.toml`:
   ```toml
   [build-system]
   requires = ["setuptools>=61.0", "wheel"]
   build-backend = "setuptools.build_meta"

   [project]
   name = "aztm"
   version = "0.1.0"
   description = "Agentic Zero Trust Mesh - HTTP over XMPP transport"
   authors = [{name = "Elad Rave", email = "eladrave@example.com"}]
   requires-python = ">=3.9"
   dependencies = [
       "slixmpp>=1.8.0",
       "requests>=2.28.0",
       "httpx>=0.24.0",
       "fastapi>=0.100.0",
       "cryptography>=41.0.0",
       "python-jose[cryptography]>=3.3.0",
       "prometheus-client>=0.17.0",
       "opentelemetry-api>=1.20.0",
       "opentelemetry-sdk>=1.20.0",
       "pydantic>=2.0.0",
       "click>=8.1.0",
   ]

   [project.optional-dependencies]
   dev = [
       "pytest>=7.4.0",
       "pytest-asyncio>=0.21.0",
       "pytest-cov>=4.1.0",
       "black>=23.0.0",
       "mypy>=1.5.0",
       "flake8>=6.1.0",
       "pre-commit>=3.4.0",
       "tox>=4.11.0",
   ]
   omemo = [
       "python-omemo>=0.1.0",
   ]
   ```

3. Create Docker environment:
   ```dockerfile
   # Dockerfile
   FROM python:3.11-slim
   WORKDIR /app
   COPY . .
   RUN pip install -e .[dev]
   CMD ["pytest"]
   ```

   ```yaml
   # docker-compose.yml
   version: '3.8'
   services:
     openfire:
       image: quantumobject/docker-openfire:latest
       ports:
         - "5222:5222"  # XMPP C2S
         - "9090:9090"  # Admin console
       environment:
         - DOMAIN=xmpp.example
       volumes:
         - openfire_data:/var/lib/openfire
     
     aztm-test:
       build: .
       depends_on:
         - openfire
       environment:
         - XMPP_HOST=openfire
         - XMPP_PORT=5222
       volumes:
         - .:/app
       command: pytest -v

   volumes:
     openfire_data:
   ```

#### Task 2: Core XMPP Session Management
**Description**: Implement the XMPP client wrapper and authentication

**File: `aztm/core/xmpp_client.py`**
```python
import asyncio
from typing import Optional, Dict, Any, Callable
import slixmpp
from slixmpp.exceptions import IqError, IqTimeout

class XMPPClient(slixmpp.ClientXMPP):
    def __init__(self, jid: str, password: str):
        super().__init__(jid, password)
        self.connected = asyncio.Event()
        self.add_event_handler("session_start", self.on_session_start)
        self.add_event_handler("disconnected", self.on_disconnected)
        self.add_event_handler("message", self.on_message)
        self._message_handlers: Dict[str, Callable] = {}
        
    async def on_session_start(self, event):
        self.send_presence()
        await self.get_roster()
        self.connected.set()
        
    async def on_disconnected(self, event):
        self.connected.clear()
        # Implement exponential backoff reconnection
        await self._reconnect_with_backoff()
        
    async def on_message(self, msg):
        # Route to registered handlers
        if msg['subject'] in self._message_handlers:
            await self._message_handlers[msg['subject']](msg)
            
    def register_handler(self, subject: str, handler: Callable):
        self._message_handlers[subject] = handler
```

**File: `aztm/core/auth.py`**
```python
from typing import Optional, Dict, Any
from .xmpp_client import XMPPClient
from .config import Config

_client: Optional[XMPPClient] = None

def login(userid: str, password: str, **kwargs) -> None:
    """Main entry point for AZTM initialization"""
    global _client
    
    config = Config.from_env()
    config.update(kwargs)
    
    _client = XMPPClient(userid, password)
    _client.connect()
    _client.process(forever=False)
    
    # Patch HTTP libraries
    from ..interceptors import patch_all
    patch_all(_client, config)
    
    # Auto-detect and hook FastAPI
    from ..server import auto_hook_fastapi
    auto_hook_fastapi(_client, config)
    
def get_client() -> XMPPClient:
    if not _client:
        raise RuntimeError("Call aztm.login() first")
    return _client
```

#### Task 3: HTTP Request Interception Layer
**Description**: Intercept HTTP requests and convert to XMPP messages

**File: `aztm/interceptors/requests_hook.py`**
```python
import json
import uuid
from typing import Any, Dict
from urllib.parse import urlparse, unquote
import requests

original_request = requests.Session.request

def patched_request(self, method, url, **kwargs):
    """Intercept requests and route through XMPP"""
    from ..core.auth import get_client
    from ..protocol.message import create_request_envelope
    
    client = get_client()
    parsed = urlparse(url)
    
    # Map host to JID
    to_jid = f"{parsed.hostname}@{client.boundjid.domain}"
    
    # Create subject from path
    path = unquote(parsed.path)
    subject = path.lstrip('/') if path != '/' else 'root'
    
    # Build message envelope
    envelope = create_request_envelope(
        method=method,
        path=parsed.path,
        query=parsed.query,
        headers=dict(kwargs.get('headers', {})),
        body=kwargs.get('json') or kwargs.get('data'),
    )
    
    # Send via XMPP and wait for response
    response = client.send_http_over_xmpp(to_jid, subject, envelope)
    
    # Convert back to requests.Response
    return convert_to_requests_response(response)

def patch_requests():
    requests.Session.request = patched_request
```

### Phase 2: Server Integration (Tasks 4-5)

#### Task 4: FastAPI Server Integration
**Description**: Auto-detect FastAPI and handle incoming XMPP messages

**File: `aztm/server/fastapi_hook.py`**
```python
import sys
from typing import Optional
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response

def find_fastapi_app() -> Optional[FastAPI]:
    """Auto-detect FastAPI app in current process"""
    for obj in sys.modules.values():
        if hasattr(obj, '__dict__'):
            for item in obj.__dict__.values():
                if isinstance(item, FastAPI):
                    return item
    return None

def auto_hook_fastapi(client, config):
    """Automatically hook into FastAPI if detected"""
    app = find_fastapi_app()
    if not app:
        return
    
    # Register XMPP message handler
    async def handle_xmpp_request(msg):
        # Parse XMPP message to HTTP request
        envelope = json.loads(msg['body'])
        aztm_meta = envelope['_aztm']
        
        # Create mock ASGI scope
        scope = {
            'type': 'http',
            'method': aztm_meta['method'],
            'path': aztm_meta['path'],
            'query_string': aztm_meta.get('query', '').encode(),
            'headers': [(k.encode(), v.encode()) 
                       for k, v in aztm_meta.get('headers', {}).items()],
        }
        
        # Create request and get response
        request = Request(scope)
        response = await app(request)
        
        # Send response back via XMPP
        reply_envelope = create_response_envelope(
            status=response.status_code,
            headers=dict(response.headers),
            body=response.body,
            corr=aztm_meta['corr']
        )
        
        client.send_message(
            mto=msg['from'],
            mbody=json.dumps(reply_envelope),
            msubject=f"{msg['subject']}:result"
        )
    
    # Register handler for all messages to this JID
    client.register_handler('*', handle_xmpp_request)
```

#### Task 5: Wire Protocol Implementation
**Description**: Define the JSON message format and payload handling

**File: `aztm/protocol/message.py`**
```python
import json
import uuid
import time
from typing import Dict, Any, Optional

def create_request_envelope(
    method: str,
    path: str,
    query: str = "",
    headers: Dict[str, str] = None,
    body: Any = None,
) -> str:
    """Create AZTM request envelope"""
    envelope = {
        "_aztm": {
            "ns": "urn:aztm:v1",
            "method": method,
            "path": path,
            "query": query,
            "headers": headers or {},
            "corr": str(uuid.uuid4()),
            "ts": int(time.time()),
        },
        "payload": body
    }
    return json.dumps(envelope)

def create_response_envelope(
    status: int,
    headers: Dict[str, str] = None,
    body: Any = None,
    corr: str = None,
) -> str:
    """Create AZTM response envelope"""
    envelope = {
        "_aztm": {
            "status": status,
            "headers": headers or {},
            "corr": corr,
        },
        "payload": body
    }
    return json.dumps(envelope)
```

**File: `aztm/protocol/payload.py`**
```python
import base64
import hashlib
from typing import Any, Optional, List
from ..core.config import Config

class PayloadHandler:
    def __init__(self, config: Config):
        self.inline_limit = config.inline_limit_kb * 1024
        self.stream_limit = config.stream_limit_mb * 1024 * 1024
        
    def should_inline(self, data: bytes) -> bool:
        return len(data) <= self.inline_limit
    
    def should_stream(self, data: bytes) -> bool:
        return self.inline_limit < len(data) <= self.stream_limit
    
    def should_use_slot(self, data: bytes) -> bool:
        return len(data) > self.stream_limit

class SmallPayloadHandler(PayloadHandler):
    """Handle payloads < 128KB inline"""
    def encode(self, data: bytes) -> Dict[str, Any]:
        return {
            "type": "inline",
            "data": base64.b64encode(data).decode('utf-8'),
            "encoding": "base64"
        }
    
    def decode(self, envelope: Dict[str, Any]) -> bytes:
        return base64.b64decode(envelope["data"])

class MediumPayloadHandler(PayloadHandler):
    """Handle payloads < 5MB via chunking"""
    def chunk_data(self, data: bytes, chunk_size: int = 64*1024) -> List[bytes]:
        return [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
    
    def create_chunks(self, data: bytes, stream_id: str) -> List[Dict[str, Any]]:
        chunks = self.chunk_data(data)
        return [
            {
                "stream": {
                    "id": stream_id,
                    "seq": i,
                    "eof": i == len(chunks) - 1,
                    "sha256": hashlib.sha256(chunk).hexdigest()
                },
                "data": base64.b64encode(chunk).decode('utf-8')
            }
            for i, chunk in enumerate(chunks)
        ]

class LargePayloadHandler(PayloadHandler):
    """Handle payloads > 5MB via upload slots"""
    async def request_upload_slot(self, size: int) -> Dict[str, str]:
        # Request upload slot from XMPP server
        # Returns PUT URL and metadata
        pass
    
    async def upload_to_slot(self, url: str, data: bytes) -> str:
        # Upload data via HTTPS PUT
        # Return object key
        pass
```

### Phase 3: Security and Advanced Features (Tasks 6-8)

#### Task 6: Security Layer Implementation
**Description**: Add TLS, JOSE, and OMEMO support

**File: `aztm/security/jose.py`**
```python
from jose import jwt, jws
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from typing import Dict, Any, Optional

class JOSEHandler:
    def __init__(self):
        self.signing_key = None
        self.encryption_key = None
        
    def generate_keys(self):
        """Generate RSA key pair for signing and encryption"""
        self.signing_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
        self.encryption_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048
        )
    
    def sign_payload(self, payload: Dict[str, Any]) -> str:
        """Sign payload with JWS"""
        return jws.sign(payload, self.signing_key, algorithm='RS256')
    
    def verify_signature(self, token: str, public_key) -> Dict[str, Any]:
        """Verify JWS signature"""
        return jws.verify(token, public_key, algorithms=['RS256'])
    
    def encrypt_payload(self, payload: Dict[str, Any], public_key) -> str:
        """Encrypt payload with JWE"""
        return jwt.encode(payload, public_key, algorithm='RSA-OAEP')
    
    def decrypt_payload(self, token: str) -> Dict[str, Any]:
        """Decrypt JWE payload"""
        return jwt.decode(token, self.encryption_key, algorithms=['RSA-OAEP'])
```

#### Task 7: Observability and Monitoring
**Description**: Add metrics, logging, and distributed tracing

**File: `aztm/observability/metrics.py`**
```python
from prometheus_client import Counter, Histogram, Gauge
import time

# Define metrics
request_counter = Counter(
    'aztm_requests_total',
    'Total AZTM requests',
    ['method', 'status']
)

request_duration = Histogram(
    'aztm_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'transport']
)

active_connections = Gauge(
    'aztm_active_connections',
    'Number of active XMPP connections'
)

payload_size = Histogram(
    'aztm_payload_bytes',
    'Payload size in bytes',
    ['direction', 'transfer_mode'],
    buckets=[1024, 10240, 102400, 1048576, 5242880, 10485760]
)

class MetricsCollector:
    def record_request(self, method: str, status: int, duration: float):
        request_counter.labels(method=method, status=status).inc()
        request_duration.labels(method=method, transport='xmpp').observe(duration)
    
    def record_payload(self, direction: str, mode: str, size: int):
        payload_size.labels(direction=direction, transfer_mode=mode).observe(size)
```

#### Task 8: Testing Suite Development
**Description**: Create comprehensive test coverage

**Test Structure**:
```
tests/
├── unit/
│   ├── test_mapping.py
│   ├── test_message_format.py
│   ├── test_payload_handlers.py
│   └── test_interceptors.py
├── integration/
│   ├── test_client_server.py
│   ├── test_fastapi_hook.py
│   ├── test_upload_slots.py
│   └── test_streaming.py
├── performance/
│   ├── test_throughput.py
│   ├── test_latency.py
│   └── test_concurrent.py
└── security/
    ├── test_jose.py
    ├── test_omemo.py
    └── test_tls.py
```

**Example test: `tests/unit/test_mapping.py`**
```python
import pytest
from aztm.core.mapping import url_to_jid, path_to_subject

def test_url_to_jid():
    assert url_to_jid("https://orders.api/test", "user@xmpp.example") == "orders.api@xmpp.example"
    assert url_to_jid("http://service.local/api", "client@domain.com") == "service.local@domain.com"

def test_path_to_subject():
    assert path_to_subject("/orders/create") == "orders/create"
    assert path_to_subject("/users/%7Bid%7D") == "users/{id}"
    assert path_to_subject("/") == "root"
    assert path_to_subject("/api/v1/items?page=1") == "api/v1/items"

def test_special_characters():
    assert path_to_subject("/hello%20world") == "hello world"
    assert path_to_subject("/path%2Fwith%2Fslash") == "path/with/slash"
```

### Phase 4: Documentation and Examples (Tasks 9-10)

#### Task 9: Documentation and Examples
**Description**: Create user guides and example applications

**Example Client (`examples/client_example.py`)**:
```python
import aztm
import requests

# Login to XMPP
aztm.login(userid="client@xmpp.example", password="secret123")

# Make HTTP requests as normal - they go over XMPP!
response = requests.post(
    "https://orders.api/orders/create",
    json={"sku": "ABC123", "quantity": 5}
)

print(f"Status: {response.status_code}")
print(f"Order ID: {response.json()['order_id']}")
```

**Example Server (`examples/server_example.py`)**:
```python
from fastapi import FastAPI
import aztm

app = FastAPI()

# Login to XMPP as a service
aztm.login(userid="orders.api@xmpp.example", password="secret456")

@app.post("/orders/create")
async def create_order(order: dict):
    # This endpoint receives requests via XMPP!
    return {"order_id": 12345, "status": "created"}

# Run with: uvicorn server_example:app
```

#### Task 10: CI/CD Pipeline Setup
**Description**: Set up automated testing and deployment

**File: `.github/workflows/ci.yml`**
```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.9", "3.10", "3.11", "3.12"]
    
    services:
      openfire:
        image: quantumobject/docker-openfire:latest
        ports:
          - 5222:5222
        options: >-
          --health-cmd "nc -z localhost 5222"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e .[dev]
      
      - name: Run tests
        run: |
          pytest --cov=aztm --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
```

### Phase 5: Advanced Features (Tasks 11-12)

#### Task 11: Advanced Features and Optimization
**Description**: Add connection pooling, caching, and resilience

**Key implementations**:
- Connection multiplexing for multiple JIDs
- Response caching with TTL
- Circuit breaker for failed services
- Request retry with exponential backoff
- Health check endpoints

#### Task 12: Final Integration and Polish
**Description**: Complete testing, optimization, and release preparation

**Checklist**:
- [ ] All tests passing with >80% coverage
- [ ] Performance benchmarks completed
- [ ] Security audit passed
- [ ] Documentation complete
- [ ] Examples working
- [ ] PyPI package ready
- [ ] Docker images built
- [ ] Release notes prepared

## Configuration Reference

All configuration via environment variables with `AZTM_` prefix:

```bash
# Size thresholds
AZTM_INLINE_LIMIT_KB=128              # Max inline JSON size
AZTM_STREAM_LIMIT_MB=5                # Above this, use upload slots

# Transfer modes
AZTM_LARGE_TRANSFER_MODE=auto         # auto|slot|inband
AZTM_LARGE_TRANSFER_FALLBACK=inband   # Fallback if primary unavailable

# Features
AZTM_FEATURE_UPLOAD_SLOTS=1           # Enable slot-based transfer
AZTM_FEATURE_INBAND_STREAM=1          # Enable streaming fallback

# Flow control
AZTM_STREAM_WINDOW=8                  # In-flight chunks
AZTM_CHECKSUM_ALG=sha256             # Integrity algorithm

# Behavior
AZTM_EMPTY_SUBJECT=root              # Subject when path is "/"
```

## Testing Strategy

### Critical Testing Rules for AZTM

**⚠️ IMPORTANT: A single process can only login as either CLIENT or SERVER, never both!**

This is a fundamental limitation - one process = one XMPP connection = one identity. Always use separate processes for client and server testing.

### Correct Testing Procedure

#### Local Testing (Recommended)
1. **Start server in Docker**:
   ```bash
   docker build -t aztm-server -f docker/Dockerfile.server .
   docker run -d --rm --name aztm-server aztm-server
   ```

2. **Run client test locally**:
   ```bash
   source venv/bin/activate
   python test_e2e_complete.py
   ```

3. **Cleanup**:
   ```bash
   docker stop aztm-server
   ```

#### Use Existing Test Files - DO NOT CREATE NEW ONES:
- `test_e2e_complete.py` - Full end-to-end test
- `test_simple_connectivity.py` - Client connectivity only
- `test_server_login.py` - Server login only
- `docker/client_demo.py` - Docker client demo
- `docker/server_demo.py` - Docker server demo
- `tests/regression/test_*.py` - Full regression suite with ProcessManager

### Regression Testing Infrastructure
The project includes comprehensive regression testing with support for:
- **Unit tests** with mocked components (no Docker required)
- **Integration tests** with real XMPP server (Docker-based)
- **Performance tests** with baseline tracking
- **Subprocess management** for testing client-server communication
- **CI/CD integration** via GitHub Actions

### Local Development Testing

#### Quick Start with Test Runner Script
```bash
# Run all tests (starts Docker automatically)
./scripts/run_regression_tests.sh

# Run only unit tests (no Docker needed)
./scripts/run_regression_tests.sh -t unit

# Run integration tests with debug output
./scripts/run_regression_tests.sh -t integration -d

# Run tests matching a pattern
./scripts/run_regression_tests.sh -k "connectivity"

# Keep Docker running after tests for debugging
./scripts/run_regression_tests.sh --keep

# Clean Docker containers and run fresh
./scripts/run_regression_tests.sh -c
```

#### Manual Testing
```bash
# Start Openfire in Docker
docker-compose up -d openfire

# Wait for Openfire to start (health check included)
docker-compose ps  # Check status

# Run unit tests
pytest tests/unit/ tests/regression/test_*connectivity.py::TestMockedConnectivity -v

# Run integration tests
pytest tests/regression -m integration -v

# Run with coverage
pytest --cov=aztm --cov-report=html --cov-report=term

# Run performance tests
pytest tests/regression/test_performance.py -m performance --benchmark-only
```

### Clean Docker Testing
```bash
# Using docker-compose (recommended)
docker-compose run --rm aztm-test pytest -v

# Build and run manually
docker build -t aztm-test .

# Run tests in clean environment
docker run --rm \
  --network aztm_default \
  -e XMPP_HOST=openfire \
  -e AZTM_LOG_LEVEL=DEBUG \
  aztm-test pytest -v tests/regression/

# Interactive debugging with exec
docker-compose up -d openfire aztm-test
docker exec -it aztm-test /bin/bash
# Inside container:
python -c "import aztm; aztm.login('test@test.aztm', 'test')"
pytest tests/regression/test_basic_connectivity.py -v -s
```

### Regression Test Structure
```
tests/regression/
├── conftest.py                    # Pytest fixtures and configuration
├── utils/
│   └── process_manager.py         # Subprocess management for client/server
├── test_basic_connectivity.py     # Connection establishment tests
├── test_http_transport.py         # HTTP method and header tests
├── test_payload_sizes.py          # Payload boundary tests
├── test_error_handling.py         # Error condition tests
├── test_performance.py            # Performance benchmarks
└── test_mocked_transport.py       # Mock-based unit tests
```

### Test Types and Markers
- `@pytest.mark.integration` - Requires Docker/XMPP server
- `@pytest.mark.mock` - Uses mocked components (fast)
- `@pytest.mark.performance` - Performance regression tests
- `@pytest.mark.slow` - Long-running tests

### CI/CD Testing
GitHub Actions workflow (`.github/workflows/regression-tests.yml`):
- Matrix testing: Python 3.9, 3.10, 3.11, 3.12
- Parallel unit and integration test execution
- Service containers for Openfire XMPP server
- Performance baseline tracking
- Test result reporting with artifacts
- Coverage reporting to Codecov

### Running Specific Test Scenarios
```bash
# Test client-server message exchange
pytest tests/regression/test_basic_connectivity.py::TestBasicConnectivity::test_client_server_message_exchange -v

# Test with specific XMPP server
AZTM_HOST=xmpp.example.com AZTM_PORT=5222 pytest tests/regression/

# Test with custom timeout
pytest tests/regression/ --timeout=60

# Generate JUnit XML for CI
pytest tests/regression/ --junit-xml=results.xml
```

## DevOps Requirements

### Openfire Setup (AWS)
1. **Install Openfire 4.7.0+**
   - Port 5222: XMPP client-to-server
   - Port 7443: HTTPS upload slots
   - Port 9090: Admin console (internal only)

2. **Create Service Accounts**
   ```
   orders.api@xmpp.example
   inventory.api@xmpp.example
   client1@xmpp.example
   ```

3. **Enable Upload Slots**
   - Install HTTP File Upload plugin
   - Configure max size > 5MB
   - Set retention policy

4. **TLS Configuration**
   - Valid certificate for domain
   - Enforce TLS 1.2+

## Security Checklist

1. ✅ TLS everywhere
2. ✅ SASL authentication required
3. ✅ Inject `X-AZTM-From-JID` header
4. ✅ Validate bearer tokens
5. ✅ Per-route ACLs
6. ✅ Optional JOSE signing
7. ✅ Server-only GET for uploads
8. ✅ Checksum validation
9. ✅ Key rotation
10. ✅ Audit logging

## Common Development Commands

### Setup
```bash
# Clone and setup
git clone https://github.com/eladrave/aztm
cd aztm
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -e .[dev]

# Start dependencies
docker-compose up -d

# Run tests
pytest

# Format code
black aztm tests
flake8 aztm tests
mypy aztm
```

### Development Workflow
```bash
# Create feature branch
git checkout -b feature/your-feature

# Make changes and test
pytest tests/unit/test_your_feature.py

# Run full test suite
pytest

# Commit and push
git add .
git commit -m "feat: add your feature"
git push origin feature/your-feature
```

## Implementation Notes

### Critical Design Decisions
1. **No hard-coded ports** - API servers only make outbound connections
2. **Transparent interception** - No changes to application code
3. **Protocol agnostic** - Preserve HTTP semantics completely
4. **Dynamic discovery** - Services discovered via XMPP presence
5. **Backward compatible** - Can fallback to HTTP if XMPP unavailable

### Performance Targets
- Latency overhead: <10ms for small payloads
- Throughput: >100MB/s for large transfers
- Concurrent connections: >1000 per process
- Memory footprint: <100MB base

### Known Limitations
1. WebSocket upgrade not supported (use XMPP directly)
2. HTTP/2 server push not supported
3. Streaming responses use chunked transfer
4. Maximum message size limited by XMPP server

## Getting Help

### Resources
- PRD: See complete PRD section above
- API Docs: Will be at `/docs` when running
- Examples: See `examples/` directory
- Tests: See `tests/` for usage patterns

### Debugging Tips
1. Enable debug logging: `AZTM_LOG_LEVEL=DEBUG`
2. Check XMPP connection: `aztm.get_client().connected.is_set()`
3. Monitor metrics: `http://localhost:9090/metrics`
4. Trace requests: Look for correlation ID in logs
5. Test connectivity: Use `aztm.tools.cli` for diagnostics

## Next Steps for Development

When you're ready to start development:

1. **Read the TODO list above** - Tasks are in dependency order
2. **Set up the environment** - Follow Task 1 completely
3. **Implement core features** - Tasks 2-5 are the minimum viable product
4. **Add security** - Task 6 is critical before any production use
5. **Test thoroughly** - Task 8 includes all test categories
6. **Document as you go** - Update this file with any changes

The project is designed to be developed incrementally. Each task builds on the previous ones, and you can have a working prototype after completing Tasks 1-5.

## Version History

- v0.4 - Current PRD version with complete specifications
- v0.1 - Initial implementation target

## License

MIT License - See LICENSE file for details

## Author

Elad Rave - https://github.com/eladrave

---

*This WARP.md file contains all necessary information to develop AZTM. No external documentation is required.*