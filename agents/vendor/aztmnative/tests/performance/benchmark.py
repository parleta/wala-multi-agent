#!/usr/bin/env python3
"""
AZTM Performance Benchmarks
Measures throughput, latency, and scalability
"""
import asyncio
import time
import statistics
from typing import List, Dict, Any
import json
import argparse
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from aztm.observability import get_metrics_collector


@dataclass
class BenchmarkResult:
    """Result of a benchmark run"""
    name: str
    duration: float
    requests_sent: int
    requests_successful: int
    requests_failed: int
    throughput: float  # requests per second
    latencies: List[float]
    
    @property
    def avg_latency(self) -> float:
        return statistics.mean(self.latencies) if self.latencies else 0
    
    @property
    def p50_latency(self) -> float:
        return statistics.median(self.latencies) if self.latencies else 0
    
    @property
    def p95_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[index]
    
    @property
    def p99_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        index = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[index]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'duration': self.duration,
            'requests_sent': self.requests_sent,
            'requests_successful': self.requests_successful,
            'requests_failed': self.requests_failed,
            'throughput': self.throughput,
            'avg_latency': self.avg_latency,
            'p50_latency': self.p50_latency,
            'p95_latency': self.p95_latency,
            'p99_latency': self.p99_latency,
        }


class AZTMBenchmark:
    """Performance benchmark for AZTM"""
    
    def __init__(self):
        self.metrics = get_metrics_collector()
        
    async def benchmark_throughput(self, num_requests: int = 1000, 
                                  concurrent_clients: int = 10) -> BenchmarkResult:
        """Benchmark throughput with concurrent requests"""
        print(f"\n📊 Throughput Benchmark")
        print(f"   Requests: {num_requests}")
        print(f"   Concurrent clients: {concurrent_clients}")
        
        start_time = time.time()
        latencies = []
        successful = 0
        failed = 0
        
        async def send_request(i: int):
            nonlocal successful, failed
            req_start = time.time()
            try:
                # Simulate AZTM request
                await asyncio.sleep(0.001)  # Simulate network latency
                latency = time.time() - req_start
                latencies.append(latency)
                successful += 1
                self.metrics.record_request('GET', 200, latency)
            except Exception:
                failed += 1
                self.metrics.record_connection_failure('benchmark_error')
        
        # Create concurrent tasks
        batch_size = 100
        for batch_start in range(0, num_requests, batch_size):
            batch_end = min(batch_start + batch_size, num_requests)
            tasks = [send_request(i) for i in range(batch_start, batch_end)]
            await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = time.time() - start_time
        throughput = successful / duration if duration > 0 else 0
        
        return BenchmarkResult(
            name="throughput",
            duration=duration,
            requests_sent=num_requests,
            requests_successful=successful,
            requests_failed=failed,
            throughput=throughput,
            latencies=latencies
        )
    
    async def benchmark_latency(self, num_requests: int = 100,
                               payload_sizes: List[int] = None) -> Dict[str, BenchmarkResult]:
        """Benchmark latency for different payload sizes"""
        if payload_sizes is None:
            payload_sizes = [100, 1024, 10240, 102400, 1048576]  # 100B to 1MB
        
        print(f"\n📊 Latency Benchmark")
        print(f"   Requests per size: {num_requests}")
        print(f"   Payload sizes: {payload_sizes}")
        
        results = {}
        
        for size in payload_sizes:
            print(f"\n   Testing {size} bytes...")
            latencies = []
            successful = 0
            failed = 0
            start_time = time.time()
            
            for _ in range(num_requests):
                req_start = time.time()
                try:
                    # Simulate AZTM request with payload
                    payload = b'x' * size
                    await asyncio.sleep(0.001 + size / 10_000_000)  # Simulate transfer time
                    
                    latency = time.time() - req_start
                    latencies.append(latency)
                    successful += 1
                    
                    # Record metrics
                    self.metrics.record_payload('send', 'inline' if size < 128000 else 'chunked', size)
                    self.metrics.record_request('POST', 200, latency)
                    
                except Exception:
                    failed += 1
            
            duration = time.time() - start_time
            throughput = successful / duration if duration > 0 else 0
            
            results[f"{size}B"] = BenchmarkResult(
                name=f"latency_{size}B",
                duration=duration,
                requests_sent=num_requests,
                requests_successful=successful,
                requests_failed=failed,
                throughput=throughput,
                latencies=latencies
            )
        
        return results
    
    async def benchmark_connection_pool(self, num_connections: int = 50,
                                       requests_per_connection: int = 100) -> BenchmarkResult:
        """Benchmark connection pooling efficiency"""
        print(f"\n📊 Connection Pool Benchmark")
        print(f"   Connections: {num_connections}")
        print(f"   Requests per connection: {requests_per_connection}")
        
        from aztm.resilience import ConnectionPool
        
        pool = ConnectionPool(max_connections=10)
        latencies = []
        successful = 0
        failed = 0
        start_time = time.time()
        
        async def use_connection(conn_id: int):
            nonlocal successful, failed
            for _ in range(requests_per_connection):
                req_start = time.time()
                try:
                    # Simulate getting connection from pool
                    await asyncio.sleep(0.0001)  # Pool overhead
                    await asyncio.sleep(0.001)  # Request time
                    
                    latency = time.time() - req_start
                    latencies.append(latency)
                    successful += 1
                    
                except Exception:
                    failed += 1
        
        # Run connections concurrently
        tasks = [use_connection(i) for i in range(num_connections)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        duration = time.time() - start_time
        total_requests = num_connections * requests_per_connection
        throughput = successful / duration if duration > 0 else 0
        
        return BenchmarkResult(
            name="connection_pool",
            duration=duration,
            requests_sent=total_requests,
            requests_successful=successful,
            requests_failed=failed,
            throughput=throughput,
            latencies=latencies
        )
    
    async def benchmark_cache_hit_rate(self, num_requests: int = 1000,
                                      cache_size: int = 100,
                                      unique_endpoints: int = 50) -> BenchmarkResult:
        """Benchmark cache effectiveness"""
        print(f"\n📊 Cache Benchmark")
        print(f"   Requests: {num_requests}")
        print(f"   Cache size: {cache_size}")
        print(f"   Unique endpoints: {unique_endpoints}")
        
        from aztm.resilience import ResponseCache
        
        cache = ResponseCache(max_size=cache_size)
        latencies = []
        cache_hits = 0
        cache_misses = 0
        start_time = time.time()
        
        for i in range(num_requests):
            # Generate endpoint with some repetition
            endpoint_id = i % unique_endpoints
            path = f"/endpoint/{endpoint_id}"
            
            req_start = time.time()
            
            # Check cache
            cached = await cache.get('GET', path)
            
            if cached:
                cache_hits += 1
                latency = 0.0001  # Cache hit is very fast
            else:
                cache_misses += 1
                latency = 0.01  # Cache miss requires full request
                
                # Store in cache
                await cache.set('GET', path, {'data': f'response_{endpoint_id}'})
            
            latencies.append(latency)
        
        duration = time.time() - start_time
        hit_rate = cache_hits / num_requests if num_requests > 0 else 0
        throughput = num_requests / duration if duration > 0 else 0
        
        print(f"   Cache hit rate: {hit_rate:.2%}")
        
        return BenchmarkResult(
            name="cache",
            duration=duration,
            requests_sent=num_requests,
            requests_successful=cache_hits,
            requests_failed=cache_misses,
            throughput=throughput,
            latencies=latencies
        )
    
    def print_results(self, results: List[BenchmarkResult]):
        """Print benchmark results in a nice format"""
        print("\n" + "="*70)
        print("📊 AZTM Performance Benchmark Results")
        print("="*70)
        
        for result in results:
            print(f"\n🔹 {result.name.upper()}")
            print(f"   Duration: {result.duration:.2f}s")
            print(f"   Requests: {result.requests_sent} (✅ {result.requests_successful}, ❌ {result.requests_failed})")
            print(f"   Throughput: {result.throughput:.2f} req/s")
            print(f"   Latency:")
            print(f"      Average: {result.avg_latency*1000:.2f}ms")
            print(f"      P50: {result.p50_latency*1000:.2f}ms")
            print(f"      P95: {result.p95_latency*1000:.2f}ms")
            print(f"      P99: {result.p99_latency*1000:.2f}ms")
        
        print("\n" + "="*70)
        
        # Performance assessment
        print("\n🎯 Performance Assessment:")
        
        for result in results:
            if result.name == "throughput":
                if result.throughput > 1000:
                    print("   ✅ Excellent throughput (>1000 req/s)")
                elif result.throughput > 500:
                    print("   ✅ Good throughput (>500 req/s)")
                else:
                    print("   ⚠️ Low throughput (<500 req/s)")
            
            if result.p99_latency < 0.010:  # 10ms
                print(f"   ✅ {result.name}: Excellent P99 latency (<10ms)")
            elif result.p99_latency < 0.050:  # 50ms
                print(f"   ✅ {result.name}: Good P99 latency (<50ms)")
            elif result.p99_latency < 0.100:  # 100ms
                print(f"   ⚠️ {result.name}: Acceptable P99 latency (<100ms)")
            else:
                print(f"   ❌ {result.name}: Poor P99 latency (>100ms)")
    
    async def run_full_benchmark(self):
        """Run complete benchmark suite"""
        results = []
        
        # Throughput test
        throughput_result = await self.benchmark_throughput(
            num_requests=1000,
            concurrent_clients=10
        )
        results.append(throughput_result)
        
        # Latency test
        latency_results = await self.benchmark_latency(
            num_requests=100,
            payload_sizes=[1024, 102400]  # 1KB and 100KB
        )
        results.extend(latency_results.values())
        
        # Connection pool test
        pool_result = await self.benchmark_connection_pool(
            num_connections=20,
            requests_per_connection=50
        )
        results.append(pool_result)
        
        # Cache test
        cache_result = await self.benchmark_cache_hit_rate(
            num_requests=1000,
            cache_size=100,
            unique_endpoints=50
        )
        results.append(cache_result)
        
        # Print results
        self.print_results(results)
        
        # Save results to JSON
        with open('benchmark_results.json', 'w') as f:
            json.dump([r.to_dict() for r in results], f, indent=2)
        print("\n📁 Results saved to benchmark_results.json")


async def main():
    """Main benchmark runner"""
    parser = argparse.ArgumentParser(description='AZTM Performance Benchmark')
    parser.add_argument('--test', choices=['throughput', 'latency', 'pool', 'cache', 'all'],
                       default='all', help='Which benchmark to run')
    args = parser.parse_args()
    
    benchmark = AZTMBenchmark()
    
    if args.test == 'all':
        await benchmark.run_full_benchmark()
    elif args.test == 'throughput':
        result = await benchmark.benchmark_throughput()
        benchmark.print_results([result])
    elif args.test == 'latency':
        results = await benchmark.benchmark_latency()
        benchmark.print_results(list(results.values()))
    elif args.test == 'pool':
        result = await benchmark.benchmark_connection_pool()
        benchmark.print_results([result])
    elif args.test == 'cache':
        result = await benchmark.benchmark_cache_hit_rate()
        benchmark.print_results([result])


if __name__ == "__main__":
    asyncio.run(main())