import asyncio
import logging
from slixmpp import ClientXMPP

class WalaAgent(ClientXMPP):
    def __init__(self, jid, password):
        super().__init__(jid, password)

        # Register event handlers
        self.add_event_handler("session_start", self.start)
        self.add_event_handler("message", self.message)

    async def start(self, event):
        """
        Triggered when the agent successfully connects.
        We must broadcast 'presence' so others know we are online.
        """
        self.send_presence()
        print(f"Wala Agent connected as: {self.boundjid}")

    def message(self, msg):
        """
        Triggered whenever a message is received.
        """
        if msg['type'] in ('chat', 'normal'):
            # This is where your AI logic (LangGraph/Wala) would go
            reply_text = f"Wala Agent received: {msg['body']}"
            
            msg.reply(reply_text).send()
            print(f"Replied to {msg['from']}: {reply_text}")

async def run_agent():
    # Use the local IP of your PC and the user you created in Prosody
    # Format: user@ip_address
    jid = "wala_agent@192.168.1.15" 
    password = "your_password"

    xmpp = WalaAgent(jid, password)

    # If your local server uses a self-signed cert, we disable verification
    xmpp.ca_certs = None 

    # Connect to the local server
    # address=('127.0.0.1', 5222) ensures it looks at your local machine
    await xmpp.connect_async(address=('127.0.0.1', 5222))
    await xmpp.process(forever=True)

if __name__ == '__main__':
    # Setup logging for debugging
    logging.basicConfig(level=logging.INFO, format='%(levelname)-8s %(message)s')
    
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("Agent stopped.")