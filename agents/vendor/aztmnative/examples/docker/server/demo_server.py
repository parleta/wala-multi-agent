#!/usr/bin/env python3
"""
AZTM Demo Server

A FastAPI server that receives HTTP requests via XMPP.
No inbound ports required - only outbound XMPP connection!
"""

import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Import and initialize AZTM
import aztm
from aztm.security import JOSEHandler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="AZTM Demo Server",
    description="A server that receives HTTP requests via XMPP",
    version="1.0.0"
)

# Initialize JOSE handler for secure communication
jose_handler = None
if os.getenv("AZTM_FEATURE_JOSE") == "1":
    jose_handler = JOSEHandler()
    logger.info("JOSE security enabled")

# Data models
class Order(BaseModel):
    sku: str
    quantity: int
    customer_email: Optional[str] = None

class OrderResponse(BaseModel):
    order_id: str
    status: str
    created_at: str
    message: str

# In-memory storage for demo
orders_db: List[Dict] = []

# API Routes
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "AZTM Demo Server",
        "status": "running",
        "transport": "XMPP",
        "secure": jose_handler is not None,
        "message": "This server receives HTTP requests via XMPP!",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "xmpp_connected": True,
        "orders_processed": len(orders_db),
        "uptime_seconds": 0  # Would track actual uptime in production
    }

@app.post("/orders/create", response_model=OrderResponse)
async def create_order(order: Order):
    """Create a new order."""
    import uuid
    
    order_id = str(uuid.uuid4())[:8]
    order_data = {
        "order_id": order_id,
        "sku": order.sku,
        "quantity": order.quantity,
        "customer_email": order.customer_email,
        "created_at": datetime.utcnow().isoformat(),
        "status": "created"
    }
    
    orders_db.append(order_data)
    
    logger.info(f"Created order: {order_id} for {order.quantity}x {order.sku}")
    
    return OrderResponse(
        order_id=order_id,
        status="created",
        created_at=order_data["created_at"],
        message=f"Order {order_id} created successfully via XMPP transport!"
    )

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    """Get order details."""
    for order in orders_db:
        if order["order_id"] == order_id:
            return order
    
    raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

@app.get("/orders")
async def list_orders():
    """List all orders."""
    return {
        "total": len(orders_db),
        "orders": orders_db
    }

@app.get("/demo/echo")
async def echo(message: str = "Hello AZTM"):
    """Echo endpoint for testing."""
    response = {
        "echo": message,
        "reversed": message[::-1],
        "length": len(message),
        "transport": "XMPP",
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # If JOSE is enabled, add signature
    if jose_handler:
        signature = jose_handler.sign_payload(response)
        response["signature"] = signature[:50] + "..."  # Show truncated signature
    
    return response

@app.get("/demo/secure")
async def secure_endpoint():
    """Demonstrate secure communication."""
    if not jose_handler:
        return {"error": "JOSE not enabled"}
    
    # Export our public keys
    public_keys = jose_handler.export_public_keys()
    
    return {
        "message": "Secure endpoint accessed via XMPP",
        "security": {
            "jose_enabled": True,
            "signing_key_id": jose_handler.current_signing_key,
            "encryption_key_id": jose_handler.current_encryption_key,
            "public_keys_available": len(public_keys)
        },
        "timestamp": datetime.utcnow().isoformat()
    }

async def initialize_aztm():
    """Initialize AZTM with XMPP credentials."""
    jid = os.getenv("AZTM_JID", "aztmapi@sure.im")
    password = os.getenv("AZTM_PASSWORD", "12345678")
    
    logger.info(f"Initializing AZTM server as {jid}")
    
    try:
        # Login to XMPP - this will auto-hook into FastAPI
        aztm.login(
            userid=jid,
            password=password,
            secure=os.getenv("AZTM_FEATURE_TLS") == "1"
        )
        
        logger.info("✅ AZTM server initialized successfully!")
        logger.info("Server is now receiving HTTP requests via XMPP")
        logger.info("No inbound ports required!")
        
    except Exception as e:
        logger.error(f"Failed to initialize AZTM: {e}")
        raise

async def main():
    """Main entry point."""
    # Initialize AZTM
    await initialize_aztm()
    
    # Add a small delay to ensure XMPP connection is established
    await asyncio.sleep(2)
    
    # Run FastAPI app (even though we're receiving via XMPP, 
    # we still need the ASGI app running)
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=False  # We're not actually serving HTTP
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("AZTM Demo Server Starting")
    logger.info("This server receives HTTP requests via XMPP")
    logger.info("No inbound ports required!")
    logger.info("=" * 60)
    
    # Run the async main
    asyncio.run(main())