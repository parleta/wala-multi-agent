"""
Example of using AZTM Native Server API.
Receives messages and RPC requests without patching HTTP libraries.
"""

import sys
import time
import logging
import aztm

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("native_server")

def main():
    # 1. Connect (Server Mode is implied by usage, but connect() handles it)
    session = aztm.connect(
        identity="api@connect.mishtamesh.net",
        password="apipass",
        host="connect.mishtamesh.net",
        port=443,
        secure=True,
        verify=False,
        route_weight=100,
    )
    
    logger.info(f"Server listening as {session.identity}")

    # 2. Handle generic greetings
    def on_greeting(context, payload):
        sender = context['identity']
        logger.info(f"Greeting from {sender}: {payload}")
        
        # Send a notification back
        session.send(
            identity=sender,
            topic="notifications",
            data=f"Welcome {sender}, I received your greeting!"
        )
        
    session.on("greetings", on_greeting)
    
    # 3. Handle RPC requests (Calculator)
    def on_add(context, payload):
        logger.info(f"RPC Request 'add' from {context['identity']}: {payload}")
        a = payload.get("a", 0)
        b = payload.get("b", 0)
        return {"result": a + b}
        
    session.on("calculator/add", on_add)
    
    # 4. Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        aztm.disconnect()

if __name__ == "__main__":
    main()
