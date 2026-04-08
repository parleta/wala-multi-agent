#!/usr/bin/env python3
"""
AZTM Client Example
Demonstrates how to use AZTM to make HTTP requests over XMPP
"""

import aztm
import requests
import logging
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


def main():
    """Main example function"""

    # Get credentials from environment or use defaults
    xmpp_user = os.getenv("AZTM_CLIENT_JID", "client@xmpp.example")
    xmpp_pass = os.getenv("AZTM_CLIENT_PASSWORD", "client123")

    print(f"Logging in as {xmpp_user}...")

    # Login to XMPP - this patches HTTP libraries automatically
    aztm.login(
        userid=xmpp_user,
        password=xmpp_pass,
        xmpp_host=os.getenv("XMPP_HOST", "localhost"),
        xmpp_port=int(os.getenv("XMPP_PORT", 5222)),
    )

    print("Successfully logged in to XMPP server")
    print("All HTTP requests will now be routed through XMPP")

    # Example 1: Simple GET request
    print("\nExample 1: GET request")
    try:
        response = requests.get("https://orders.api/status")
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 2: POST request with JSON
    print("\nExample 2: POST request with JSON")
    try:
        data = {"sku": "ABC123", "quantity": 5, "customer": "test@example.com"}
        response = requests.post("https://orders.api/orders/create", json=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 3: Request with headers
    print("\nExample 3: Request with custom headers")
    try:
        headers = {"Authorization": "Bearer token123", "X-Custom-Header": "CustomValue"}
        response = requests.get("https://inventory.api/items", headers=headers)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
    except Exception as e:
        print(f"Error: {e}")

    # Example 4: Request with query parameters
    print("\nExample 4: Request with query parameters")
    try:
        params = {"page": 1, "limit": 10, "status": "active"}
        response = requests.get("https://users.api/list", params=params)
        print(f"Status Code: {response.status_code}")
        print(f"Final URL: {response.url}")
    except Exception as e:
        print(f"Error: {e}")

    print("\nAll examples completed!")


if __name__ == "__main__":
    main()
