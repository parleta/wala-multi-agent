#!/usr/bin/env python3
"""
AZTM Service Mapping Example: Localhost Development
Shows how to use localhost URLs with AZTM without changing your code
"""
import aztm
import requests
import logging

# Enable debug logging to see the mapping in action
logging.basicConfig(level=logging.DEBUG)

def main():
    print("\n" + "="*60)
    print("AZTM Service Mapping - Localhost Example")
    print("="*60)
    
    # Step 1: Login to AZTM
    print("\n1. Logging in to AZTM...")
    aztm.login(
        userid="aztmclient@sure.im",
        password="12345678"
    )
    print("✅ Logged in as aztmclient@sure.im")
    
    # Step 2: Map localhost URLs to AZTM services
    print("\n2. Setting up service mappings...")
    aztm.register_service_mapping({
        "localhost:8080": "aztmapi@sure.im",
        "127.0.0.1:8080": "aztmapi@sure.im",
        "localhost:3000": "frontend@sure.im",
    })
    print("✅ Mapped localhost:8080 → aztmapi@sure.im")
    print("✅ Mapped 127.0.0.1:8080 → aztmapi@sure.im")
    print("✅ Mapped localhost:3000 → frontend@sure.im")
    
    # Step 3: Use existing localhost URLs - they work unchanged!
    print("\n3. Making requests to localhost (routed through AZTM)...")
    print("-"*60)
    
    try:
        # This looks like a normal localhost request, but it goes through AZTM!
        print("\n📤 GET http://localhost:8080/health")
        response = requests.get("http://localhost:8080/health", timeout=5)
        print(f"📥 Status: {response.status_code}")
        print(f"📥 Response: {response.json()}")
        
        # POST request with data
        print("\n📤 POST http://localhost:8080/api/orders")
        order_data = {"item": "widget", "quantity": 5}
        response = requests.post(
            "http://localhost:8080/api/orders",
            json=order_data,
            timeout=5
        )
        print(f"📥 Status: {response.status_code}")
        print(f"📥 Response: {response.json()}")
        
        # Different port example
        print("\n📤 GET http://localhost:3000/status")
        response = requests.get("http://localhost:3000/status", timeout=5)
        print(f"📥 Status: {response.status_code}")
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        print("\nNote: Make sure the AZTM server (aztmapi@sure.im) is running!")
    
    print("\n" + "="*60)
    print("Key Benefits:")
    print("- Your existing code with localhost URLs works unchanged")
    print("- No need to modify application configuration")
    print("- Perfect for local development with remote services")
    print("="*60)


if __name__ == "__main__":
    main()