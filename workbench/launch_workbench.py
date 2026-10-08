#!/usr/bin/env python3
"""
NexusProxy Mobile™ Workbench Launcher
Spins up the interactive mobile web testing workbench on localhost.
"""

import os
import sys
import uvicorn
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "workbench" / "api"))

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8095
    print("==================================================")
    print("🛡️  NexusProxy Mobile™ Interactive Workbench")
    print(f"Server URL: http://localhost:{port}")
    print("Features: Proxy Intercept, HTTP History, Repeater, Scope Guard")
    print("==================================================")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)
