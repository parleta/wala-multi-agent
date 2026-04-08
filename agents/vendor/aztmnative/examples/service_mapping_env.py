#!/usr/bin/env python3
"""
AZTM Service Mapping Example: Environment Variable Configuration
Shows how to configure service mappings via environment variables
"""
import os
import json
import aztm
import requests

def main():
    print("\n" + "="*60)
    print("AZTM Service Mapping - Environment Variable Example")
    print("="*60)
    
    # Method 1: Set environment variables before importing aztm
    print("\n1. Setting environment variables...")
    
    # JSON mapping of hosts to services
    service_map = {
        "localhost:8080": "backend@sure.im",
        "api.local": "api@sure.im",
        "db.local:5432": "database@sure.im"
    }
    os.environ["AZTM_SERVICE_MAP"] = json.dumps(service_map)
    print(f"✅ AZTM_SERVICE_MAP = {json.dumps(service_map, indent=2)}")
    
    # Default service for unmapped URLs
    os.environ["AZTM_DEFAULT_SERVICE"] = "fallback@sure.im"
    print("✅ AZTM_DEFAULT_SERVICE = fallback@sure.im")
    
    # Special localhost handling (overrides specific mappings)
    os.environ["AZTM_LOCALHOST_SERVICE"] = "dev@sure.im"
    print("✅ AZTM_LOCALHOST_SERVICE = dev@sure.im")
    
    # Now login - mappings are loaded automatically
    print("\n2. Logging in to AZTM (mappings load automatically)...")
    aztm.login(
        userid="aztmclient@sure.im",
        password="12345678"
    )
    print("✅ Logged in - mappings loaded from environment")
    
    # Test the mappings
    print("\n3. Testing environment-based mappings...")
    print("-"*60)
    
    from aztm.core.service_mapping import resolve_service_for_url
    
    test_cases = [
        ("http://localhost/test", "Uses AZTM_LOCALHOST_SERVICE"),
        ("http://127.0.0.1/api", "Uses AZTM_LOCALHOST_SERVICE"),
        ("http://localhost:8000/", "Uses AZTM_LOCALHOST_SERVICE"),
        ("http://api.local/users", "Uses AZTM_SERVICE_MAP"),
        ("http://db.local:5432/", "Uses AZTM_SERVICE_MAP"),
        ("http://unknown.com/", "Uses AZTM_DEFAULT_SERVICE"),
    ]
    
    for url, description in test_cases:
        service = resolve_service_for_url(url)
        print(f"\n📍 {url}")
        print(f"   {description}")
        print(f"   → Resolved to: {service}")
    
    # Method 2: Override with programmatic configuration
    print("\n\n4. Adding programmatic overrides...")
    print("-"*60)
    
    # You can still add mappings programmatically
    aztm.register_service_mapping({
        "special.service.com": "special@sure.im"
    })
    print("✅ Added programmatic mapping: special.service.com → special@sure.im")
    
    # Test the override
    service = resolve_service_for_url("http://special.service.com/api")
    print(f"\n📍 http://special.service.com/api")
    print(f"   → Resolved to: {service}")
    
    print("\n" + "="*60)
    print("Environment Variable Configuration:")
    print("- AZTM_SERVICE_MAP: JSON dictionary of host mappings")
    print("- AZTM_DEFAULT_SERVICE: Fallback for unmapped URLs")
    print("- AZTM_LOCALHOST_SERVICE: Special handling for all localhost")
    print("")
    print("Benefits:")
    print("- Configure without changing code")
    print("- Perfect for Docker/Kubernetes deployments")
    print("- Different mappings per environment (dev/staging/prod)")
    print("="*60)
    
    # Clean up environment variables
    del os.environ["AZTM_SERVICE_MAP"]
    del os.environ["AZTM_DEFAULT_SERVICE"]
    del os.environ["AZTM_LOCALHOST_SERVICE"]


if __name__ == "__main__":
    main()