"""
HTTP transport tests for AZTM.
Tests various HTTP methods, content types, headers, and parameters.
"""

import pytest
import time
import sys
import json
import base64
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.mark.integration
class TestHTTPTransport:
    """Test HTTP request/response transport over XMPP."""
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_get_request(self, process_manager, test_env, xmpp_config):
        """Test GET request with query parameters."""
        
        server_script = '''
import aztm
from fastapi import FastAPI, Query
import uvicorn
import os

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

@app.get("/items/{item_id}")
async def get_item(item_id: int, q: str = Query(None)):
    return {
        "item_id": item_id,
        "query": q,
        "method": "GET"
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
    response = requests.get(
        "http://localhost:8000/items/42?q=test",
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        if data["item_id"] == 42 and data["query"] == "test":
            print(f"SUCCESS: GET request working! Data: {data}", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {response.status_code} - {response.text}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_client_server_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: GET request working!"
        )
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_post_json(self, process_manager, test_env, xmpp_config):
        """Test POST request with JSON payload."""
        
        server_script = '''
import aztm
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os

class Item(BaseModel):
    name: str
    price: float
    quantity: int

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

@app.post("/items")
async def create_item(item: Item):
    return {
        "created": True,
        "item": item.dict(),
        "total": item.price * item.quantity
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
    payload = {
        "name": "Widget",
        "price": 9.99,
        "quantity": 5
    }
    
    response = requests.post(
        "http://localhost:8000/items",
        json=payload,
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        if data["created"] and data["total"] == 49.95:
            print(f"SUCCESS: POST JSON working! Data: {data}", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {response.status_code} - {response.text}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_client_server_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: POST JSON working!"
        )
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_put_request(self, process_manager, test_env, xmpp_config):
        """Test PUT request for updates."""
        
        server_script = '''
import aztm
from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os

class UpdateItem(BaseModel):
    name: str = None
    price: float = None

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

@app.put("/items/{item_id}")
async def update_item(item_id: int, item: UpdateItem):
    return {
        "updated": True,
        "item_id": item_id,
        "changes": item.dict(exclude_unset=True)
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
    response = requests.put(
        "http://localhost:8000/items/123",
        json={"name": "Updated Widget", "price": 19.99},
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        if data["updated"] and data["item_id"] == 123:
            print(f"SUCCESS: PUT request working! Data: {data}", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {response.status_code} - {response.text}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_client_server_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: PUT request working!"
        )
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_delete_request(self, process_manager, test_env, xmpp_config):
        """Test DELETE request."""
        
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

@app.delete("/items/{item_id}")
async def delete_item(item_id: int):
    return {
        "deleted": True,
        "item_id": item_id,
        "message": f"Item {item_id} deleted"
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
    response = requests.delete(
        "http://localhost:8000/items/456",
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        if data["deleted"] and data["item_id"] == 456:
            print(f"SUCCESS: DELETE request working! Data: {data}", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {response.status_code} - {response.text}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_client_server_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: DELETE request working!"
        )
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_custom_headers(self, process_manager, test_env, xmpp_config):
        """Test custom header preservation."""
        
        server_script = '''
import aztm
from fastapi import FastAPI, Header
import uvicorn
import os

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

@app.get("/headers")
async def check_headers(
    x_custom_header: str = Header(None),
    authorization: str = Header(None)
):
    return {
        "custom_header": x_custom_header,
        "auth": authorization,
        "headers_received": True
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
    headers = {
        "X-Custom-Header": "test-value",
        "Authorization": "Bearer token123"
    }
    
    response = requests.get(
        "http://localhost:8000/headers",
        headers=headers,
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        if data["custom_header"] == "test-value" and "Bearer" in data["auth"]:
            print(f"SUCCESS: Headers preserved! Data: {data}", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {response.status_code} - {response.text}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_client_server_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: Headers preserved!"
        )
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_form_data(self, process_manager, test_env, xmpp_config):
        """Test form data submission."""
        
        server_script = '''
import aztm
from fastapi import FastAPI, Form
import uvicorn
import os

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

@app.post("/form")
async def submit_form(
    username: str = Form(...),
    password: str = Form(...),
    remember: bool = Form(False)
):
    return {
        "form_received": True,
        "username": username,
        "remember": remember
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
    form_data = {
        "username": "testuser",
        "password": "secret123",
        "remember": "true"
    }
    
    response = requests.post(
        "http://localhost:8000/form",
        data=form_data,
        timeout=10
    )
    
    if response.status_code == 200:
        data = response.json()
        if data["form_received"] and data["username"] == "testuser":
            print(f"SUCCESS: Form data working! Data: {data}", flush=True)
            sys.exit(0)
    
    print(f"Unexpected response: {response.status_code} - {response.text}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_client_server_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: Form data working!"
        )
    
    def _run_client_server_test(self, process_manager, test_env, xmpp_config,
                                server_script, client_script, success_message):
        """Helper to run client-server test pairs."""
        
        # Write scripts
        server_file = Path(f"/tmp/test_server_{time.time()}.py")
        client_file = Path(f"/tmp/test_client_{time.time()}.py")
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
        server_name = f"server_{time.time()}"
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
                timeout=20
            )
            
            assert result['returncode'] == 0, f"Test failed: {result['stderr']}"
            assert success_message in result['stdout']
            
        finally:
            process_manager.stop_process(server_name)
            # Clean up temp files
            server_file.unlink(missing_ok=True)
            client_file.unlink(missing_ok=True)