"""
Pytest configuration and fixtures for AZTM regression tests.
Provides infrastructure for running client and server in separate processes.
"""

import pytest
import os
import sys
import time
import signal
import socket
import subprocess
import tempfile
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Generator, Tuple
from contextlib import contextmanager

# Add parent directory to path so we can import aztm
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger = logging.getLogger(__name__)


def find_free_port() -> int:
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


# Docker fixtures removed - using sure.im directly


@pytest.fixture
def xmpp_config():
    """Get XMPP server configuration for tests using real AZTM accounts."""
    return {
        'host': 'sure.im',
        'port': 5222,
        'domain': 'sure.im',
        'client_jid': 'aztmclient@sure.im',
        'client_password': '12345678',
        'server_jid': 'aztmapi@sure.im', 
        'server_password': '12345678',
    }


@pytest.fixture
def process_manager():
    """Manage subprocess lifecycle for tests."""
    from tests.regression.utils.process_manager import ProcessManager
    manager = ProcessManager()
    yield manager
    manager.cleanup_all()


@pytest.fixture
def test_env(xmpp_config, tmp_path) -> Dict[str, str]:
    """Create environment variables for test processes."""
    return {
        **os.environ.copy(),
        'AZTM_HOST': xmpp_config['host'],
        'AZTM_PORT': str(xmpp_config['port']),
        'AZTM_DOMAIN': xmpp_config['domain'],
        'AZTM_LOG_LEVEL': 'DEBUG',
        'AZTM_TEST_MODE': '1',
        'AZTM_TIMEOUT': '10',
        'PYTHONPATH': str(Path(__file__).parent.parent.parent),
        'AZTM_LOG_DIR': str(tmp_path / 'logs'),
    }


@pytest.fixture
def server_process(process_manager, test_env, xmpp_config):
    """Start a test server in a subprocess."""
    script = Path(__file__).parent / 'test_server.py'
    
    # Create test server script if it doesn't exist
    if not script.exists():
        script.write_text('''
import aztm
from fastapi import FastAPI
import uvicorn
import sys
import os

app = FastAPI()

# Get config from environment
jid = os.environ.get('AZTM_SERVER_JID', 'testserver@test.aztm')
password = os.environ.get('AZTM_SERVER_PASSWORD', 'server123')

print(f"Starting test server with JID: {jid}", flush=True)

# Login to XMPP
aztm.login(userid=jid, password=password, server_mode=True)

@app.get("/health")
async def health():
    return {"status": "ok", "transport": "xmpp"}

@app.post("/echo")
async def echo(data: dict):
    return {"echo": data, "transport": "xmpp"}

@app.get("/test/{item_id}")
async def get_item(item_id: int):
    return {"item_id": item_id, "name": f"Item {item_id}"}

if __name__ == "__main__":
    print("Test server ready!", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=8000)
''')
    
    # Add server credentials to env
    env = test_env.copy()
    env['AZTM_SERVER_JID'] = xmpp_config['server_jid']
    env['AZTM_SERVER_PASSWORD'] = xmpp_config['server_password']
    
    # Start server process
    proc = process_manager.start_process(
        'server',
        [sys.executable, str(script)],
        env=env,
        wait_for="Test server ready!",
        timeout=30
    )
    
    yield proc
    
    process_manager.stop_process('server')


@pytest.fixture
def client_env(test_env, xmpp_config):
    """Environment for client processes."""
    env = test_env.copy()
    env['AZTM_CLIENT_JID'] = xmpp_config['client_jid']
    env['AZTM_CLIENT_PASSWORD'] = xmpp_config['client_password']
    env['AZTM_SERVER_JID'] = xmpp_config['server_jid']
    return env


@pytest.fixture(autouse=True)
def test_timeout():
    """Apply timeout to all tests to prevent hanging."""
    import threading
    
    def timeout_handler():
        time.sleep(60)  # 60 second timeout
        pytest.fail("Test timeout after 60 seconds")
    
    timer = threading.Timer(60, timeout_handler)
    timer.start()
    yield
    timer.cancel()


@pytest.fixture
def mock_xmpp_client():
    """Provide a mock XMPP client for unit tests."""
    from unittest.mock import Mock, AsyncMock
    
    client = Mock()
    client.connected = Mock()
    client.connected.is_set = Mock(return_value=True)
    client.boundjid = Mock()
    client.boundjid.domain = "test.aztm"
    client.send_message = AsyncMock()
    client.register_handler = Mock()
    
    return client


@contextmanager
def temporary_service_mapping(mappings: Dict[str, str]):
    """Temporarily register service mappings for tests."""
    import aztm
    original = getattr(aztm, '_service_mappings', {}).copy()
    try:
        aztm.register_service_mapping(mappings)
        yield
    finally:
        # Restore original mappings
        aztm._service_mappings = original


@pytest.fixture
def performance_tracker(tmp_path):
    """Track performance metrics across test runs."""
    metrics_file = tmp_path / 'performance_metrics.json'
    
    class PerformanceTracker:
        def __init__(self):
            self.metrics = []
        
        def record(self, name: str, duration: float, **kwargs):
            self.metrics.append({
                'name': name,
                'duration': duration,
                'timestamp': time.time(),
                **kwargs
            })
        
        def save(self):
            with open(metrics_file, 'w') as f:
                json.dump(self.metrics, f, indent=2)
        
        def get_baseline(self, name: str) -> Optional[float]:
            """Get baseline performance for comparison."""
            for metric in self.metrics:
                if metric['name'] == name:
                    return metric['duration']
            return None
    
    tracker = PerformanceTracker()
    yield tracker
    tracker.save()


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test requiring Docker"
    )
    config.addinivalue_line(
        "markers", "performance: mark test as performance regression test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "mock: mark test as using mocked components"
    )


def pytest_collection_modifyitems(config, items):
    """Automatically mark tests based on their location."""
    for item in items:
        # Add markers based on test file name
        if "mock" in item.nodeid:
            item.add_marker(pytest.mark.mock)
        if "performance" in item.nodeid:
            item.add_marker(pytest.mark.performance)
        if "integration" in item.nodeid or "e2e" in item.nodeid:
            item.add_marker(pytest.mark.integration)