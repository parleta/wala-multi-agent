#!/usr/bin/env python3
"""
AZTM Service Mapping Example: Pattern-Based Routing
Shows how to use patterns for flexible service routing
"""
import aztm
import requests
import os

def main():
    print("\n" + "="*60)
    print("AZTM Service Mapping - Pattern Routing Example")
    print("="*60)
    
    # Login to AZTM
    print("\n1. Logging in to AZTM...")
    aztm.login(
        userid="aztmclient@sure.im",
        password="12345678"
    )
    print("✅ Logged in")
    
    # Setup pattern-based mappings
    print("\n2. Setting up pattern-based routing...")
    
    # Port-based patterns
    aztm.register_service_pattern("*:8080", "backend@sure.im")
    print("✅ Pattern: *:8080 → backend@sure.im (any host on port 8080)")
    
    aztm.register_service_pattern("*:3000", "frontend@sure.im")
    print("✅ Pattern: *:3000 → frontend@sure.im (any host on port 3000)")
    
    # Domain patterns
    aztm.register_service_pattern("*.staging.com", "staging@sure.im")
    print("✅ Pattern: *.staging.com → staging@sure.im")
    
    aztm.register_service_pattern("api-*", "api-services@sure.im")
    print("✅ Pattern: api-* → api-services@sure.im")
    
    # Contains pattern
    aztm.register_service_pattern("*test*", "test-env@sure.im")
    print("✅ Pattern: *test* → test-env@sure.im")
    
    # Default fallback
    aztm.set_default_service("default@sure.im")
    print("✅ Default service: default@sure.im (for unmapped URLs)")
    
    # Demonstrate routing
    print("\n3. Demonstrating pattern-based routing...")
    print("-"*60)
    
    test_urls = [
        ("http://myapp:8080/api", "Matches *:8080 → backend@sure.im"),
        ("http://localhost:3000/", "Matches *:3000 → frontend@sure.im"),
        ("http://app.staging.com/test", "Matches *.staging.com → staging@sure.im"),
        ("http://api-v1.com/users", "Matches api-* → api-services@sure.im"),
        ("http://test-server.net/", "Matches *test* → test-env@sure.im"),
        ("http://random.site.com/", "No pattern match → default@sure.im"),
    ]
    
    for url, expected in test_urls:
        print(f"\n📍 URL: {url}")
        print(f"   → {expected}")
        
        # Show which service would be used (without making actual request)
        from urllib.parse import urlparse
        parsed = urlparse(url)
        from aztm.core.service_mapping import resolve_service_for_url
        service = resolve_service_for_url(url)
        print(f"   ✅ Resolved to: {service}")
    
    print("\n" + "="*60)
    print("Pattern Matching Capabilities:")
    print("- Port wildcards: Route all services on a specific port")
    print("- Domain wildcards: Route subdomains together")
    print("- Prefix patterns: Route services by naming convention")
    print("- Contains patterns: Route based on substring matching")
    print("- Default fallback: Catch-all for unmapped URLs")
    print("="*60)


if __name__ == "__main__":
    main()