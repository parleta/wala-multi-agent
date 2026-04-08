#!/usr/bin/env python3
"""
AZTM Demo Client

A client that sends HTTP requests via XMPP transport.
No direct network connection to the server required!
"""

import os
import sys
import time
import asyncio
import logging
import requests
from typing import Dict, Any

# Import and initialize AZTM
import aztm
from aztm.security import JOSEHandler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize JOSE handler for secure communication
jose_handler = None
if os.getenv("AZTM_FEATURE_JOSE") == "1":
    jose_handler = JOSEHandler()
    logger.info("JOSE security enabled on client")

def initialize_aztm():
    """Initialize AZTM with XMPP credentials."""
    jid = os.getenv("AZTM_JID", "aztmclient@sure.im")
    password = os.getenv("AZTM_PASSWORD", "12345678")
    
    logger.info(f"Initializing AZTM client as {jid}")
    
    try:
        # Login to XMPP - this will intercept all HTTP requests
        aztm.login(
            userid=jid,
            password=password,
            secure=os.getenv("AZTM_FEATURE_TLS") == "1"
        )
        
        logger.info("✅ AZTM client initialized successfully!")
        logger.info("HTTP requests will now be sent via XMPP")
        
    except Exception as e:
        logger.error(f"Failed to initialize AZTM: {e}")
        raise

def demo_basic_requests():
    """Demonstrate basic HTTP requests via XMPP."""
    server_jid = os.getenv("AZTM_SERVER_JID", "aztmapi@sure.im")
    
    # The URL host will be mapped to the server's JID
    # For demo, we use the server JID as the hostname
    base_url = f"https://{server_jid.split('@')[0]}.api"
    
    logger.info("=" * 60)
    logger.info("Demo: Basic HTTP Requests via XMPP")
    logger.info(f"Target: {server_jid}")
    logger.info("=" * 60)
    
    # 1. GET request to root
    logger.info("\n1. Testing GET /")
    try:
        response = requests.get(f"{base_url}/")
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Response: {response.json()}")
    except Exception as e:
        logger.error(f"Request failed: {e}")
    
    time.sleep(1)
    
    # 2. Health check
    logger.info("\n2. Testing GET /health")
    try:
        response = requests.get(f"{base_url}/health")
        logger.info(f"Status: {response.status_code}")
        logger.info(f"Response: {response.json()}")
    except Exception as e:
        logger.error(f"Request failed: {e}")
    
    time.sleep(1)
    
    # 3. Echo test with parameter
    logger.info("\n3. Testing GET /demo/echo")
    try:
        response = requests.get(
            f"{base_url}/demo/echo",
            params={"message": "Hello from AZTM client via XMPP!"}
        )
        logger.info(f"Status: {response.status_code}")
        data = response.json()
        logger.info(f"Echo: {data.get('echo')}")
        logger.info(f"Reversed: {data.get('reversed')}")
        logger.info(f"Transport: {data.get('transport')}")
        if 'signature' in data:
            logger.info(f"Signed: {data.get('signature')}")
    except Exception as e:
        logger.error(f"Request failed: {e}")

def demo_create_orders():
    """Demonstrate POST requests to create orders."""
    server_jid = os.getenv("AZTM_SERVER_JID", "aztmapi@sure.im")
    base_url = f"https://{server_jid.split('@')[0]}.api"
    
    logger.info("\n" + "=" * 60)
    logger.info("Demo: Creating Orders via XMPP")
    logger.info("=" * 60)
    
    # Create multiple orders
    orders = [
        {"sku": "LAPTOP-001", "quantity": 2, "customer_email": "alice@example.com"},
        {"sku": "MOUSE-002", "quantity": 5, "customer_email": "bob@example.com"},
        {"sku": "KEYBOARD-003", "quantity": 3, "customer_email": "charlie@example.com"},
    ]
    
    created_orders = []
    
    for order_data in orders:
        logger.info(f"\nCreating order: {order_data}")
        try:
            response = requests.post(
                f"{base_url}/orders/create",
                json=order_data
            )
            
            if response.status_code == 200:
                result = response.json()
                created_orders.append(result["order_id"])
                logger.info(f"✅ Order created: {result['order_id']}")
                logger.info(f"   Message: {result['message']}")
            else:
                logger.error(f"Failed with status: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Request failed: {e}")
        
        time.sleep(1)
    
    return created_orders

def demo_retrieve_orders(order_ids):
    """Demonstrate retrieving orders."""
    server_jid = os.getenv("AZTM_SERVER_JID", "aztmapi@sure.im")
    base_url = f"https://{server_jid.split('@')[0]}.api"
    
    logger.info("\n" + "=" * 60)
    logger.info("Demo: Retrieving Orders via XMPP")
    logger.info("=" * 60)
    
    # Get individual orders
    for order_id in order_ids[:2]:  # Just check first two
        logger.info(f"\nRetrieving order: {order_id}")
        try:
            response = requests.get(f"{base_url}/orders/{order_id}")
            if response.status_code == 200:
                order = response.json()
                logger.info(f"✅ Order found: {order}")
            else:
                logger.error(f"Order not found: {response.status_code}")
        except Exception as e:
            logger.error(f"Request failed: {e}")
        
        time.sleep(0.5)
    
    # List all orders
    logger.info("\nListing all orders")
    try:
        response = requests.get(f"{base_url}/orders")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Total orders: {data['total']}")
            for order in data['orders']:
                logger.info(f"   - {order['order_id']}: {order['quantity']}x {order['sku']}")
    except Exception as e:
        logger.error(f"Request failed: {e}")

def demo_secure_communication():
    """Demonstrate secure communication features."""
    if not jose_handler:
        logger.info("\n⚠️  JOSE not enabled, skipping secure demo")
        return
    
    server_jid = os.getenv("AZTM_SERVER_JID", "aztmapi@sure.im")
    base_url = f"https://{server_jid.split('@')[0]}.api"
    
    logger.info("\n" + "=" * 60)
    logger.info("Demo: Secure Communication via XMPP")
    logger.info("=" * 60)
    
    # Access secure endpoint
    logger.info("\nAccessing secure endpoint")
    try:
        response = requests.get(f"{base_url}/demo/secure")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"✅ Secure response: {data}")
            
            if 'security' in data:
                sec = data['security']
                logger.info(f"   JOSE enabled: {sec.get('jose_enabled')}")
                logger.info(f"   Signing key: {sec.get('signing_key_id')}")
                logger.info(f"   Encryption key: {sec.get('encryption_key_id')}")
        else:
            logger.error(f"Failed: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Request failed: {e}")

def run_demo_loop():
    """Run continuous demo loop."""
    iteration = 0
    
    while True:
        iteration += 1
        logger.info("\n" + "=" * 60)
        logger.info(f"Demo Iteration #{iteration}")
        logger.info("=" * 60)
        
        try:
            # Run basic tests
            demo_basic_requests()
            
            # Create some orders
            order_ids = demo_create_orders()
            
            # Retrieve orders
            if order_ids:
                demo_retrieve_orders(order_ids)
            
            # Test secure communication
            demo_secure_communication()
            
            # Wait before next iteration
            logger.info("\n" + "=" * 60)
            logger.info("✅ Demo iteration complete!")
            logger.info("All HTTP requests were sent via XMPP transport")
            logger.info("No direct network connection to server required!")
            logger.info("Waiting 30 seconds before next iteration...")
            logger.info("=" * 60)
            
            time.sleep(30)
            
        except KeyboardInterrupt:
            logger.info("\n👋 Demo stopped by user")
            break
        except Exception as e:
            logger.error(f"Demo error: {e}")
            logger.info("Retrying in 10 seconds...")
            time.sleep(10)

def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("AZTM Demo Client Starting")
    logger.info("This client sends HTTP requests via XMPP")
    logger.info("No direct connection to the server!")
    logger.info("=" * 60)
    
    # Initialize AZTM
    initialize_aztm()
    
    # Give XMPP connection time to establish
    logger.info("Waiting for XMPP connection to establish...")
    time.sleep(5)
    
    # Run demo
    run_demo_loop()

if __name__ == "__main__":
    main()