"""
Performance regression tests for AZTM.
Tests throughput, latency, and concurrent request handling.
"""

import pytest
import time
import sys
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.mark.performance
@pytest.mark.integration
class TestPerformance:
    """Performance regression tests."""
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_latency_simple_request(self, process_manager, test_env, xmpp_config, performance_tracker):
        """Measure latency for simple requests."""
        
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

@app.get("/ping")
async def ping():
    return {"pong": True}

print("Server ready!", flush=True)
uvicorn.run(app, host="127.0.0.1", port=8000)
'''
        
        client_script = '''
import aztm
import requests
import os
import sys
import time
import statistics

aztm.register_service_mapping({
    "localhost:8000": os.environ.get('AZTM_SERVER_JID')
})

aztm.login(
    userid=os.environ.get('AZTM_CLIENT_JID'),
    password=os.environ.get('AZTM_CLIENT_PASSWORD')
)

time.sleep(3)

# Warm up
for _ in range(3):
    requests.get("http://localhost:8000/ping", timeout=10)

# Measure latency
latencies = []
for i in range(20):
    start = time.time()
    try:
        response = requests.get("http://localhost:8000/ping", timeout=10)
        if response.status_code == 200:
            latencies.append((time.time() - start) * 1000)  # Convert to ms
    except Exception as e:
        print(f"Request failed: {e}", flush=True)

if latencies:
    avg_latency = statistics.mean(latencies)
    p50 = statistics.median(latencies)
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) > 19 else max(latencies)
    
    print(f"SUCCESS: Latency - Avg: {avg_latency:.2f}ms, P50: {p50:.2f}ms, P95: {p95:.2f}ms", flush=True)
    print(f"METRICS: {','.join([str(l) for l in latencies])}", flush=True)
    sys.exit(0)
else:
    print("No successful requests", flush=True)
    sys.exit(1)
'''
        
        # Run test
        server_env = test_env.copy()
        server_env['AZTM_SERVER_JID'] = xmpp_config['server_jid']
        server_env['AZTM_SERVER_PASSWORD'] = xmpp_config['server_password']
        
        client_env = test_env.copy()
        client_env['AZTM_CLIENT_JID'] = xmpp_config['client_jid']
        client_env['AZTM_CLIENT_PASSWORD'] = xmpp_config['client_password']
        client_env['AZTM_SERVER_JID'] = xmpp_config['server_jid']
        
        server_file = Path(f"/tmp/perf_server_{time.time()}.py")
        client_file = Path(f"/tmp/perf_client_{time.time()}.py")
        server_file.write_text(server_script)
        client_file.write_text(client_script)
        
        server_name = f"perf_server_{time.time()}"
        server = process_manager.start_process(
            server_name,
            [sys.executable, str(server_file)],
            env=server_env,
            wait_for="Server ready!",
            timeout=15
        )
        
        try:
            result = process_manager.run_command(
                [sys.executable, str(client_file)],
                env=client_env,
                timeout=40
            )
            
            assert result['returncode'] == 0, f"Test failed: {result['stderr']}"
            assert "SUCCESS:" in result['stdout']
            
            # Extract metrics
            for line in result['stdout'].split('\n'):
                if "METRICS:" in line:
                    metrics = [float(m) for m in line.split("METRICS:")[1].strip().split(',')]
                    avg_latency = statistics.mean(metrics)
                    performance_tracker.record("simple_request_latency", avg_latency, unit="ms")
                    
                    # Check performance regression (example threshold)
                    baseline = performance_tracker.get_baseline("simple_request_latency")
                    if baseline and avg_latency > baseline * 1.5:
                        pytest.warning(f"Performance regression detected: {avg_latency}ms vs baseline {baseline}ms")
                    
        finally:
            process_manager.stop_process(server_name)
            server_file.unlink(missing_ok=True)
            client_file.unlink(missing_ok=True)
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_throughput_small_payloads(self, process_manager, test_env, xmpp_config, performance_tracker):
        """Measure throughput for small payloads."""
        
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

@app.post("/echo")
async def echo(data: dict):
    return data

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

# Test throughput with 1KB payloads
payload = {"data": "x" * 1024}  # 1KB payload
num_requests = 50
successful = 0

start = time.time()
for i in range(num_requests):
    try:
        response = requests.post(
            "http://localhost:8000/echo",
            json=payload,
            timeout=10
        )
        if response.status_code == 200:
            successful += 1
    except Exception as e:
        print(f"Request {i} failed: {e}", flush=True)

duration = time.time() - start
throughput = successful / duration if duration > 0 else 0

print(f"SUCCESS: Throughput - {throughput:.2f} requests/sec ({successful}/{num_requests} successful)", flush=True)
print(f"METRICS: throughput={throughput},successful={successful},duration={duration}", flush=True)
sys.exit(0)
'''
        
        # Run test
        server_env = test_env.copy()
        server_env['AZTM_SERVER_JID'] = xmpp_config['server_jid']
        server_env['AZTM_SERVER_PASSWORD'] = xmpp_config['server_password']
        
        client_env = test_env.copy()
        client_env['AZTM_CLIENT_JID'] = xmpp_config['client_jid']
        client_env['AZTM_CLIENT_PASSWORD'] = xmpp_config['client_password']
        client_env['AZTM_SERVER_JID'] = xmpp_config['server_jid']
        
        server_file = Path(f"/tmp/throughput_server_{time.time()}.py")
        client_file = Path(f"/tmp/throughput_client_{time.time()}.py")
        server_file.write_text(server_script)
        client_file.write_text(client_script)
        
        server_name = f"throughput_server_{time.time()}"
        server = process_manager.start_process(
            server_name,
            [sys.executable, str(server_file)],
            env=server_env,
            wait_for="Server ready!",
            timeout=15
        )
        
        try:
            result = process_manager.run_command(
                [sys.executable, str(client_file)],
                env=client_env,
                timeout=60
            )
            
            assert result['returncode'] == 0, f"Test failed: {result['stderr']}"
            assert "SUCCESS:" in result['stdout']
            
            # Extract metrics
            for line in result['stdout'].split('\n'):
                if "METRICS:" in line:
                    metrics_str = line.split("METRICS:")[1].strip()
                    metrics = {}
                    for metric in metrics_str.split(','):
                        k, v = metric.split('=')
                        metrics[k] = float(v)
                    
                    performance_tracker.record(
                        "throughput_small_payloads",
                        metrics.get('throughput', 0),
                        unit="req/sec",
                        payload_size="1KB"
                    )
                    
        finally:
            process_manager.stop_process(server_name)
            server_file.unlink(missing_ok=True)
            client_file.unlink(missing_ok=True)
    
    @pytest.mark.slow
    def test_memory_leak_detection(self, process_manager, test_env, xmpp_config):
        """Test for memory leaks with repeated operations."""
        
        # Skip for now as it requires memory profiling
        pytest.skip("Memory leak detection requires additional profiling tools")
    
    @pytest.mark.skip("TODO: Fix edge case - see issue #3")
    def test_concurrent_connections(self, process_manager, test_env, xmpp_config, performance_tracker):
        """Test performance with concurrent connections."""
        
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

active_requests = 0
max_concurrent = 0

@app.get("/concurrent")
async def concurrent():
    global active_requests, max_concurrent
    active_requests += 1
    max_concurrent = max(max_concurrent, active_requests)
    await asyncio.sleep(0.05)  # Simulate some work
    active_requests -= 1
    return {"ok": True, "max_concurrent": max_concurrent}

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
        response = requests.get("http://localhost:8000/concurrent", timeout=10)
        return response.status_code == 200
    except Exception as e:
        return False

# Test with different concurrency levels
for workers in [5, 10, 20]:
    successful = 0
    start = time.time()
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(make_request, i) for i in range(workers * 5)]
        results = [f.result() for f in futures]
        successful = sum(results)
    
    duration = time.time() - start
    throughput = successful / duration if duration > 0 else 0
    
    print(f"Workers={workers}: {throughput:.2f} req/sec ({successful}/{len(results)} successful)", flush=True)

print(f"SUCCESS: Concurrent connection test completed", flush=True)
sys.exit(0)
'''
        
        # Run test
        server_env = test_env.copy()
        server_env['AZTM_SERVER_JID'] = xmpp_config['server_jid']
        server_env['AZTM_SERVER_PASSWORD'] = xmpp_config['server_password']
        
        client_env = test_env.copy()
        client_env['AZTM_CLIENT_JID'] = xmpp_config['client_jid']
        client_env['AZTM_CLIENT_PASSWORD'] = xmpp_config['client_password']
        client_env['AZTM_SERVER_JID'] = xmpp_config['server_jid']
        
        server_file = Path(f"/tmp/concurrent_server_{time.time()}.py")
        client_file = Path(f"/tmp/concurrent_client_{time.time()}.py")
        server_file.write_text(server_script)
        client_file.write_text(client_script)
        
        server_name = f"concurrent_server_{time.time()}"
        server = process_manager.start_process(
            server_name,
            [sys.executable, str(server_file)],
            env=server_env,
            wait_for="Server ready!",
            timeout=15
        )
        
        try:
            result = process_manager.run_command(
                [sys.executable, str(client_file)],
                env=client_env,
                timeout=90
            )
            
            assert result['returncode'] == 0, f"Test failed: {result['stderr']}"
            assert "SUCCESS:" in result['stdout']
            
            # Record performance metrics
            performance_tracker.record(
                "concurrent_connections_test",
                1.0,
                test_type="concurrent",
                workers="5,10,20"
            )
            
        finally:
            process_manager.stop_process(server_name)
            server_file.unlink(missing_ok=True)
            client_file.unlink(missing_ok=True)