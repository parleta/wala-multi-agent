"""
Debug test to understand CI failures.
Minimal test that captures and shows actual error messages.
"""

import pytest
import sys
import subprocess
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.mark.integration
class TestCIDebug:
    """Debug tests for CI issues."""
    
    def test_server_startup_debug(self):
        """Debug server startup issues in CI."""
        
        # Very simple server script that shows any import/startup errors
        server_script = '''
import sys
import os

print(f"Python: {sys.version}", flush=True)
print(f"Path: {sys.path}", flush=True)
print(f"SERVER_JID: {os.environ.get('AZTM_SERVER_JID', 'NOT SET')}", flush=True)

try:
    import aztm
    print("✓ aztm imported", flush=True)
except Exception as e:
    print(f"✗ Failed to import aztm: {e}", flush=True)
    sys.exit(1)

try:
    from fastapi import FastAPI
    print("✓ FastAPI imported", flush=True)
except Exception as e:
    print(f"✗ Failed to import FastAPI: {e}", flush=True)
    sys.exit(1)

try:
    import uvicorn
    print("✓ uvicorn imported", flush=True)
except Exception as e:
    print(f"✗ Failed to import uvicorn: {e}", flush=True)
    sys.exit(1)

# Try to create app
try:
    app = FastAPI()
    print("✓ FastAPI app created", flush=True)
except Exception as e:
    print(f"✗ Failed to create FastAPI app: {e}", flush=True)
    sys.exit(1)

# Try to login
jid = os.environ.get('AZTM_SERVER_JID', 'aztmapi@sure.im')
password = os.environ.get('AZTM_SERVER_PASSWORD', '12345678')

print(f"Attempting login as {jid}...", flush=True)

try:
    aztm.login(userid=jid, password=password, server_mode=True)
    print("✓ Login successful!", flush=True)
except Exception as e:
    print(f"✗ Login failed: {e}", flush=True)
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("All imports and login successful!", flush=True)
'''
        
        # Write script
        script_file = Path("/tmp/test_debug_server.py")
        script_file.write_text(server_script)
        
        # Prepare environment
        env = os.environ.copy()
        env['PYTHONPATH'] = str(Path(__file__).parent.parent.parent)
        env['AZTM_SERVER_JID'] = os.environ.get('AZTM_SERVER_JID', 'aztmapi@sure.im')
        env['AZTM_SERVER_PASSWORD'] = os.environ.get('AZTM_SERVER_PASSWORD', '12345678')
        
        # Run the script and capture all output
        result = subprocess.run(
            [sys.executable, str(script_file)],
            env=env,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print("=== STDOUT ===")
        print(result.stdout)
        print("=== STDERR ===")
        print(result.stderr)
        print(f"=== EXIT CODE: {result.returncode} ===")
        
        # Provide detailed error info
        if result.returncode != 0:
            pytest.fail(f"Server startup failed. Exit code: {result.returncode}\n"
                       f"STDOUT:\n{result.stdout}\n\n"
                       f"STDERR:\n{result.stderr}")