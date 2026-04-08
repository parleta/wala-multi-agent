#!/usr/bin/env python3
"""
AZTM Server Example
Demonstrates a FastAPI server that receives HTTP requests via XMPP
"""

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
import aztm
import uvicorn
import logging
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Create FastAPI app
app = FastAPI(
    title="AZTM Example API",
    description="Example API that receives requests via XMPP",
    version="1.0.0",
)


# Pydantic models
class Order(BaseModel):
    sku: str
    quantity: int
    customer: str


class OrderResponse(BaseModel):
    order_id: int
    status: str
    message: str


class Item(BaseModel):
    id: int
    name: str
    price: float
    in_stock: bool


# In-memory storage for demo
orders_db = []
items_db = [
    Item(id=1, name="Widget A", price=19.99, in_stock=True),
    Item(id=2, name="Widget B", price=29.99, in_stock=False),
    Item(id=3, name="Widget C", price=39.99, in_stock=True),
]

# API Routes


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "AZTM Example API is running"}


@app.get("/status")
async def get_status():
    """Get API status"""
    return {"status": "online", "service": "orders.api", "version": "1.0.0", "transport": "XMPP"}


@app.post("/orders/create", response_model=OrderResponse)
async def create_order(order: Order):
    """Create a new order"""
    # Generate order ID
    order_id = len(orders_db) + 1000

    # Store order
    orders_db.append({"id": order_id, "order": order.dict()})

    return OrderResponse(
        order_id=order_id, status="created", message=f"Order {order_id} created successfully"
    )


@app.get("/items")
async def list_items(
    x_aztm_from_jid: Optional[str] = Header(None), authorization: Optional[str] = Header(None)
):
    """List all items"""
    # Log who made the request (via XMPP)
    if x_aztm_from_jid:
        logging.info(f"Request from XMPP JID: {x_aztm_from_jid}")

    # Simple auth check
    if authorization and not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization")

    return {"items": [item.dict() for item in items_db]}


@app.get("/users/list")
async def list_users(page: int = 1, limit: int = 10, status: str = "all"):
    """List users with pagination"""
    # Mock user data
    users = [
        {"id": i, "username": f"user{i}", "status": "active" if i % 2 == 0 else "inactive"}
        for i in range(1, 21)
    ]

    # Filter by status
    if status != "all":
        users = [u for u in users if u["status"] == status]

    # Paginate
    start = (page - 1) * limit
    end = start + limit

    return {"page": page, "limit": limit, "total": len(users), "users": users[start:end]}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


def main():
    """Main function to start the server"""

    # Get credentials from environment or use defaults
    xmpp_user = os.getenv("AZTM_SERVER_JID", "orders.api@xmpp.example")
    xmpp_pass = os.getenv("AZTM_SERVER_PASSWORD", "server123")

    print(f"Logging in as {xmpp_user}...")

    # Login to XMPP - this auto-hooks FastAPI
    aztm.login(
        userid=xmpp_user,
        password=xmpp_pass,
        xmpp_host=os.getenv("XMPP_HOST", "localhost"),
        xmpp_port=int(os.getenv("XMPP_PORT", 5222)),
    )

    print("Successfully logged in to XMPP server")
    print("FastAPI server is now receiving requests via XMPP")
    print(f"Service JID: {xmpp_user}")

    # Start uvicorn server (optional - for regular HTTP testing)
    if os.getenv("ENABLE_HTTP", "false").lower() == "true":
        print("Also starting HTTP server on port 8000...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    else:
        print("HTTP server disabled. Only accepting XMPP requests.")
        print("Set ENABLE_HTTP=true to also enable regular HTTP")
        # Keep the process running
        import time

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
