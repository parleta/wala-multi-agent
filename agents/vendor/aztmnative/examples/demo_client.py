#!/usr/bin/env python3
"""
AZTM Demo Client - Sends HTTP requests via XMPP
No direct connection to the server!
"""

import aztm
import requests
import time
import json

print("=" * 60)
print("AZTM Demo Client - HTTP over XMPP")
print("=" * 60)

# Configure service mapping
print("\n1. Setting up service mapping...")
aztm.register_service_mapping({
    "localhost:8080": "aztmapi@sure.im",
    "aztmapi": "aztmapi@sure.im",
    "orders.api": "aztmapi@sure.im"
})
print("   ✓ Mapped localhost:8080 → aztmapi@sure.im")

# Login to XMPP as the client
print("\n2. Connecting to XMPP server (sure.im)...")
print("   This will take a few seconds...")

aztm.login(
    userid="aztmclient@sure.im",
    password="12345678"
)

client = aztm.get_client()
print(f"\n✓ Connected to XMPP as: {client.boundjid}")

# Wait a moment for everything to stabilize
time.sleep(2)

print("\n" + "=" * 60)
print("DEMONSTRATION: HTTP REQUESTS VIA XMPP")
print("=" * 60)

# Demo 1: Create an order
print("\n📤 Demo 1: Creating an order...")
print("   POST http://localhost:8080/orders/create")
print("   (This will be sent as XMPP message to aztmapi@sure.im)")

try:
    response = requests.post(
        "http://localhost:8080/orders/create",
        json={"sku": "DEMO-123", "quantity": 5},
        timeout=10
    )
    
    print(f"\n✓ Response received via XMPP!")
    print(f"   Status: {response.status_code}")
    print(f"   Body: {json.dumps(response.json(), indent=2)}")
    
except requests.exceptions.Timeout:
    print("\n⚠ Request timed out - server may not be running")
    print("  Make sure demo_server.py is running first!")
except Exception as e:
    print(f"\n⚠ Error: {e}")

# Demo 2: Get order details
print("\n📤 Demo 2: Getting order details...")
print("   GET http://localhost:8080/orders/12345")

try:
    response = requests.get(
        "http://localhost:8080/orders/12345",
        timeout=10
    )
    
    print(f"\n✓ Response received via XMPP!")
    print(f"   Status: {response.status_code}")
    print(f"   Body: {json.dumps(response.json(), indent=2)}")
    
except Exception as e:
    print(f"\n⚠ Error: {e}")

# Demo 3: Health check
print("\n📤 Demo 3: Health check...")
print("   GET http://localhost:8080/health")

try:
    response = requests.get(
        "http://localhost:8080/health",
        timeout=10
    )
    
    print(f"\n✓ Response received via XMPP!")
    print(f"   Status: {response.status_code}")
    print(f"   Body: {json.dumps(response.json(), indent=2)}")
    
except Exception as e:
    print(f"\n⚠ Error: {e}")

print("\n" + "=" * 60)
print("KEY POINTS:")
print("=" * 60)
print("✅ All HTTP requests were sent as XMPP messages")
print("✅ No direct TCP connection to the server")
print("✅ Server has ZERO open ports")
print("✅ Works behind NAT/firewalls")
print("✅ Only requirement: XMPP connectivity")

print("\n" + "=" * 60)
print("AZTM Demo Complete!")
print("=" * 60)