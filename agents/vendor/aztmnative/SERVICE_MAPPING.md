# AZTM Service Mapping

## Overview

AZTM now supports flexible URL-to-service mapping, allowing you to:
- Keep using existing URLs (including localhost)
- Map different hosts to specific AZTM services
- Use pattern-based routing
- Configure mappings via environment variables

## Quick Start

### Keep Using localhost URLs

```python
import aztm

# Login as client
aztm.login(userid="aztmclienti@sure.im", password="12345678")

# Map localhost to your AZTM service
aztm.register_service_mapping({
    "localhost:8080": "aztmapi@sure.im",
    "127.0.0.1:8080": "aztmapi@sure.im"
})

# Now your existing code works unchanged!
import requests
response = requests.get("http://localhost:8080/api/health")
# This request goes through AZTM to aztmapi@sure.im
```

## Configuration Methods

### 1. Programmatic Configuration

```python
import aztm

aztm.login(userid="client@sure.im", password="password")

# Exact host mappings
aztm.register_service_mapping({
    "localhost:8080": "service1@sure.im",
    "api.example.com": "service2@sure.im",
    "staging.api.com": "service3@sure.im"
})

# Pattern-based mappings
aztm.register_service_pattern("*:8080", "default-8080@sure.im")
aztm.register_service_pattern("*.local", "local-services@sure.im")

# Default service for unmapped URLs
aztm.set_default_service("fallback@sure.im")
```

### 2. Environment Variables

```bash
# JSON mapping of hosts to services
export AZTM_SERVICE_MAP='{"localhost:8080":"aztmapi@sure.im","api.local":"api@sure.im"}'

# Default service for unmapped URLs
export AZTM_DEFAULT_SERVICE="default@sure.im"

# Special handling for all localhost URLs
export AZTM_LOCALHOST_SERVICE="aztmapi@sure.im"
```

Then in your code:
```python
import aztm
aztm.login(userid="client@sure.im", password="password")
# Mappings are loaded automatically from environment
```

### 3. Mixed Approach

```python
import os
import aztm

# Set via environment
os.environ["AZTM_LOCALHOST_SERVICE"] = "aztmapi@sure.im"

aztm.login(userid="client@sure.im", password="password")

# Add additional mappings programmatically
aztm.register_service_mapping({
    "custom.api.com": "custom@sure.im"
})
```

## Pattern Matching

AZTM supports several pattern types:

```python
# Port wildcards - any host on port 8080
aztm.register_service_pattern("*:8080", "port8080@sure.im")

# Domain wildcards - any subdomain of example.com
aztm.register_service_pattern("*.example.com", "example@sure.im")

# Prefix matching
aztm.register_service_pattern("api-*", "api-services@sure.im")

# Contains matching
aztm.register_service_pattern("*staging*", "staging@sure.im")
```

## Resolution Order

When a URL is intercepted, AZTM resolves the service in this order:

1. **Exact match with port**: `localhost:8080` 
2. **Exact match without port**: `localhost`
3. **Pattern matching**: `*:8080`, `*.local`, etc.
4. **Default service**: If set via `set_default_service()`
5. **Standard AZTM mapping**: hostname becomes service name

## Complete Examples

### Example 1: Development Setup

```python
import aztm
import requests

# Client setup
aztm.login(userid="dev-client@sure.im", password="dev-password")

# Map all localhost ports to development service
aztm.register_service_mapping({
    "localhost:3000": "frontend@sure.im",
    "localhost:8080": "backend@sure.im",
    "localhost:5432": "database@sure.im"
})

# Your existing code works unchanged
api_response = requests.get("http://localhost:8080/api/users")
db_response = requests.get("http://localhost:5432/health")
```

### Example 2: Multi-Environment Setup

```python
import os
import aztm

# Determine environment
env = os.getenv("ENVIRONMENT", "dev")

# Environment-specific mappings
mappings = {
    "dev": {
        "localhost:8080": "dev-api@sure.im",
        "api.local": "dev-api@sure.im"
    },
    "staging": {
        "localhost:8080": "staging-api@sure.im",
        "staging.example.com": "staging-api@sure.im"
    },
    "prod": {
        "api.example.com": "prod-api@sure.im"
    }
}

aztm.login(userid=f"{env}-client@sure.im", password="password")
aztm.register_service_mapping(mappings[env])
```

### Example 3: Zero Configuration Change

Your existing application code:
```python
# app.py - NO CHANGES NEEDED
import requests

def check_health():
    return requests.get("http://localhost:8080/health")

def get_users():
    return requests.get("http://localhost:8080/api/users")
```

Add AZTM with just a startup script:
```python
# aztm_init.py - Run this before your app
import aztm
aztm.login(userid="app-client@sure.im", password="password")
aztm.register_service_mapping({"localhost:8080": "app-service@sure.im"})

# Now import and run your app
from app import *
```

## Integration with aztmchain

For the aztmchain project specifically:

```python
# client_sdk.py
import aztm
aztm.login(userid="aztmclienti@sure.im", password="12345678")
aztm.register_service_mapping({"localhost:8080": "aztmapi@sure.im"})

# Now your RemoteGraphClient can keep using http://localhost:8080
class RemoteGraphClient:
    def __init__(self, url: str = "http://localhost:8080", graph_name: str = "agent"):
        # No changes needed - AZTM handles the routing!
```

## Debugging

Enable debug logging to see mapping resolution:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

import aztm
aztm.login(userid="client@sure.im", password="password")
aztm.register_service_mapping({"localhost:8080": "service@sure.im"})

# You'll see debug output like:
# DEBUG:aztm.core.service_mapping:Resolved localhost:8080 -> service@sure.im
```

## Benefits

1. **Zero Code Changes**: Keep all existing URLs
2. **Localhost Support**: Development servers work seamlessly
3. **Flexible Routing**: Map different services dynamically
4. **Environment-Specific**: Different mappings for dev/staging/prod
5. **Pattern Matching**: Route groups of services easily
6. **Backward Compatible**: Works with existing AZTM deployments