"""
Error handling tests for AZTM.
Tests error conditions, timeouts, and edge cases.
"""

import pytest
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.mark.integration
class TestErrorHandling:
    """Test error conditions and edge cases."""
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_server_not_available(self, process_manager, test_env, xmpp_config):
        """Test behavior when server is not available."""
        
        client_script = '''
import aztm
import requests
import os
import sys
import time

# Register mapping to a non-existent server
aztm.register_service_mapping({
    "localhost:9999": "nonexistent@test.aztm"
})

aztm.login(
    userid=os.environ.get('AZTM_CLIENT_JID'),
    password=os.environ.get('AZTM_CLIENT_PASSWORD')
)

time.sleep(2)

try:
    response = requests.get(
        "http://localhost:9999/test",
        timeout=5
    )
    print(f"Unexpected success: {response.status_code}", flush=True)
    sys.exit(1)
except requests.exceptions.Timeout:
    print("SUCCESS: Request timed out as expected for unavailable server", flush=True)
    sys.exit(0)
except requests.exceptions.ConnectionError:
    print("SUCCESS: Connection error as expected for unavailable server", flush=True)
    sys.exit(0)
except Exception as e:
    print(f"Unexpected error type: {e}", flush=True)
    sys.exit(1)
'''
        
        client_env = test_env.copy()
        client_env['AZTM_CLIENT_JID'] = xmpp_config['client_jid']
        client_env['AZTM_CLIENT_PASSWORD'] = xmpp_config['client_password']
        
        result = process_manager.run_command(
            [sys.executable, "-c", client_script],
            env=client_env,
            timeout=15
        )
        
        assert result['returncode'] == 0, f"Test failed: {result['stderr']}"
        assert "SUCCESS:" in result['stdout']
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_invalid_jid_mapping(self, process_manager, test_env, xmpp_config):
        """Test behavior with invalid JID mapping."""
        
        client_script = '''
import aztm
import requests
import os
import sys
import time

# Register invalid mapping
aztm.register_service_mapping({
    "localhost:8000": "invalid-jid-format"
})

aztm.login(
    userid=os.environ.get('AZTM_CLIENT_JID'),
    password=os.environ.get('AZTM_CLIENT_PASSWORD')
)

time.sleep(2)

try:
    response = requests.get(
        "http://localhost:8000/test",
        timeout=5
    )
    print(f"Unexpected success: {response.status_code}", flush=True)
    sys.exit(1)
except Exception as e:
    print(f"SUCCESS: Error with invalid JID: {type(e).__name__}", flush=True)
    sys.exit(0)
'''
        
        client_env = test_env.copy()
        client_env['AZTM_CLIENT_JID'] = xmpp_config['client_jid']
        client_env['AZTM_CLIENT_PASSWORD'] = xmpp_config['client_password']
        
        result = process_manager.run_command(
            [sys.executable, "-c", client_script],
            env=client_env,
            timeout=15
        )
        
        assert result['returncode'] == 0, f"Test failed: {result['stderr']}"
        assert "SUCCESS:" in result['stdout']
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_route_not_found(self, process_manager, test_env, xmpp_config):
        """Test 404 route not found handling."""
        
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

@app.get("/existing")
async def existing():
    return {"exists": True}

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
        "http://localhost:8000/nonexistent",
        timeout=10
    )
    
    if response.status_code == 404:
        print("SUCCESS: 404 error handled correctly", flush=True)
        sys.exit(0)
    else:
        print(f"Unexpected status: {response.status_code}", flush=True)
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_error_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: 404 error"
        )
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_malformed_request(self, process_manager, test_env, xmpp_config):
        """Test handling of malformed requests."""
        
        server_script = '''
import aztm
from fastapi import FastAPI
from pydantic import BaseModel, validator
import uvicorn
import os

class StrictModel(BaseModel):
    required_field: str
    number: int
    
    @validator('number')
    def validate_positive(cls, v):
        if v < 0:
            raise ValueError('Must be positive')
        return v

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

@app.post("/strict")
async def strict_endpoint(data: StrictModel):
    return {"accepted": True}

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
    # Send malformed data
    response = requests.post(
        "http://localhost:8000/strict",
        json={"wrong_field": "value", "number": "not_a_number"},
        timeout=10
    )
    
    if response.status_code == 422:  # Unprocessable Entity
        print("SUCCESS: Validation error handled correctly", flush=True)
        sys.exit(0)
    else:
        print(f"Unexpected status: {response.status_code}", flush=True)
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_error_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: Validation error"
        )
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_timeout_handling(self, process_manager, test_env, xmpp_config):
        """Test request timeout handling."""
        
        server_script = '''
import aztm
from fastapi import FastAPI
import uvicorn
import os
import asyncio

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

@app.get("/slow")
async def slow_endpoint():
    await asyncio.sleep(10)  # Sleep longer than client timeout
    return {"too": "late"}

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
        "http://localhost:8000/slow",
        timeout=3  # Short timeout
    )
    print(f"Unexpected success: {response.status_code}", flush=True)
    sys.exit(1)
except requests.exceptions.Timeout:
    print("SUCCESS: Request timeout handled correctly", flush=True)
    sys.exit(0)
except Exception as e:
    print(f"Unexpected error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_error_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: Request timeout"
        )
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_server_error_500(self, process_manager, test_env, xmpp_config):
        """Test 500 internal server error handling."""
        
        server_script = '''
import aztm
from fastapi import FastAPI, HTTPException
import uvicorn
import os

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

@app.get("/error")
async def error_endpoint():
    raise HTTPException(status_code=500, detail="Internal server error")

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
        "http://localhost:8000/error",
        timeout=10
    )
    
    if response.status_code == 500:
        print("SUCCESS: 500 error handled correctly", flush=True)
        sys.exit(0)
    else:
        print(f"Unexpected status: {response.status_code}", flush=True)
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_error_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: 500 error"
        )
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_concurrent_requests(self, process_manager, test_env, xmpp_config):
        """Test handling of concurrent requests."""
        
        server_script = '''
import aztm
from fastapi import FastAPI
import uvicorn
import os
import asyncio

app = FastAPI()
aztm.login(
    userid=os.environ.get('AZTM_SERVER_JID'),
    password=os.environ.get('AZTM_SERVER_PASSWORD', server_mode=True)
)

request_count = 0

@app.get("/concurrent/{id}")
async def concurrent_endpoint(id: int):
    global request_count
    request_count += 1
    await asyncio.sleep(0.1)  # Small delay
    return {
        "id": id,
        "count": request_count
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
import concurrent.futures

aztm.register_service_mapping({
    "localhost:8000": os.environ.get('AZTM_SERVER_JID')
})

aztm.login(
    userid=os.environ.get('AZTM_CLIENT_JID'),
    password=os.environ.get('AZTM_CLIENT_PASSWORD')
)

time.sleep(3)

def make_request(i):
    try:
        response = requests.get(
            f"http://localhost:8000/concurrent/{i}",
            timeout=10
        )
        return response.status_code == 200 and response.json()["id"] == i
    except Exception as e:
        print(f"Request {i} failed: {e}", flush=True)
        return False

try:
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(make_request, i) for i in range(10)]
        results = [f.result() for f in futures]
    
    if all(results):
        print("SUCCESS: All concurrent requests handled correctly", flush=True)
        sys.exit(0)
    else:
        print(f"Some requests failed: {results}", flush=True)
        sys.exit(1)
except Exception as e:
    print(f"Error: {e}", flush=True)
    sys.exit(1)
'''
        
        self._run_error_test(
            process_manager, test_env, xmpp_config,
            server_script, client_script,
            "SUCCESS: All concurrent requests",
            timeout=30
        )
    
    def _run_error_test(self, process_manager, test_env, xmpp_config,
                        server_script, client_script, success_message,
                        timeout=20):
        """Helper to run error test pairs."""
        
        # Write scripts
        server_file = Path(f"/tmp/test_error_server_{time.time()}.py")
        client_file = Path(f"/tmp/test_error_client_{time.time()}.py")
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
        
        # Start server if script is provided
        server_name = None
        if server_script:
            server_name = f"error_server_{time.time()}"
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
            if server_name:
                process_manager.stop_process(server_name)
            # Clean up temp files
            server_file.unlink(missing_ok=True)
            client_file.unlink(missing_ok=True)