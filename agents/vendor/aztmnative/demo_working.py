#!/usr/bin/env python3
"""
Working AZTM Demo - Client and Server Communication via XMPP
"""

import asyncio
import json
import logging
import slixmpp
from typing import Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class AZTMClient(slixmpp.ClientXMPP):
    """AZTM Client - sends HTTP requests over XMPP"""
    
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.connected_event = asyncio.Event()
        self.responses = {}
        
        self.add_event_handler("session_start", self.on_session_start)
        self.add_event_handler("message", self.on_message)
        
    async def on_session_start(self, event):
        self.send_presence()
        await self.get_roster()
        self.connected_event.set()
        logging.info(f"✅ Client connected as {self.boundjid}")
        
    async def on_message(self, msg):
        """Handle response messages"""
        if msg['subject'].endswith(':response'):
            try:
                # Parse JSON body
                body = json.loads(msg['body']) if isinstance(msg['body'], str) else msg['body']
                aztm_meta = body.get('_aztm', {})
                corr_id = aztm_meta.get('corr')
                
                if corr_id and corr_id in self.responses:
                    self.responses[corr_id].set_result(body)
            except Exception as e:
                logging.error(f"Error parsing response: {e}")
    
    async def send_http_request(self, to_jid: str, method: str, path: str, body: Any = None) -> Dict:
        """Send HTTP request over XMPP"""
        import uuid
        corr_id = str(uuid.uuid4())
        
        # Create request envelope
        envelope = {
            "_aztm": {
                "method": method,
                "path": path,
                "headers": {},
                "corr": corr_id
            },
            "payload": body
        }
        
        # Create future for response
        response_future = asyncio.Future()
        self.responses[corr_id] = response_future
        
        # Send message
        self.send_message(
            mto=to_jid,
            mbody=json.dumps(envelope),
            msubject=path.lstrip('/'),
            mtype='chat'
        )
        
        logging.info(f"📤 Sent {method} {path} to {to_jid}")
        
        # Wait for response
        try:
            response = await asyncio.wait_for(response_future, timeout=5)
            logging.info(f"📥 Got response: {response}")
            return response
        except asyncio.TimeoutError:
            logging.error("Response timeout")
            return {"error": "timeout"}

class AZTMServer(slixmpp.ClientXMPP):
    """AZTM Server - receives HTTP requests over XMPP"""
    
    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.connected_event = asyncio.Event()
        
        self.add_event_handler("session_start", self.on_session_start)
        self.add_event_handler("message", self.on_message)
        
        # Simple API handlers
        self.routes = {
            "health": self.handle_health,
            "orders/create": self.handle_create_order,
        }
        
    async def on_session_start(self, event):
        self.send_presence()
        await self.get_roster()
        self.connected_event.set()
        logging.info(f"✅ Server connected as {self.boundjid}")
        
    async def on_message(self, msg):
        """Handle incoming HTTP requests"""
        if not msg['body']:
            return
            
        try:
            # Parse request
            envelope = json.loads(msg['body'])
            aztm_meta = envelope.get('_aztm', {})
            payload = envelope.get('payload')
            
            method = aztm_meta.get('method', 'GET')
            path = aztm_meta.get('path', '/')
            corr_id = aztm_meta.get('corr')
            
            logging.info(f"📨 Received {method} {path} from {msg['from'].bare}")
            
            # Route to handler
            route_key = path.lstrip('/') or 'root'
            handler = self.routes.get(route_key, self.handle_not_found)
            
            # Call handler
            response_data = await handler(payload)
            
            # Send response
            response_envelope = {
                "_aztm": {
                    "status": 200,
                    "headers": {"Content-Type": "application/json"},
                    "corr": corr_id
                },
                "payload": response_data
            }
            
            self.send_message(
                mto=msg['from'],
                mbody=json.dumps(response_envelope),
                msubject=f"{msg['subject']}:response",
                mtype='chat'
            )
            
            logging.info(f"📤 Sent response to {msg['from'].bare}")
            
        except Exception as e:
            logging.error(f"Error handling request: {e}")
    
    async def handle_health(self, payload):
        """Health check endpoint"""
        return {"status": "healthy", "service": "AZTM Demo Server"}
    
    async def handle_create_order(self, payload):
        """Create order endpoint"""
        return {
            "order_id": "12345",
            "status": "created",
            "message": "Order received via XMPP!"
        }
    
    async def handle_not_found(self, payload):
        """404 handler"""
        return {"error": "Not found"}

async def run_demo():
    """Run the complete demo"""
    print("\n" + "="*60)
    print("AZTM Working Demo - HTTP over XMPP")
    print("="*60)
    
    # Create server
    server = AZTMServer("aztmapi@sure.im", "12345678")
    server.connect()
    
    # Wait for server to connect
    await asyncio.wait_for(server.connected_event.wait(), timeout=10)
    print("✅ Server ready!")
    
    # Create client  
    client = AZTMClient("aztmclient@sure.im", "12345678")
    client.connect()
    
    # Wait for client to connect
    await asyncio.wait_for(client.connected_event.wait(), timeout=10)
    print("✅ Client ready!")
    
    # Give a moment for presence to propagate
    await asyncio.sleep(2)
    
    print("\n" + "="*60)
    print("Sending HTTP Requests over XMPP...")
    print("="*60 + "\n")
    
    # Test 1: Health check
    print("1. Testing GET /health")
    response = await client.send_http_request(
        "aztmapi@sure.im",
        "GET",
        "/health"
    )
    print(f"   Response: {response}\n")
    
    # Test 2: Create order
    print("2. Testing POST /orders/create")
    response = await client.send_http_request(
        "aztmapi@sure.im",
        "POST",
        "/orders/create",
        {"sku": "ABC123", "quantity": 5}
    )
    print(f"   Response: {response}\n")
    
    # Test 3: Non-existent endpoint
    print("3. Testing GET /unknown")
    response = await client.send_http_request(
        "aztmapi@sure.im",
        "GET",
        "/unknown"
    )
    print(f"   Response: {response}\n")
    
    print("="*60)
    print("✅ Demo Complete!")
    print("All HTTP requests were sent via XMPP - no direct connection!")
    print("="*60)
    
    # Cleanup
    client.disconnect()
    server.disconnect()
    
    # Give time for disconnection
    await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\n👋 Demo stopped by user")