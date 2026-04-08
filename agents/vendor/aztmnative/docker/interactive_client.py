#!/usr/bin/env python3
"""
AZTM Interactive Docker Client
Allows sending custom HTTP requests via AZTM messaging transport
"""
import asyncio
import json
import os
import sys
import time
from typing import Dict, Any
sys.path.insert(0, '/app')

import slixmpp


class AZTMInteractiveClient(slixmpp.ClientXMPP):
    def __init__(self, jid: str, password: str):
        super().__init__(jid, password)
        self.add_event_handler("session_start", self.on_session_start)
        self.connected = asyncio.Event()
        self.responses = {}
        self.add_event_handler("message", self.on_message)
        
    async def on_session_start(self, event):
        self.send_presence()
        await self.get_roster()
        self.connected.set()
        print(f"✅ Connected as {self.boundjid}")
        
    async def on_message(self, msg):
        """Handle incoming responses"""
        if not msg['body']:
            return
        try:
            data = json.loads(msg['body'])
            if '_aztm' in data:
                corr = data['_aztm'].get('corr')
                if corr in self.responses:
                    self.responses[corr].set_result(data)
        except:
            pass
        
    async def send_request(self, to_jid: str, method: str, path: str, body: Any = None, headers: Dict = None) -> Dict[str, Any]:
        """Send HTTP request via AZTM messaging"""
        corr_id = f"req_{int(time.time()*1000)}"
        
        envelope = {
            "_aztm": {
                "method": method,
                "path": path,
                "headers": headers or {},
                "corr": corr_id,
            },
            "payload": body
        }
        
        response_future = asyncio.Future()
        self.responses[corr_id] = response_future
        
        # Send request
        self.send_message(
            mto=to_jid,
            mbody=json.dumps(envelope),
            msubject=path[1:] if path != '/' else 'root'
        )
        
        print(f"📤 Sent {method} {path}")
        
        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(response_future, timeout=10.0)
            return response
        except asyncio.TimeoutError:
            print(f"⏱️ Request timed out")
            return {"error": "timeout"}


async def interactive_session():
    """Run interactive AZTM client session"""
    print("\n" + "="*60)
    print("🚀 AZTM Interactive Client")
    print("="*60)
    
    # Get credentials from environment
    user = os.getenv('AZTM_USER', 'aztmclient@sure.im')
    password = os.getenv('AZTM_PASSWORD', '12345678')
    server_jid = os.getenv('AZTM_SERVER', 'aztmapi@sure.im')
    
    print(f"\n📝 Configuration:")
    print(f"  Client ID: {user}")
    print(f"  Server ID: {server_jid}")
    print()
    
    # Connect
    client = AZTMInteractiveClient(user, password)
    client.connect()
    
    # Wait for connection
    await client.connected.wait()
    await asyncio.sleep(1)
    
    print("\n" + "-"*60)
    print("📡 Interactive Mode - Send Custom API Calls")
    print("-"*60)
    print("\nCommands:")
    print("  GET <path>           - Send GET request")
    print("  POST <path> <json>   - Send POST with JSON body")
    print("  PUT <path> <json>    - Send PUT with JSON body")
    print("  DELETE <path>        - Send DELETE request")
    print("  LIST                 - Show available endpoints")
    print("  QUIT                 - Exit")
    print()
    
    available_endpoints = [
        "GET /health - Health check",
        "GET /status - Server status",
        "POST /orders/create - Create order (needs JSON body)",
        "GET /orders/{id} - Get order by ID",
        "POST /echo - Echo back the payload",
        "GET /info - Server information"
    ]
    
    while True:
        try:
            command = input("\n> ").strip()
            
            if not command:
                continue
                
            if command.upper() == "QUIT":
                break
                
            if command.upper() == "LIST":
                print("\n📚 Available endpoints:")
                for endpoint in available_endpoints:
                    print(f"  • {endpoint}")
                continue
            
            # Parse command
            parts = command.split(maxsplit=2)
            if len(parts) < 2:
                print("❌ Invalid command. Use: METHOD path [json_body]")
                continue
                
            method = parts[0].upper()
            path = parts[1]
            body = None
            
            # Parse JSON body if provided
            if len(parts) > 2:
                try:
                    body = json.loads(parts[2])
                except json.JSONDecodeError:
                    print("❌ Invalid JSON body")
                    continue
            
            # Ensure path starts with /
            if not path.startswith('/'):
                path = '/' + path
            
            # Send request
            print(f"\n🔄 Sending {method} {path}...")
            if body:
                print(f"   Body: {json.dumps(body)}")
            
            response = await client.send_request(server_jid, method, path, body)
            
            # Display response
            if 'payload' in response:
                print(f"\n✅ Response:")
                print(json.dumps(response['payload'], indent=2))
                if '_aztm' in response:
                    status = response['_aztm'].get('status', 'unknown')
                    print(f"   Status: {status}")
            else:
                print(f"\n❌ Error: {response.get('error', 'Unknown error')}")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print("\n👋 Disconnecting...")
    client.disconnect()


if __name__ == "__main__":
    print("Starting AZTM Interactive Client...")
    asyncio.run(interactive_session())