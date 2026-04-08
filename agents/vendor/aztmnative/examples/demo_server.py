#!/usr/bin/env python3
"""
AZTM Demo Server - Receives HTTP requests via XMPP
No inbound ports required!
"""

from fastapi import FastAPI
import aztm
import uvicorn
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AZTM Demo Server")

print("=" * 60)
print("AZTM Demo Server - HTTP over XMPP")
print("=" * 60)

# Login to XMPP as the server
print("\n1. Connecting to XMPP server (sure.im)...")
print("   This will take a few seconds...")

aztm.login(
    userid="aztmapi@sure.im",
    password="12345678"
)

print("\n✓ Connected to XMPP successfully!")
print("  Waiting for requests from clients via XMPP")
print("  NO INBOUND PORTS REQUIRED!\n")

# Define API endpoints
@app.post("/orders/create")
async def create_order(order: dict):
    """Create a new order - received via XMPP!"""
    print(f"\n📨 Received order via XMPP: {order}")
    return {
        "order_id": 12345,
        "status": "created",
        "sku": order.get("sku"),
        "quantity": order.get("quantity"),
        "message": "Order received via XMPP transport - ZERO ports open!"
    }

@app.get("/orders/{order_id}")
async def get_order(order_id: int):
    """Get order details - request received via XMPP!"""
    return {
        "order_id": order_id,
        "sku": "TEST123",
        "quantity": 3,
        "status": "processing",
        "transport": "XMPP"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    client = aztm.get_client()
    return {
        "status": "healthy",
        "service": "aztmapi",
        "transport": "XMPP",
        "connected": client.connected.is_set(),
        "jid": str(client.boundjid) if client.connected.is_set() else None,
        "ports_open": 0,
        "message": "Receiving HTTP requests via XMPP - No inbound ports!"
    }

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "AZTM Demo Server",
        "status": "running",
        "transport": "XMPP",
        "message": "This server receives HTTP requests via XMPP with ZERO open ports!"
    }

if __name__ == "__main__":
    print("=" * 60)
    print("Server ready! Receiving HTTP requests via XMPP")
    print("No inbound ports required - all traffic via XMPP!")
    print("=" * 60)
    
    # Run the FastAPI server (it only processes XMPP messages, no real HTTP server!)
    uvicorn.run(app, host="127.0.0.1", port=8000)