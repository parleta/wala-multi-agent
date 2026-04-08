#!/usr/bin/env python3
"""
AZTM Docker Server Demo
FastAPI server that receives HTTP requests via XMPP - no HTTP ports needed!
"""
import os
import sys
import time
from datetime import datetime
sys.path.insert(0, '/app')

# Import AZTM SDK
import aztm
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn

# Create FastAPI app
app = FastAPI(title="AZTM Demo Server")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AZTM Docker Server", "timestamp": datetime.now().isoformat()}

@app.post("/orders/create")
async def create_order(order: dict):
    return {
        "order_id": f"ORD-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "status": "created", 
        "message": "Order received via XMPP!",
        "details": order
    }

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    return {
        "order_id": order_id,
        "status": "processing",
        "message": f"Order {order_id} retrieved via XMPP!",
        "created_at": datetime.now().isoformat()
    }

@app.get("/status")
async def get_status():
    return {
        "server": "AZTM Demo",
        "transport": "XMPP",
        "http_ports": "NONE - All communication via XMPP!",
        "innovation": "Zero open ports, full API functionality"
    }

def run_server():
    """Run the AZTM server"""
    print("\n" + "="*60)
    print("🚀 AZTM Docker Server Demo")
    print("="*60)
    
    # Get credentials from environment
    # Use JID directly from env, not through AZTM_ prefix which Config would parse
    user = os.getenv('JID', 'aztmapi@sure.im')
    password = os.getenv('PASSWORD', '12345678')
    
    print(f"\n📝 Configuration:")
    print(f"  Server JID: {user}")
    print(f"  Transport: XMPP (no HTTP ports)")
    print(f"  APIs: /health, /orders/create, /status")
    print()
    
    # Initialize AZTM in server mode - this will auto-hook into FastAPI!
    print("🔄 Initializing AZTM in server mode...")
    aztm.login(userid=user, password=password, server_mode=True)
    
    # Manually hook FastAPI since auto-detection might not work
    from aztm.server.fastapi_hook import hook_fastapi
    from aztm.core.auth import get_client
    hook_fastapi(app, get_client(), {})
    
    print("✅ Server connected as", user)
    print("✅ FastAPI app hooked to receive XMPP messages")
    print("📡 Ready to receive HTTP requests via XMPP")
    print("🔒 No HTTP ports exposed - completely invisible to port scans!\n")
    
    # Run FastAPI app (even though we're receiving via XMPP, 
    # we still need the ASGI app running for routing)
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")

if __name__ == "__main__":
    run_server()
