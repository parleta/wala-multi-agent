#!/usr/bin/env python3
"""
AZTM Demo Client (HTTPX Version) - Sends HTTP requests via XMPP
No direct connection to the server!
This version uses httpx instead of requests to test httpx patching.
"""

import aztm
import httpx
import asyncio
import time
import json

async def run_async_demo():
    """Run async httpx demo"""
    print("\n" + "=" * 60)
    print("ASYNC HTTPX TESTS")
    print("=" * 60)
    
    async with httpx.AsyncClient() as client:
        # Async Demo 1: Create order
        print("\n📤 Async Demo 1: Creating an order...")
        print("   POST http://localhost:8080/orders/create")
        print("   (Using httpx.AsyncClient)")
        
        try:
            response = await client.post(
                "http://localhost:8080/orders/create",
                json={"sku": "ASYNC-456", "quantity": 3},
                timeout=10
            )
            
            print(f"\n✓ Async response received via XMPP!")
            print(f"   Status: {response.status_code}")
            print(f"   Body: {json.dumps(response.json(), indent=2)}")
        except httpx.TimeoutException:
            print("\n⚠ Async request timed out")
        except Exception as e:
            print(f"\n⚠ Async error: {e}")
        
        # Async Demo 2: Health check
        print("\n📤 Async Demo 2: Health check...")
        print("   GET http://localhost:8080/health")
        
        try:
            response = await client.get(
                "http://localhost:8080/health",
                timeout=10
            )
            
            print(f"\n✓ Async response received via XMPP!")
            print(f"   Status: {response.status_code}")
            print(f"   Body: {json.dumps(response.json(), indent=2)}")
        except Exception as e:
            print(f"\n⚠ Async error: {e}")

def main():
    print("=" * 60)
    print("AZTM Demo Client - HTTPX Version (HTTP over XMPP)")
    print("=" * 60)

    # Configure service mapping
    print("\n1. Setting up service mapping...")
    aztm.register_service_mapping({
        "localhost:8080": "aztmapi@sure.im",
        "localhost:8000": "aztmapi@sure.im",  # Also map port 8000
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
    print("DEMONSTRATION: HTTPX REQUESTS VIA XMPP")
    print("=" * 60)

    # Sync httpx tests
    print("\n" + "=" * 60)
    print("SYNCHRONOUS HTTPX TESTS")
    print("=" * 60)

    # Demo 1: Create an order using sync httpx
    print("\n📤 Sync Demo 1: Creating an order...")
    print("   POST http://localhost:8080/orders/create")
    print("   (Using httpx.Client - synchronous)")

    try:
        with httpx.Client() as sync_client:
            response = sync_client.post(
                "http://localhost:8080/orders/create",
                json={"sku": "HTTPX-123", "quantity": 5},
                timeout=10
            )
            
            print(f"\n✓ Response received via XMPP!")
            print(f"   Status: {response.status_code}")
            print(f"   Body: {json.dumps(response.json(), indent=2)}")
            
    except httpx.TimeoutException:
        print("\n⚠ Request timed out - server may not be running")
        print("  Make sure demo_server.py is running first!")
    except Exception as e:
        print(f"\n⚠ Error: {e}")

    # Demo 2: Get order details using sync httpx
    print("\n📤 Sync Demo 2: Getting order details...")
    print("   GET http://localhost:8080/orders/12345")

    try:
        with httpx.Client() as sync_client:
            response = sync_client.get(
                "http://localhost:8080/orders/12345",
                timeout=10
            )
            
            print(f"\n✓ Response received via XMPP!")
            print(f"   Status: {response.status_code}")
            print(f"   Body: {json.dumps(response.json(), indent=2)}")
            
    except Exception as e:
        print(f"\n⚠ Error: {e}")

    # Demo 3: Health check using sync httpx
    print("\n📤 Sync Demo 3: Health check...")
    print("   GET http://localhost:8080/health")

    try:
        with httpx.Client() as sync_client:
            response = sync_client.get(
                "http://localhost:8080/health",
                timeout=10
            )
            
            print(f"\n✓ Response received via XMPP!")
            print(f"   Status: {response.status_code}")
            print(f"   Body: {json.dumps(response.json(), indent=2)}")
            
    except Exception as e:
        print(f"\n⚠ Error: {e}")

    # Run async tests
    asyncio.run(run_async_demo())

    print("\n" + "=" * 60)
    print("KEY POINTS:")
    print("=" * 60)
    print("✅ Both sync and async httpx clients work with AZTM")
    print("✅ All HTTP requests were sent as XMPP messages")
    print("✅ No direct TCP connection to the server")
    print("✅ Server has ZERO open ports")
    print("✅ Works behind NAT/firewalls")
    print("✅ Only requirement: XMPP connectivity")

    print("\n" + "=" * 60)
    print("AZTM HTTPX Demo Complete!")
    print("=" * 60)

if __name__ == "__main__":
    main()