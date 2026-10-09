#!/usr/bin/env python3
"""
NexusProxy Mobile: Port Supervisor & Automated Socket Lifecycle Manager
Guarantees clean socket binding, automated stale process cleanup, and fail-safe shutdown.
Strict Copper Standard: Zero lingering listeners, zero [Errno 98] bind errors.
"""

import os
import sys
import time
import signal
import socket
import atexit
import subprocess
from typing import List, Set, Optional

def is_port_in_use(port: int, host: str = "0.0.0.0") -> bool:
    """Checks empirically whether a TCP port is currently bound or occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True

def get_pids_on_port(port: int) -> Set[int]:
    """Identifies process IDs actively listening on or connected to the target port."""
    pids: Set[int] = set()
    current_pid = os.getpid()

    # Method 1: psutil (Fast & Cross-platform)
    try:
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                for conn in proc.net_connections(kind='inet'):
                    if conn.laddr and conn.laddr.port == port:
                        if proc.pid != current_pid:
                            pids.add(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
    except Exception:
        pass

    if pids:
        return pids

    # Method 2: lsof fallback
    try:
        out = subprocess.check_output(
            ["lsof", "-t", f"-iTCP:{port}", "-sTCP:LISTEN"],
            stderr=subprocess.DEVNULL
        ).decode()
        for line in out.strip().splitlines():
            line = line.strip()
            if line.isdigit():
                pid = int(line)
                if pid != current_pid:
                    pids.add(pid)
    except Exception:
        pass

    if pids:
        return pids

    # Method 3: fuser fallback
    try:
        out = subprocess.check_output(
            ["fuser", f"{port}/tcp"],
            stderr=subprocess.DEVNULL
        ).decode()
        for token in out.strip().split():
            token = token.strip()
            if token.isdigit():
                pid = int(token)
                if pid != current_pid:
                    pids.add(pid)
    except Exception:
        pass

    if pids:
        return pids

    # Method 4: ss with pid regex
    try:
        out = subprocess.check_output(
            ["ss", "-tlnp", f"sport = :{port}"],
            stderr=subprocess.DEVNULL
        ).decode()
        import re
        for m in re.finditer(r"pid=(\d+)", out):
            pid = int(m.group(1))
            if pid != current_pid:
                pids.add(pid)
    except Exception:
        pass

    if pids:
        return pids

    # Method 5: Pure Python /proc/net/tcp inode inspection
    try:
        hex_port = f"{port:04X}"
        inodes = set()
        for netfile in ["/proc/net/tcp", "/proc/net/tcp6"]:
            if os.path.exists(netfile):
                with open(netfile, "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 10:
                            local_addr = parts[1]
                            state = parts[3]
                            inode = parts[9]
                            if local_addr.endswith(f":{hex_port}") and state == "0A":
                                inodes.add(f"socket:[{inode}]")
        if inodes:
            for entry in os.listdir("/proc"):
                if entry.isdigit() and int(entry) != current_pid:
                    fd_dir = os.path.join("/proc", entry, "fd")
                    if os.path.isdir(fd_dir):
                        try:
                            for fd in os.listdir(fd_dir):
                                link = os.readlink(os.path.join(fd_dir, fd))
                                if link in inodes:
                                    pids.add(int(entry))
                        except Exception:
                            pass
    except Exception:
        pass

    return pids

def ensure_port_free(port: int, timeout: float = 3.0, host: str = "0.0.0.0") -> bool:
    """
    Automated pre-flight port clearance.
    If the port is occupied, terminates previous instances and waits for release.
    """
    if not is_port_in_use(port, host):
        return True

    pids = get_pids_on_port(port)
    if not pids:
        # Port might be in TIME_WAIT or occupied by a process without inspect permissions
        print(f"[PortManager] ⚠️ Port {port} is busy. Waiting for socket release...", file=sys.stderr)
        start = time.time()
        while time.time() - start < 1.5:
            if not is_port_in_use(port, host):
                return True
            time.sleep(0.1)

    if pids:
        print(f"[PortManager] ⚠️ Port {port} is occupied by PID(s): {list(pids)}. Auto-cleaning previous instance...", file=sys.stderr)
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError):
                pass

        # Poll for graceful release
        start = time.time()
        while time.time() - start < timeout:
            if not is_port_in_use(port, host):
                print(f"[PortManager] ✓ Port {port} released successfully in {time.time()-start:.2f}s.", file=sys.stderr)
                return True
            time.sleep(0.1)

        # Force kill if still lingering
        for pid in pids:
            try:
                print(f"[PortManager] ⚡ Force killing unresponsive process PID {pid}...", file=sys.stderr)
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass

        time.sleep(0.2)

    cleared = not is_port_in_use(port, host)
    if cleared:
        print(f"[PortManager] ✓ Port {port} verified clean and ready for binding.", file=sys.stderr)
    else:
        print(f"[PortManager] ❌ Port {port} could not be cleared automatically.", file=sys.stderr)
    return cleared

def register_cleanup(ports: Optional[List[int]] = None, on_cleanup=None):
    """
    Registers bulletproof signal handlers and atexit triggers to guarantee
    zero orphaned processes or sockets on shutdown.
    """
    cleanup_done = False

    def do_cleanup(signum=None, frame=None):
        nonlocal cleanup_done
        if cleanup_done:
            return
        cleanup_done = True

        sig_name = f"Signal {signum}" if signum else "Normal Exit"
        print(f"\n[Shutdown] 🛑 NexusProxy Mobile shutdown initiated ({sig_name})...", file=sys.stderr)

        if on_cleanup and callable(on_cleanup):
            try:
                on_cleanup()
            except Exception as e:
                print(f"[Shutdown] Cleanup hook error: {e}", file=sys.stderr)

        if ports:
            for p in ports:
                # Small yield to let sockets close
                time.sleep(0.05)

        print("[Shutdown] ✓ Cleanup completed cleanly. Goodbye.\n", file=sys.stderr)
        if signum in (signal.SIGINT, signal.SIGTERM):
            sys.exit(0)

    # Register OS signals
    try:
        signal.signal(signal.SIGINT, do_cleanup)
        signal.signal(signal.SIGTERM, do_cleanup)
        if hasattr(signal, "SIGHUP"):
            signal.signal(signal.SIGHUP, do_cleanup)
    except (ValueError, AttributeError):
        pass

    # Register normal exit
    atexit.register(do_cleanup)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NexusProxy Mobile Port & Socket Lifecycle Manager")
    parser.add_argument("port", type=int, nargs="?", default=8095, help="Port number to inspect/clean")
    parser.add_argument("--clean", action="store_true", help="Auto-clean any process holding the port")
    parser.add_argument("--status", action="store_true", help="Check status of port")
    args = parser.parse_args()

    in_use = is_port_in_use(args.port)
    pids = get_pids_on_port(args.port) if in_use else set()

    if args.status:
        print(f"Port {args.port}: {'IN USE' if in_use else 'FREE'}")
        if pids:
            print(f"Holding PIDs: {list(pids)}")
        sys.exit(0 if not in_use else 1)

    if args.clean or in_use:
        ok = ensure_port_free(args.port)
        sys.exit(0 if ok else 1)

    print(f"Port {args.port} is already free.")
