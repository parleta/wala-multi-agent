#!/usr/bin/env python3
"""
Diagnostic script to understand why messages aren't being received
"""
import sys
import time
import json
import logging
sys.path.insert(0, '/Users/eladrave/git/aztm')

# Enable DEBUG logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

import aztm
from aztm.core.auth import get_client, get_jid
from aztm.protocol.message import create_request_envelope

print("=" * 60)
print("DIAGNOSTIC TEST")
print("=" * 60)

# Test 1: Connect as server and check handler registration
print("\n1. Testing server mode with handler registration...")
aztm.login(
    userid="aztmapi@sure.im", 
    password="12345678",
    server_mode=True  # Server mode - no HTTP patching
)
print(f"✅ Connected as: {get_jid()}")

server_client = get_client()

# Check what handlers are registered
print(f"\n2. Checking registered handlers...")
if hasattr(server_client, '_message_handlers'):
    print(f"   Message handlers: {list(server_client._message_handlers.keys())}")
else:
    print(f"   ❌ No _message_handlers attribute!")

# Check event handlers
if hasattr(server_client, '_BaseXMPP__event_handlers'):
    handlers = server_client._BaseXMPP__event_handlers
    print(f"   Event handlers: {list(handlers.keys())[:10]}...")  # First 10
    if 'message' in handlers:
        print(f"   'message' event has {len(handlers['message'])} handler(s)")
else:
    print(f"   No event handlers found")

# Add a simple test handler
print(f"\n3. Adding test handler...")
def test_handler(msg):
    print(f"TEST HANDLER RECEIVED: {msg['from']}")

if hasattr(server_client, 'register_message_handler'):
    server_client.register_message_handler('test', test_handler)
    print(f"   ✅ Test handler registered")
    print(f"   Message handlers now: {list(server_client._message_handlers.keys())}")
else:
    print(f"   ❌ No register_message_handler method!")

# Test self-messaging
print(f"\n4. Testing self-message (should work)...")
server_client.send_message(
    mto="aztmapi@sure.im",
    mbody="Test message",
    msubject="test"
)
print(f"   Message sent to self")

# Wait for processing
time.sleep(2)

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
print("\nKey findings:")
print("- Handler registration method exists:", hasattr(server_client, 'register_message_handler'))
print("- Message handlers dict exists:", hasattr(server_client, '_message_handlers'))
print("- Can send messages:", hasattr(server_client, 'send_message'))
print("\nIf the test handler didn't fire, the issue is in message routing/receiving.")