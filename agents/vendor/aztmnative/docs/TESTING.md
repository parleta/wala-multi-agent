# AZTM Testing Guide

## Important Testing Concepts

### ⚠️ Critical Testing Rule
**A single process can only login as either CLIENT or SERVER, never both!**

This is a fundamental limitation of AZTM - one process establishes one XMPP connection with one identity. Attempting to login twice in the same process (as both client and server) will fail.

## Testing Approaches

### 1. Local Testing (Client + Dockerized Server)

This is the recommended approach for development testing:

#### Step 1: Build and Start Server in Docker
```bash
# Build the server Docker image
cd /Users/eladrave/git/aztm
docker build -t aztm-server -f docker/Dockerfile.server .

# Run server in Docker (it will login as aztmapi@sure.im)
docker run -d --rm --name aztm-server aztm-server

# Check server logs (optional)
docker logs aztm-server
```

#### Step 2: Run Client Test Locally
```bash
# Activate virtual environment
source venv/bin/activate

# Run the E2E test (it will login as aztmclient@sure.im)
python test_e2e_complete.py

# Expected output:
# ✓ ALL E2E TESTS PASSED!
# HTTP-over-XMPP is working correctly!
```

#### Step 3: Cleanup
```bash
# Stop the server container
docker stop aztm-server
```

### 2. Docker-to-Docker Testing

For CI/CD or isolated testing:

```bash
# Build both containers
docker build -t aztm-server -f docker/Dockerfile.server .
docker build -t aztm-client -f docker/Dockerfile.client .

# Create a network for containers to communicate
docker network create aztm-test

# Start server
docker run -d --rm --name aztm-server --network aztm-test aztm-server

# Run client test
docker run --rm --name aztm-client --network aztm-test aztm-client

# Cleanup
docker stop aztm-server
docker network rm aztm-test
```

### 3. Unit Testing

Unit tests can be run in a single process as they use mocks:

```bash
# Run all unit tests
pytest tests/unit/ -v

# Run specific test file
pytest tests/unit/test_mapping.py -v

# Run with coverage
pytest tests/unit/ --cov=aztm --cov-report=html
```

### 4. Integration Testing

Integration tests require real XMPP accounts and must run client/server in separate processes:

```bash
# Run regression tests (starts subprocesses for client/server separation)
pytest tests/regression/ -v --timeout=300

# The regression tests use ProcessManager to handle client/server separation
# See: tests/regression/utils/process_manager.py
```

## Existing Test Files

### DO NOT CREATE NEW TEST FILES - Use These Existing Ones:

| Test File | Purpose | How to Run |
|-----------|---------|------------|
| `test_e2e_complete.py` | Full end-to-end test | Requires server in separate process/Docker |
| `test_simple_connectivity.py` | Basic XMPP connectivity | Single client login only |
| `test_server_login.py` | Server-side login test | Run as server only |
| `docker/client_demo.py` | Docker client demonstration | Run in Docker container |
| `docker/server_demo.py` | Docker server demonstration | Run in Docker container |
| `tests/regression/test_*.py` | Full regression suite | Use pytest with ProcessManager |

## Testing in CI/CD (GitHub Actions)

The CI pipeline handles client/server separation automatically:

1. **Integration tests spawn subprocesses**:
   - ProcessManager creates separate processes for client and server
   - Each process logs in with its own XMPP identity
   - Tests run HTTP-over-XMPP communication between them

2. **Required GitHub Secrets**:
   ```
   AZTM_CLIENT_JID=aztmclient@sure.im
   AZTM_CLIENT_PASSWORD=<password>
   AZTM_SERVER_JID=aztmapi@sure.im
   AZTM_SERVER_PASSWORD=<password>
   ```

3. **CI Workflow Structure**:
   - Unit tests: Run in single process with mocks
   - Integration tests: Use ProcessManager for client/server separation
   - No Docker-in-Docker needed - ProcessManager handles it

## Common Testing Mistakes to Avoid

### ❌ DON'T: Try to login as both client and server in same process
```python
# THIS WILL FAIL!
aztm.login(userid="aztmclient@sure.im", password="...")
aztm.login(userid="aztmapi@sure.im", password="...")  # FAILS - already logged in
```

### ❌ DON'T: Create new test files when existing ones work
```python
# Don't create test_local.py, test_new.py, etc.
# Use the existing test files listed above
```

### ✅ DO: Run server in one process, client in another
```bash
# Terminal 1 (or Docker)
python test_server_login.py  # or docker run aztm-server

# Terminal 2
python test_e2e_complete.py
```

### ✅ DO: Use ProcessManager for automated testing
```python
# The regression tests handle this automatically
# See: tests/regression/utils/process_manager.py
```

## Quick Test Commands

### Local Development Testing
```bash
# Quick smoke test (client only)
python -c "import aztm; print('✓ Import works')"

# Full E2E test (requires Docker)
docker run -d --rm --name aztm-server aztm-server && \
  python test_e2e_complete.py && \
  docker stop aztm-server

# Unit tests only
pytest tests/unit/ -v
```

### CI/CD Testing
```bash
# This is what runs in GitHub Actions
pytest tests/unit/ -v  # Unit tests
pytest tests/regression/ -v --timeout=300  # Integration tests with ProcessManager
```

## Debugging Tips

1. **Server won't start**: Check if another process is already using the XMPP credentials
2. **Login hangs**: The account might be already connected elsewhere
3. **Tests timeout**: Increase timeout values in ProcessManager
4. **Connection refused**: Ensure sure.im is accessible (not blocked by firewall)

## Testing Architecture

```
┌──────────────┐          ┌──────────────┐
│              │   XMPP   │              │
│  Client      │◄────────►│   Server     │
│  Process     │ sure.im  │   Process    │
│              │          │              │
│ aztmclient@  │          │  aztmapi@    │
└──────────────┘          └──────────────┘
     ▲                           ▲
     │                           │
     │                           │
┌──────────────────────────────────────┐
│          ProcessManager               │
│  (tests/regression/utils/)           │
│                                      │
│  - Spawns client/server processes   │
│  - Manages lifecycle                │
│  - Captures logs                    │
│  - Handles cleanup                  │
└──────────────────────────────────────┘
```

## Summary

- **Always run client and server in separate processes**
- **Use existing test files - don't create new ones**
- **Docker is preferred for server isolation**
- **ProcessManager handles separation in automated tests**
- **Real XMPP accounts (sure.im) are used for integration testing**