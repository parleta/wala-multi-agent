#!/usr/bin/env python3
"""
AZTM Docker Client Demo
Sends HTTP requests that are transparently routed through XMPP
"""
import json
import logging
import os
import sys
import time
sys.path.insert(0, '/app')

# Set up logging to see what's happening
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# IMPORTANT: Set up service mapping BEFORE importing aztm
# This must happen before the import to ensure proper initialization
server_jid = os.getenv('SERVER_JID', 'aztmapi@sure.im')
service_map = {"aztmapi.service": server_jid}
os.environ['SERVICE_MAP'] = json.dumps(service_map)

# Now import AZTM SDK and requests
import aztm
import requests

def run_demo():
    """Run the AZTM client demo"""
    print("\n" + "="*60)
    print("🚀 AZTM Docker Client Demo")
    print("="*60)
    
    # Get credentials from environment
    # Use JID directly from env, not through AZTM_ prefix which Config would parse
    user = os.getenv('JID', 'aztmclient@sure.im')
    password = os.getenv('PASSWORD', '12345678')
    # server_jid already set above before imports
    
    print(f"\n📝 Configuration:")
    print(f"  Client JID: {user}")
    print(f"  Server JID: {server_jid}")
    print(f"  Service Mapping: aztmapi.service -> {server_jid}")
    print()
    
    # Initialize AZTM - this will intercept all HTTP requests!
    print("\n🔄 Initializing AZTM...")
    aztm.login(userid=user, password=password)
    
    print("✅ Client connected as", user)
    print("\n" + "-"*60)
    print("📡 Making API Calls via XMPP (No HTTP ports!)")
    print("-"*60 + "\n")
    
    # Now make normal HTTP requests - AZTM will route them via XMPP!
    base_url = "http://aztmapi.service"
    
    # Demo API calls
    demos = [
        ("Health Check", "GET", "/health", None),
        ("Create Order", "POST", "/orders/create", {
            "sku": "DOCKER-123",
            "quantity": 10,
            "customer": "Docker Demo"
        }),
        ("Get Status", "GET", "/status", None),
    ]
    
    for title, method, path, body in demos:
        print(f"\n### {title}")
        print(f"Request: {method} {path}")
        if body:
            print(f"Payload: {json.dumps(body, indent=2)}")
        
        print(f"📤 Sending {method} {path} via XMPP to {server_jid}")
        
        try:
            # Make normal HTTP requests - AZTM handles the XMPP transport!
            if method == "GET":
                response = requests.get(f"{base_url}{path}")
            elif method == "POST":
                response = requests.post(f"{base_url}{path}", json=body)
            
            if response.status_code == 200:
                print(f"✅ Response: {json.dumps(response.json(), indent=2)}")
            else:
                print(f"❌ Error: Status {response.status_code}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        time.sleep(1)
    
    print("\n" + "="*60)
    print("✨ Demo Complete!")
    print("Key Innovation: All HTTP traffic went through XMPP messaging!")
    print("="*60 + "\n")

if __name__ == "__main__":
    run_demo()
