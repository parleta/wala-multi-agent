import multiprocessing
import time
import os
import sys

# Add the parent directory to the path so we can import the examples directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_server():
    """Runs the native server example."""
    print("[Launcher] Starting server...")
    try:
        from examples.native_server import main as server_main
        server_main()
    except Exception as e:
        print(f"[Launcher] Server failed: {e}")

def run_client():
    """Runs the native client example."""
    # Give the server a moment to start up
    time.sleep(2)
    print("[Launcher] Starting client...")
    try:
        from examples.native_client import main as client_main
        client_main()
    except Exception as e:
        print(f"[Launcher] Client failed: {e}")

if __name__ == "__main__":
    print("[Launcher] Spawning server process...")
    server_process = multiprocessing.Process(target=run_server)
    server_process.start()

    print("[Launcher] Spawning client process...")
    client_process = multiprocessing.Process(target=run_client)
    client_process.start()

    # Wait for the client to finish (it has a limited run time in the example)
    client_process.join()
    print("[Launcher] Client process finished.")

    # The server runs forever, so we need to terminate it
    print("[Launcher] Terminating server process...")
    server_process.terminate()
    server_process.join()
    
    print("[Launcher] Done.")
