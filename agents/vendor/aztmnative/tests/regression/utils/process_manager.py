"""
Process management utilities for AZTM regression tests.
Handles subprocess lifecycle, logging, and cleanup.
"""

import subprocess
import signal
import time
import threading
import os
import sys
from pathlib import Path
from typing import Dict, Optional, List, IO, Any
from dataclasses import dataclass
import logging
from queue import Queue, Empty
import tempfile

logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """Information about a managed subprocess."""
    name: str
    process: subprocess.Popen
    stdout_log: Path
    stderr_log: Path
    stdout_thread: Optional[threading.Thread] = None
    stderr_thread: Optional[threading.Thread] = None
    start_time: float = 0
    ready_event: Optional[threading.Event] = None


class ProcessManager:
    """
    Manages subprocess lifecycle for testing.
    Provides utilities for starting, monitoring, and stopping processes.
    """
    
    def __init__(self, log_dir: Optional[Path] = None):
        """Initialize the process manager."""
        self.processes: Dict[str, ProcessInfo] = {}
        self.log_dir = log_dir or Path(tempfile.mkdtemp(prefix="aztm_test_"))
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._shutdown = False
        
        # Register signal handlers for cleanup
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle termination signals."""
        logger.info(f"Received signal {signum}, cleaning up...")
        self.cleanup_all()
        sys.exit(0)
    
    def start_process(
        self,
        name: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        wait_for: Optional[str] = None,
        timeout: float = 30,
    ) -> ProcessInfo:
        """
        Start a subprocess and optionally wait for a ready signal.
        
        Args:
            name: Unique name for this process
            command: Command and arguments to execute
            env: Environment variables (optional)
            cwd: Working directory (optional)
            wait_for: String to wait for in stdout to indicate readiness
            timeout: Maximum time to wait for readiness
        
        Returns:
            ProcessInfo object containing process details
        """
        if name in self.processes:
            raise ValueError(f"Process '{name}' already exists")
        
        # Create log files
        stdout_log = self.log_dir / f"{name}_stdout.log"
        stderr_log = self.log_dir / f"{name}_stderr.log"
        
        logger.info(f"Starting process '{name}': {' '.join(command)}")
        
        # Start the process
        with open(stdout_log, 'wb') as stdout_file, \
             open(stderr_log, 'wb') as stderr_file:
            
            process = subprocess.Popen(
                command,
                env=env,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,  # Use binary mode for better control
                bufsize=0,  # Unbuffered
            )
        
        # Create process info
        info = ProcessInfo(
            name=name,
            process=process,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
            start_time=time.time(),
        )
        
        # Start log streaming threads
        info.stdout_thread = threading.Thread(
            target=self._stream_output,
            args=(name, process.stdout, stdout_log, wait_for, info),
            daemon=True
        )
        info.stderr_thread = threading.Thread(
            target=self._stream_output,
            args=(name, process.stderr, stderr_log, None, None),
            daemon=True
        )
        
        info.stdout_thread.start()
        info.stderr_thread.start()
        
        self.processes[name] = info
        
        # Wait for ready signal if specified
        if wait_for:
            info.ready_event = threading.Event()
            if not self._wait_for_ready(info, wait_for, timeout):
                self.stop_process(name)
                raise TimeoutError(
                    f"Process '{name}' did not become ready within {timeout} seconds. "
                    f"Check logs at:\n  stdout: {stdout_log}\n  stderr: {stderr_log}"
                )
        
        return info
    
    def _stream_output(
        self,
        process_name: str,
        stream: IO[bytes],
        log_file: Path,
        wait_for: Optional[str],
        info: Optional[ProcessInfo],
    ):
        """Stream output from subprocess to log file."""
        try:
            with open(log_file, 'ab') as f:
                for line in stream:
                    if self._shutdown:
                        break
                    
                    f.write(line)
                    f.flush()
                    
                    # Also print to console in debug mode
                    try:
                        decoded = line.decode('utf-8', errors='replace').rstrip()
                        logger.debug(f"[{process_name}] {decoded}")
                        
                        # Check for ready signal
                        if wait_for and wait_for in decoded and info and info.ready_event:
                            logger.info(f"Process '{process_name}' is ready")
                            info.ready_event.set()
                    except:
                        pass
        except Exception as e:
            if not self._shutdown:
                logger.error(f"Error streaming output for {process_name}: {e}")
    
    def _wait_for_ready(self, info: ProcessInfo, wait_for: str, timeout: float) -> bool:
        """Wait for a process to signal readiness."""
        logger.info(f"Waiting for '{info.name}' to be ready (looking for: '{wait_for}')")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Check if process is still running
            if info.process.poll() is not None:
                logger.error(f"Process '{info.name}' exited with code {info.process.returncode}")
                
                # Try to read and display stderr for debugging
                try:
                    with open(info.stderr_log, 'r') as f:
                        stderr_content = f.read().strip()
                        if stderr_content:
                            logger.error(f"Process '{info.name}' stderr:\n{stderr_content}")
                    with open(info.stdout_log, 'r') as f:
                        stdout_content = f.read().strip()
                        if stdout_content:
                            logger.info(f"Process '{info.name}' stdout:\n{stdout_content}")
                except Exception as e:
                    logger.error(f"Could not read process logs: {e}")
                
                return False
            
            # Check if ready event is set
            if info.ready_event and info.ready_event.wait(timeout=0.1):
                return True
        
        return False
    
    def stop_process(self, name: str, timeout: float = 10):
        """
        Stop a subprocess gracefully, with fallback to force kill.
        
        Args:
            name: Name of the process to stop
            timeout: Maximum time to wait for graceful shutdown
        """
        if name not in self.processes:
            logger.warning(f"Process '{name}' not found")
            return
        
        info = self.processes[name]
        process = info.process
        
        if process.poll() is not None:
            logger.info(f"Process '{name}' already stopped (exit code: {process.returncode})")
            return
        
        logger.info(f"Stopping process '{name}'...")
        
        # Try graceful shutdown with SIGTERM
        try:
            process.terminate()
            process.wait(timeout=timeout)
            logger.info(f"Process '{name}' stopped gracefully")
        except subprocess.TimeoutExpired:
            # Force kill with SIGKILL
            logger.warning(f"Process '{name}' did not stop gracefully, force killing...")
            process.kill()
            process.wait(timeout=5)
            logger.info(f"Process '{name}' force killed")
        except Exception as e:
            logger.error(f"Error stopping process '{name}': {e}")
        
        # Clean up from tracking
        del self.processes[name]
    
    def is_running(self, name: str) -> bool:
        """Check if a process is still running."""
        if name not in self.processes:
            return False
        
        info = self.processes[name]
        return info.process.poll() is None
    
    def get_logs(self, name: str) -> Dict[str, str]:
        """
        Get stdout and stderr logs for a process.
        
        Returns:
            Dictionary with 'stdout' and 'stderr' keys
        """
        if name not in self.processes:
            return {"stdout": "", "stderr": ""}
        
        info = self.processes[name]
        
        stdout_content = ""
        stderr_content = ""
        
        try:
            if info.stdout_log.exists():
                stdout_content = info.stdout_log.read_text(errors='replace')
        except:
            pass
        
        try:
            if info.stderr_log.exists():
                stderr_content = info.stderr_log.read_text(errors='replace')
        except:
            pass
        
        return {
            "stdout": stdout_content,
            "stderr": stderr_content,
        }
    
    def wait_for_exit(self, name: str, timeout: float = 30) -> int:
        """
        Wait for a process to exit and return its exit code.
        
        Args:
            name: Name of the process
            timeout: Maximum time to wait
        
        Returns:
            Exit code of the process
        
        Raises:
            TimeoutError if process doesn't exit within timeout
        """
        if name not in self.processes:
            raise ValueError(f"Process '{name}' not found")
        
        info = self.processes[name]
        
        try:
            exit_code = info.process.wait(timeout=timeout)
            logger.info(f"Process '{name}' exited with code {exit_code}")
            return exit_code
        except subprocess.TimeoutExpired:
            raise TimeoutError(f"Process '{name}' did not exit within {timeout} seconds")
    
    def cleanup_all(self):
        """Stop all managed processes and clean up resources."""
        self._shutdown = True
        logger.info(f"Cleaning up {len(self.processes)} processes...")
        
        # Stop all processes
        for name in list(self.processes.keys()):
            try:
                self.stop_process(name, timeout=5)
            except Exception as e:
                logger.error(f"Error stopping process '{name}': {e}")
        
        # Wait for threads to finish
        for info in list(self.processes.values()):
            if info.stdout_thread and info.stdout_thread.is_alive():
                info.stdout_thread.join(timeout=1)
            if info.stderr_thread and info.stderr_thread.is_alive():
                info.stderr_thread.join(timeout=1)
        
        logger.info("Cleanup complete")
    
    def run_command(
        self,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: float = 30,
    ) -> Dict[str, Any]:
        """
        Run a command and wait for it to complete.
        
        Returns:
            Dictionary with 'returncode', 'stdout', and 'stderr'
        """
        logger.info(f"Running command: {' '.join(command)}")
        
        try:
            result = subprocess.run(
                command,
                env=env,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            return {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired as e:
            return {
                "returncode": -1,
                "stdout": e.stdout or "",
                "stderr": e.stderr or "",
                "error": f"Command timed out after {timeout} seconds",
            }
        except Exception as e:
            return {
                "returncode": -1,
                "stdout": "",
                "stderr": str(e),
                "error": str(e),
            }
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure cleanup."""
        self.cleanup_all()