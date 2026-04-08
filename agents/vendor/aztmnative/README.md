# AZTM - Agentic Zero Trust Mesh

[![CI](https://github.com/eladrave/aztm/actions/workflows/ci.yml/badge.svg)](https://github.com/eladrave/aztm/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/eladrave/aztm/branch/Agentic/graph/badge.svg)](https://codecov.io/gh/eladrave/aztm)
[![Python Version](https://img.shields.io/pypi/pyversions/aztm)](https://pypi.org/project/aztm/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**AZTM** transparently replaces HTTP transport with a secure messaging plane while keeping existing client and server code unchanged. Simply import and login - no other code changes required!

## Key Features

- 🚀 **Zero Code Changes** - Just add `import aztm` and `aztm.login()`
- 🔒 **NAT/Firewall Friendly** - No inbound ports required on API servers
- 🌐 **Protocol Transparent** - Preserves full HTTP semantics
- 🔄 **Auto-Detection** - Automatically hooks FastAPI applications
- 📦 **All Payload Sizes** - Handles small, medium, and large transfers
- 🔐 **Secure** - TLS, SASL auth, optional JOSE/OMEMO encryption

## Quick Start

## Installation

```bash
# Install from GitHub (currently)
pip install git+https://github.com/eladrave/aztm.git@Agentic

# Will be available on PyPI soon:
# pip install aztm
```

### Client Example

```python
import aztm
import requests

# Login to secure transport - this patches HTTP libraries automatically
aztm.login(userid="client@example.com", password="secret123")

# All HTTP requests now go through the secure transport!
response = requests.post(
    "https://orders.api/orders/create",
    json={"sku": "ABC123", "quantity": 5}
)

print(f"Order ID: {response.json()['order_id']}")
```

### Server Example

```python
from fastapi import FastAPI
import aztm

app = FastAPI()

# Login to secure transport - this auto-hooks FastAPI
aztm.login(userid="orders.api@example.com", password="secret456")

@app.post("/orders/create")
async def create_order(order: dict):
    # This endpoint receives requests via AZTM (no inbound ports required)
    return {"order_id": 12345, "status": "created"}

# No need to expose ports - only an outbound secure transport connection needed!
```

## How It Works

1. **URL → Identity Mapping**: `https://orders.api/path` → `orders.api@mesh.example.com`
2. **Path → Topic**: `/orders/create` → `orders/create`
3. **JSON Wire Protocol**: HTTP requests/responses over the mesh
4. **Transparent Interception**: Patches `requests`/`httpx` libraries
5. **Auto Server Hook**: Detects and hooks FastAPI automatically

📖 **[Detailed Monkey Patching Documentation](docs/MONKEY_PATCHING.md)** - Learn about the patching mechanism, LangGraph integration, and advanced usage patterns.

📖 **[HTTPX Testing Guide](docs/HTTPX_TESTING.md)** - Complete guide to testing HTTPX (sync/async) integration with AZTM.

## Configuration

Environment variables (all optional):

```bash
# Connection
AZTM_HOST=mesh.example.com
AZTM_PORT=443
AZTM_DOMAIN=mesh.example.com

# Load balancing (optional)
AZTM_ROUTE_WEIGHT=100

# Size thresholds
AZTM_INLINE_LIMIT_KB=128      # Max inline size
AZTM_STREAM_LIMIT_MB=5         # Max streaming size

## Advanced Features (v0.2+)

### 🚀 Performance & Resilience
- **Connection Pooling**: Efficiently manage multiple concurrent connections
- **Response Caching**: Intelligent caching with TTL and LRU eviction
- **Circuit Breaker**: Automatically handle failing services
- **Retry Logic**: Exponential backoff for transient failures
- **Health Checks**: Monitor service availability
- **Service Discovery**: Dynamic service registration and discovery

### 📊 Observability
- **Prometheus Metrics**: Full metrics for monitoring
- **Performance Tracking**: Request duration, throughput, latency percentiles
- **Connection Monitoring**: Active connections, failures, retries
- **Payload Analytics**: Track transfer modes and sizes

### 🎯 Benchmarked Performance
- **Throughput**: >50,000 req/s (simulated)
- **P99 Latency**: <10ms for small payloads
- **Cache Hit Rate**: >90% for repeated requests
- **Connection Reuse**: 10x reduction in connection overhead

## Core Features
AZTM_FEATURE_UPLOAD_SLOTS=1   # Enable large file uploads
AZTM_FEATURE_JOSE=1           # Enable message signing
```

## Docker Support

```bash
# Start the mesh server
docker-compose up -d

# Run tests
docker-compose run aztm-test
```

## CI/CD Pipeline

### Continuous Integration

Every push and pull request triggers comprehensive testing:

- **Code Quality**: Black formatting, isort imports, flake8 linting
- **Unit Tests**: Python 3.10, 3.11, 3.12 matrix testing
- **Integration Tests**: Real mesh server testing (when credentials configured)
- **Build Verification**: Package building and Docker image creation
- **Coverage Reporting**: Automatic upload to Codecov

### GitHub Secrets Required

For full CI/CD functionality, configure these repository secrets:

```
AZTM_CLIENT_JID      # Client identity for testing
AZTM_CLIENT_PASSWORD # Client password
AZTM_SERVER_JID      # Server identity for testing
AZTM_SERVER_PASSWORD # Server password
```

### Workflow Files

#### `.github/workflows/ci.yml`
- Runs on every push and PR
- Comprehensive testing across Python versions
- Code quality checks
- Build and packaging validation

#### `.github/workflows/release.yml`
- Triggered by version tags (`v*`)
- Builds and publishes Docker images to GitHub Container Registry
- Creates GitHub releases with artifacts
- Publishes to PyPI (when configured)

#### `.github/workflows/nightly.yml`
- Daily regression testing at 2 AM UTC
- Memory leak detection
- Security vulnerability scanning
- Stress testing and performance benchmarks
- Can be manually triggered with custom scope

### Running CI Locally

```bash
# Simulate CI environment
act -j unit-tests                    # Run unit tests locally
act -j integration-tests -s GITHUB_TOKEN=$GITHUB_TOKEN  # Run with secrets

# Manual testing commands used in CI
pytest tests/unit/ -v --cov=aztm
pytest tests/regression/ -v --timeout=300
black aztm tests --check
isort aztm tests --check-only
flake8 aztm tests
```

### Release Process

1. **Update version** in `pyproject.toml`
2. **Commit changes**: `git commit -am "chore: bump version to X.Y.Z"`
3. **Create tag**: `git tag vX.Y.Z`
4. **Push**: `git push origin main --tags`
5. **Monitor**: Check Actions tab for release workflow

The release workflow will automatically:
- Run full test suite
- Build Python packages
- Create Docker images
- Publish to GitHub Container Registry
- Create GitHub release with artifacts
- Optionally publish to PyPI

## Development

```bash
# Clone repository
git clone https://github.com/eladrave/aztm
cd aztm

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e .[dev]

# Run tests
pytest tests/
```

## Architecture

```
Client App                    Mesh Server                   Server App
┌─────────┐                  ┌──────────┐                  ┌─────────┐
│ Python  │──HTTP request───▶│          │──AZTM payload───▶│ FastAPI │
│ + AZTM  │                  │ (broker) │                  │ + AZTM  │
│         │◀──HTTP response──│          │◀──AZTM payload───│         │
└─────────┘                  └──────────┘                  └─────────┘
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Author

Elad Rave - [https://github.com/eladrave](https://github.com/eladrave)
