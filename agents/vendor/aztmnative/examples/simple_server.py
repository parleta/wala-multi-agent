#!/usr/bin/env python3
"""
Simple AZTM Server Example

Shows how a FastAPI server receives HTTP requests via XMPP.
No inbound ports required!
"""

from fastapi import FastAPI
import aztm
import uvicorn

app = FastAPI()

# Login to XMPP as a service (this is the ONLY change needed!)
aztm.login(
    userid="orders.api@xmpp.example",
    password="secret456"
)

# Define your API as normal
@app.post("/orders/create")
async def create_order(order: dict):
    """This endpoint receives requests via XMPP!"""
    return {
        "order_id": 12345,
        "status": "created",
        "message": "Order received via XMPP transport!"
    }

@app.get("/orders/{order_id}")
async def get_order(order_id: int):
    """Get order details."""
    return {
        "order_id": order_id,
        "sku": "ABC123",
        "quantity": 5,
        "status": "processing"
    }

@app.put("/orders/{order_id}/status")
async def update_status(order_id: int, status_update: dict):
    """Update order status."""
    return {
        "order_id": order_id,
        "new_status": status_update.get("status"),
        "updated": True
    }

# Run the server (it receives via XMPP, no ports needed!)
if __name__ == "__main__":
    print("Server receiving HTTP requests via XMPP")
    print("No inbound ports required!")
    uvicorn.run(app, host="0.0.0.0", port=8000)