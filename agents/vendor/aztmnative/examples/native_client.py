"""
Example of using AZTM Native Client API.
No HTTP libraries are patched. Messaging is explicit.
"""

import sys
import time
import logging
import aztm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("native_client")

def main():
    # 1. Connect using the native API (no monkey patching)
    # Using 'identity' instead of 'userid' to keep terminology clean
    session = aztm.connect(
        identity="client@connect.mishtamesh.net",
        password="clientpass",
        host="connect.mishtamesh.net",
        port=443,
        secure=True,
        verify=False
    )
    
    logger.info(f"Connected as {session.identity}")
    
    # 2. Register a handler for incoming messages
    def on_notification(context, payload):
        logger.info(f"Received notification from {context['identity']}: {payload}")
        
    session.on("notifications", on_notification)
    
    # 3. Send a fire-and-forget message
    target = "api@connect.mishtamesh.net"
    logger.info(f"Sending greeting to {target}...")
    
    session.send(
        identity=target,
        topic="greetings",
        data={"content": "Hello from native client!", "timestamp": time.time()}
    )
    
    # 4. Make an RPC request (wait for response)
    logger.info("Sending RPC request...")
    try:
        response = session.request(
            identity=target,
            topic="calculator/add",
            data={"a": 10, "b": 20},
            timeout=5.0
        )
        logger.info(f"RPC Response: {response}")
    except Exception as e:
        logger.error(f"RPC failed: {e}")
        
    # Keep alive for a bit to receive notifications
    time.sleep(5)
    
    # 5. Disconnect
    aztm.disconnect()
    logger.info("Disconnected")

if __name__ == "__main__":
    main()
