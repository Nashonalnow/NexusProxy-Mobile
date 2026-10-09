#!/usr/bin/env python3
"""
NexusProxy Mobile™ Workbench Launcher
Spins up the interactive mobile web testing workbench on localhost.
Automated Socket Management: Auto-clears stale processes and guarantees fail-safe shutdown.
Strict Copper Standard: Zero lingering listeners, zero [Errno 98] bind errors.
"""

import os
import sys
import time
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
API_DIR = PROJECT_ROOT / "workbench" / "api"
sys.path.insert(0, str(API_DIR))

from port_manager import ensure_port_free, register_cleanup, is_port_in_use

def main():
    parser = argparse.ArgumentParser(description="NexusProxy Mobile™ Workbench Launcher")
    parser.add_argument("port", type=int, nargs="?", default=8095, help="UI / API Daemon port (default: 8095)")
    parser.add_argument("--proxy-port", type=int, default=8085, help="Underlying L7 Proxy listen port (default: 8085)")
    parser.add_argument("--kill", "--clean", action="store_true", dest="clean_only", help="Stop any running instances and release ports without starting")
    parser.add_argument("--status", action="store_true", help="Check status of ports without starting")
    args = parser.parse_args()

    port = args.port
    proxy_port = args.proxy_port

    if args.status:
        ui_busy = is_port_in_use(port)
        proxy_busy = is_port_in_use(proxy_port)
        print(f"Workbench Web UI (Port {port}): {'BUSY' if ui_busy else 'FREE'}")
        print(f"L7 Proxy Socket  (Port {proxy_port}): {'BUSY' if proxy_busy else 'FREE'}")
        sys.exit(0 if not (ui_busy or proxy_busy) else 1)

    if args.clean_only:
        print(f"[Launcher] Cleaning up processes on ports {port} and {proxy_port}...")
        ok_ui = ensure_port_free(port)
        ok_proxy = ensure_port_free(proxy_port)
        print(f"[Launcher] Cleanup result: Web UI Port={ok_ui}, Proxy Port={ok_proxy}")
        sys.exit(0 if (ok_ui and ok_proxy) else 1)

    # 1. Pre-flight automated port check & stale process clearance
    print("==================================================")
    print("🛡️  NexusProxy Mobile™ Interactive Workbench")
    print(f"Target URL: http://localhost:{port}")
    print(f"Proxy Port: {proxy_port}")
    print("==================================================")
    print("[Launcher] Checking port availability...")

    if is_port_in_use(port):
        print(f"[Launcher] Notice: Port {port} is occupied. Performing automated cleanup...")
        if not ensure_port_free(port):
            print(f"[Launcher] ERROR: Could not free port {port}. Please check root permissions.", file=sys.stderr)
            sys.exit(1)

    if is_port_in_use(proxy_port):
        print(f"[Launcher] Notice: Proxy port {proxy_port} is occupied. Performing automated cleanup...")
        ensure_port_free(proxy_port)

    # 2. Register fail-safe OS signal handlers and atexit cleanup
    def on_shutdown():
        print(f"[Launcher] Stopping workbench services on ports {port} and {proxy_port}...")

    register_cleanup(ports=[port, proxy_port], on_cleanup=on_shutdown)

    # 3. Launch Uvicorn with graceful socket binding
    import uvicorn
    print(f"[Launcher] Starting server on 0.0.0.0:{port}...")

    config = uvicorn.Config(
        "server:app",
        host="0.0.0.0",
        port=port,
        reload=False,
        log_level="info",
        timeout_graceful_shutdown=2
    )
    server = uvicorn.Server(config)

    try:
        server.run()
    except KeyboardInterrupt:
        print("\n[Launcher] KeyboardInterrupt received. Shutting down cleanly...")
    finally:
        # Final pass to guarantee port is released immediately
        ensure_port_free(port, timeout=1.0)
        print(f"[Launcher] Ports {port} and {proxy_port} released cleanly. Exiting.")

if __name__ == "__main__":
    main()
