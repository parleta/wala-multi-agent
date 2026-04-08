#!/usr/bin/env python3
"""
Simple AZTM Client Example

Shows how to make HTTP requests that transparently go via XMPP.
"""

import aztm
import requests

# Login to XMPP (this is the ONLY change needed!)
aztm.login(
    userid="client@xmpp.example",
    password="secret123"
)

# Now make HTTP requests as normal - they go over XMPP!
response = requests.post(
    "https://orders.api/orders/create",
    json={"sku": "ABC123", "quantity": 5}
)

print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")

# GET request
items = requests.get("https://inventory.api/items")
print(f"Items: {items.json()}")

# All standard HTTP features work
response = requests.put(
    "https://orders.api/orders/123/status",
    json={"status": "shipped"},
    headers={"Authorization": "Bearer token123"}
)

print("All requests sent via XMPP - no direct connection to servers!")