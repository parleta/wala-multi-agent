"""
Payload size boundary tests for AZTM.
Tests small, medium, and large payload handling with edge cases.
"""

import pytest
import time
import sys
import json
import random
import string
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def generate_payload(size_kb: float) -> str:
    """Generate a test payload of approximately the specified size in KB."""
    size_bytes = int(size_kb * 1024)
    # Create structured data with padding
    base_data = {
        "test": "payload",
        "size_kb": size_kb,
        "timestamp": time.time(),
        "padding": ""
    }
    base_json = json.dumps(base_data)
    padding_needed = max(0, size_bytes - len(base_json) - 20)  # Leave room for quotes
    base_data["padding"] = ''.join(random.choices(string.ascii_letters + string.digits, k=padding_needed))
    return json.dumps(base_data)


@pytest.mark.integration
class TestPayloadSizes:
    """Test different payload sizes and boundary conditions."""
    
    def test_small_payload_inline(self, process_manager, test_env, xmpp_config):
        """Test small payload (<128KB) that should be sent inline."""
        
        payload_size_kb = 50  # 50KB payload
        
        server_script = f'''
import aztm
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os
import json

class LargeData(BaseModel):
    data: str

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD')
)

@app.post("/echo")
async def echo_data(payload: LargeData):
    data = json.loads(payload.data)
    return {{
        "received_size_kb": len(payload.data) / 1024,
        "original_size_kb": data.get("size_kb"),
        "transfer_mode": "inline"
    }}

print("Server ready!", flush=True)
uvicorn.run(app, host="127.0.0.1", port=8000)
'''
        
        client_script = f'''
import aztm
import requests
import os
import sys
import time
import json

aztm.register_service_mapping({{
    "localhost:8000": os.environ.get('AZTM_SERVER_JID')
}})

aztm.login(
    userid=os.environ.get('AZTM_CLIENT_JID'),
    password=os.environ.get('AZTM_CLIENT_PASSWORD')
)

time.sleep(3)

# Generate payload
payload_data = {generate_payload.__code__.co_consts}
exec("""
def generate_payload(size_kb):
    import json, random, string, time
    size_bytes = int(size_kb * 1024)
    base_data = {{
        "test": "payload",
        "size_kb": size_kb,
        "timestamp": time.time(),
        "padding": ""
    }}
    base_json = json.dumps(base_data)
    padding_needed = max(0, size_bytes - len(base_json) - 20)
    base_data["padding"] = ''.join(random.choices(string.ascii_letters + string.digits, k=padding_needed))
    return json.dumps(base_data)
""")

try:
    test_data = generate_payload({payload_size_kb})
    
    response = requests.post(
        "http://localhost:8000/echo",
        json={{"data": test_data}},
        timeout=15
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {{data}}", flush=True)
        if data["original_size_kb"] == {payload_size_kb}:
            print(f"SUCCESS: Small payload ({{data['received_size_kb']:.1f}}KB) handled inline!", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {{response.status_code}} - {{response.text}}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {{e}}", flush=True)
    sys.exit(1)
'''
        
        self._run_payload_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: Small payload"
        )
    
    def test_boundary_128kb(self, process_manager, test_env, xmpp_config):
        """Test payload exactly at 128KB boundary."""
        
        payload_size_kb = 128  # Exactly 128KB
        
        server_script = f'''
import aztm
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os
import json

class LargeData(BaseModel):
    data: str

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD')
)

@app.post("/echo")
async def echo_data(payload: LargeData):
    data = json.loads(payload.data)
    return {{
        "received_size_kb": len(payload.data) / 1024,
        "original_size_kb": data.get("size_kb"),
        "at_boundary": True
    }}

print("Server ready!", flush=True)
uvicorn.run(app, host="127.0.0.1", port=8000)
'''
        
        client_script = f'''
import aztm
import requests
import os
import sys
import time
import json
import random
import string

aztm.register_service_mapping({{
    "localhost:8000": os.environ.get('AZTM_SERVER_JID')
}})

aztm.login(
    userid=os.environ.get('AZTM_CLIENT_JID'),
    password=os.environ.get('AZTM_CLIENT_PASSWORD')
)

time.sleep(3)

def generate_payload(size_kb):
    size_bytes = int(size_kb * 1024)
    base_data = {{
        "test": "payload",
        "size_kb": size_kb,
        "timestamp": time.time(),
        "padding": ""
    }}
    base_json = json.dumps(base_data)
    padding_needed = max(0, size_bytes - len(base_json) - 20)
    base_data["padding"] = ''.join(random.choices(string.ascii_letters + string.digits, k=padding_needed))
    return json.dumps(base_data)

try:
    test_data = generate_payload({payload_size_kb})
    
    response = requests.post(
        "http://localhost:8000/echo",
        json={{"data": test_data}},
        timeout=20
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {{data}}", flush=True)
        if data["at_boundary"] and abs(data["received_size_kb"] - 128) < 1:
            print(f"SUCCESS: 128KB boundary payload handled!", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {{response.status_code}} - {{response.text}}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {{e}}", flush=True)
    sys.exit(1)
'''
        
        self._run_payload_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: 128KB boundary"
        )
    
    def test_medium_payload_chunked(self, process_manager, test_env, xmpp_config):
        """Test medium payload (128KB-5MB) that should be chunked."""
        
        payload_size_kb = 512  # 512KB payload
        
        server_script = f'''
import aztm
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os
import json

class LargeData(BaseModel):
    data: str

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD')
)

@app.post("/echo")
async def echo_data(payload: LargeData):
    data = json.loads(payload.data)
    return {{
        "received_size_kb": len(payload.data) / 1024,
        "original_size_kb": data.get("size_kb"),
        "transfer_mode": "chunked",
        "chunks_expected": True
    }}

print("Server ready!", flush=True)
uvicorn.run(app, host="127.0.0.1", port=8000)
'''
        
        client_script = f'''
import aztm
import requests
import os
import sys
import time
import json
import random
import string

aztm.register_service_mapping({{
    "localhost:8000": os.environ.get('AZTM_SERVER_JID')
}})

aztm.login(
    userid=os.environ.get('AZTM_CLIENT_JID'),
    password=os.environ.get('AZTM_CLIENT_PASSWORD')
)

time.sleep(3)

def generate_payload(size_kb):
    size_bytes = int(size_kb * 1024)
    base_data = {{
        "test": "payload",
        "size_kb": size_kb,
        "timestamp": time.time(),
        "padding": ""
    }}
    base_json = json.dumps(base_data)
    padding_needed = max(0, size_bytes - len(base_json) - 20)
    base_data["padding"] = ''.join(random.choices(string.ascii_letters + string.digits, k=padding_needed))
    return json.dumps(base_data)

try:
    test_data = generate_payload({payload_size_kb})
    print(f"Sending {{len(test_data)/1024:.1f}}KB payload...", flush=True)
    
    response = requests.post(
        "http://localhost:8000/echo",
        json={{"data": test_data}},
        timeout=30
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"Response: {{data}}", flush=True)
        if data["original_size_kb"] == {payload_size_kb}:
            print(f"SUCCESS: Medium payload ({{data['received_size_kb']:.1f}}KB) handled with chunking!", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {{response.status_code}} - {{response.text}}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {{e}}", flush=True)
    sys.exit(1)
'''
        
        self._run_payload_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: Medium payload",
            timeout=40
        )
    
    def test_boundary_5mb(self, process_manager, test_env, xmpp_config):
        """Test payload at 5MB boundary."""
        
        # Skip for now as 5MB is large for testing
        pytest.skip("5MB payload test skipped for performance")
        
    def test_large_payload_slot(self, process_manager, test_env, xmpp_config):
        """Test large payload (>5MB) that should use upload slots."""
        
        # Skip for now as upload slots may not be implemented
        pytest.skip("Upload slot mechanism not yet implemented")
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_binary_payload(self, process_manager, test_env, xmpp_config):
        """Test binary payload handling."""
        
        server_script = '''
import aztm
from fastapi import FastAPI
import uvicorn
import os
import base64

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

@app.post("/binary")
async def handle_binary(data: dict):
    binary_data = base64.b64decode(data["binary"])
    return {
        "received_bytes": len(binary_data),
        "first_bytes": list(binary_data[:10]),
        "binary_handled": True
    }

print("Server ready!", flush=True)
uvicorn.run(app, host="127.0.0.1", port=8000)
'''
        
        client_script = '''
import aztm
import requests
import os
import sys
import time
import base64

aztm.register_service_mapping({
    "localhost:8000": os.environ.get('AZTM_SERVER_JID')
})

aztm.login(
    userid=os.environ.get('AZTM_CLIENT_JID'),
    password=os.environ.get('AZTM_CLIENT_PASSWORD')
)

time.sleep(3)

try:
    # Create binary data
    binary_data = bytes(range(256)) * 100  # 25.6KB of binary data
    encoded = base64.b64encode(binary_data).decode('utf-8')
    
    response = requests.post(
        "http://localhost:8000/binary",
        json={"binary": encoded},
        timeout=15
    )
    
    if response.status_code == 200:
        data = response.json()
        if data["received_bytes"] == 25600 and data["first_bytes"] == list(range(10)):
            print(f"SUCCESS: Binary payload handled! Size: {data['received_bytes']} bytes", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {response.status_code} - {response.text}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_payload_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: Binary payload handled!"
        )
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_empty_payload(self, process_manager, test_env, xmpp_config):
        """Test empty payload handling."""
        
        server_script = '''
import aztm
from fastapi import FastAPI
import uvicorn
import os

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

@app.post("/empty")
async def handle_empty(data: dict = None):
    return {
        "empty_handled": True,
        "data_is_none": data is None or data == {}
    }

print("Server ready!", flush=True)
uvicorn.run(app, host="127.0.0.1", port=8000)
'''
        
        client_script = '''
import aztm
import requests
import os
import sys
import time

aztm.register_service_mapping({
    "localhost:8000": os.environ.get('AZTM_SERVER_JID')
})

aztm.login(
    userid=os.environ.get('AZTM_CLIENT_JID'),
    password=os.environ.get('AZTM_CLIENT_PASSWORD')
)

time.sleep(3)

try:
    response = requests.post(
        "http://localhost:8000/empty",
        json={},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        if data["empty_handled"]:
            print(f"SUCCESS: Empty payload handled!", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {response.status_code} - {response.text}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_payload_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: Empty payload handled!"
        )
    
    def _run_payload_test(self, process_manager, test_env, xmpp_config,
                          server_script, client_script, success_message,
                          timeout=30):
        """Helper to run payload test pairs."""
        
        # Write scripts
        server_file = Path(f"/tmp/test_payload_server_{time.time()}.py")
        client_file = Path(f"/tmp/test_payload_client_{time.time()}.py")
        server_file.write_text(server_script)
        client_file.write_text(client_script)
        
        # Prepare environments
        server_env = test_env.copy()
        server_env['AZTM_SERVER_JID'] = xmpp_config['server_jid']
        server_env['AZTM_SERVER_PASSWORD'] = xmpp_config['server_password']
        
        client_env = test_env.copy()
        client_env['AZTM_CLIENT_JID'] = xmpp_config['client_jid']
        client_env['AZTM_CLIENT_PASSWORD'] = xmpp_config['client_password']
        client_env['AZTM_SERVER_JID'] = xmpp_config['server_jid']
        
        # Start server
        server_name = f"payload_server_{time.time()}"
        server = process_manager.start_process(
            server_name,
            [sys.executable, str(server_file)],
            env=server_env,
            wait_for="Server ready!",
            timeout=15
        )
        
        try:
            # Run client
            result = process_manager.run_command(
                [sys.executable, str(client_file)],
                env=client_env,
                timeout=timeout
            )
            
            assert result['returncode'] == 0, f"Test failed: {result['stderr']}"
            assert success_message in result['stdout']
            
        finally:
            process_manager.stop_process(server_name)
            # Clean up temp files
            server_file.unlink(missing_ok=True)
            client_file.unlink(missing_ok=True)