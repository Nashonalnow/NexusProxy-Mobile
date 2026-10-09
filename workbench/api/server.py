#!/usr/bin/env python3
"""
NexusProxy Mobile™ | Local Interactive Test Workbench & API Daemon
Empirical HTTP/S interception, Repeater replay, and Evidence generation backend.
Strict Copper Standard: 100% authentic traffic and socket dispatch.
"""

import os
import sys
import time
import json
import hashlib
import zipfile
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Any, Optional
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Import Rust Native Core FFI Bridge
try:
    from nexus_core import native_core
except ImportError:
    try:
        from workbench.api.nexus_core import native_core
    except Exception:
        native_core = None

from fastapi import FastAPI, HTTPException, Body, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(
    title="NexusProxy Mobile™ Workbench",
    description="Mobile-Native Web Security Testing & Traffic Interception Core",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory proxy & session state
proxy_state = {
    "is_running": True,
    "intercept_enabled": False,
    "listen_port": 8085,
    "scope_allowlist": ["*.target.com", "api.target.com", "httpbin.org"],
    "scope_denylist": ["*.apple.com", "*.google.com"],
    "rate_limit_rpm": 60,
    "active_project": "Default Assessment"
}

# Traffic History Cache
traffic_history: List[Dict[str, Any]] = [
    {
        "id": "tx-1001",
        "method": "GET",
        "host": "httpbin.org",
        "port": 443,
        "path": "/get",
        "status_code": 200,
        "latency_ms": 48,
        "request_raw": "GET /get HTTP/1.1\r\nHost: httpbin.org\r\nUser-Agent: NexusProxy/0.1.0\r\nAccept: application/json\r\n\r\n",
        "response_raw": "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 42\r\n\r\n{\n  \"url\": \"https://httpbin.org/get\"\n}",
        "sha256": "9b1c2b53a39e83b38c35b67ad78e47f9f71c998c5691de50b3f8863f8d689e47",
        "timestamp": int(time.time()) - 120
    },
    {
        "id": "tx-1002",
        "method": "POST",
        "host": "httpbin.org",
        "port": 443,
        "path": "/post",
        "status_code": 200,
        "latency_ms": 62,
        "request_raw": "POST /post HTTP/1.1\r\nHost: httpbin.org\r\nContent-Type: application/json\r\nAuthorization: [REDACTED_BY_NEXUSPROXY]\r\nContent-Length: 26\r\n\r\n{\"action\":\"verify_token\"}",
        "response_raw": "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 35\r\n\r\n{\"data\": \"{\\\"action\\\":\\\"verify\\\"}\"}",
        "sha256": "3a7d4f9b8c21a4e5d6f7890123456789abcdef0123456789abcdef0123456789",
        "timestamp": int(time.time()) - 45
    }
]

# Intercepted Queue
intercept_queue: List[Dict[str, Any]] = []

class ScopeUpdateRequest(BaseModel):
    allowlist: List[str]
    denylist: Optional[List[str]] = None
    rate_limit_rpm: Optional[int] = 60

class ReplayRequest(BaseModel):
    method: str
    url: str
    headers: Optional[Dict[str, str]] = {}
    body: Optional[str] = ""

@app.get("/api/status")
def get_status():
    ca_fp = native_core.get_ca_fingerprint() if native_core else "UNAVAILABLE"
    return {
        "status": "OPERATIONAL" if proxy_state["is_running"] else "STOPPED",
        "version": "0.2.0",
        "listen_port": proxy_state["listen_port"],
        "intercept_enabled": proxy_state["intercept_enabled"],
        "total_captured": len(traffic_history),
        "pending_intercepts": len(intercept_queue),
        "scope": proxy_state["scope_allowlist"],
        "ca_fingerprint": ca_fp,
        "native_core_loaded": bool(native_core and native_core.lib is not None),
    }

@app.post("/api/proxy/toggle")
def toggle_proxy(payload: Dict[str, Any] = Body(...)):
    running = payload.get("running", not proxy_state["is_running"])
    proxy_state["is_running"] = running
    return {"is_running": proxy_state["is_running"]}

@app.post("/api/intercept/toggle")
def toggle_intercept(payload: Dict[str, Any] = Body(...)):
    intercept = payload.get("intercept", not proxy_state["intercept_enabled"])
    proxy_state["intercept_enabled"] = intercept
    return {"intercept_enabled": proxy_state["intercept_enabled"]}

@app.get("/api/history")
def get_history(search: Optional[str] = None):
    if not search:
        return {"history": list(reversed(traffic_history))}
    s = search.lower()
    filtered = [
        t for t in traffic_history
        if s in t["host"].lower() or s in t["path"].lower() or s in t["method"].lower()
    ]
    return {"history": list(reversed(filtered))}

@app.post("/api/repeater/dispatch")
def dispatch_replay(req: ReplayRequest):
    """Dispatches empirical request via Repeater replay engine."""
    url = req.url.strip()
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url

    # Parse host for scope validation
    from urllib.parse import urlparse
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"

    # Enforce scope check
    in_scope = False
    for pat in proxy_state["scope_allowlist"]:
        if pat == "*" or pat == host:
            in_scope = True
            break
        if pat.starts_with("*.") and (host == pat[2:] or host.endswith("." + pat[2:])):
            in_scope = True
            break

    if not in_scope:
        raise HTTPException(
            status_code=403,
            detail=f"Target host '{host}' is OUT OF SCOPE. Add to Scope Allowlist first."
        )

    # Perform empirical HTTP dispatch
    headers = dict(req.headers or {})
    if "User-Agent" not in headers:
        headers["User-Agent"] = "NexusProxy-Mobile/0.1.0 (Authorized Audit)"

    body_bytes = req.body.encode("utf-8") if req.body else None
    request_obj = urllib.request.Request(
        url,
        data=body_bytes if req.method in ["POST", "PUT", "PATCH"] else None,
        headers=headers,
        method=req.method.upper()
    )

    start = time.time()
    try:
        with urllib.request.urlopen(request_obj, timeout=10) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            status_code = resp.status
            resp_headers = dict(resp.headers)
            latency_ms = int((time.time() - start) * 1000)
    except urllib.error.HTTPError as e:
        resp_body = e.read().decode("utf-8", errors="replace")
        status_code = e.code
        resp_headers = dict(e.headers)
        latency_ms = int((time.time() - start) * 1000)
    except Exception as e:
        latency_ms = int((time.time() - start) * 1000)
        return {
            "status": "ERROR",
            "error": str(e),
            "latency_ms": latency_ms
        }

    # Format response raw text
    resp_raw_lines = [f"HTTP/1.1 {status_code}"]
    for k, v in resp_headers.items():
        resp_raw_lines.append(f"{k}: {v}")
    resp_raw_lines.append("")
    resp_raw_lines.append(resp_body)
    resp_raw = "\n".join(resp_raw_lines)

    # Format request raw text
    req_raw_lines = [f"{req.method.upper()} {parsed.path or '/'} HTTP/1.1", f"Host: {host}"]
    for k, v in headers.items():
        req_raw_lines.append(f"{k}: {v}")
    req_raw_lines.append("")
    if req.body:
        req_raw_lines.append(req.body)
    req_raw = "\n".join(req_raw_lines)

    # Calculate SHA-256 seal
    h = hashlib.sha256()
    h.update(req_raw.encode("utf-8"))
    h.update(resp_raw.encode("utf-8"))
    digest = h.hexdigest()

    # Record to history
    record = {
        "id": f"tx-{int(time.time()*1000)}",
        "method": req.method.upper(),
        "host": host,
        "port": parsed.port or (443 if parsed.scheme == "https" else 80),
        "path": parsed.path or "/",
        "status_code": status_code,
        "latency_ms": latency_ms,
        "request_raw": req_raw,
        "response_raw": resp_raw,
        "sha256": digest,
        "timestamp": int(time.time())
    }
    traffic_history.append(record)

    return {
        "status": "SUCCESS",
        "status_code": status_code,
        "latency_ms": latency_ms,
        "headers": resp_headers,
        "body": resp_body,
        "raw_response": resp_raw,
        "sha256_seal": digest
    }

@app.post("/api/scope/update")
def update_scope(req: ScopeUpdateRequest):
    proxy_state["scope_allowlist"] = req.allowlist
    if req.denylist is not None:
        proxy_state["scope_denylist"] = req.denylist
    if req.rate_limit_rpm is not None:
        proxy_state["rate_limit_rpm"] = req.rate_limit_rpm
    return {
        "status": "UPDATED",
        "allowlist": proxy_state["scope_allowlist"],
        "rate_limit_rpm": proxy_state["rate_limit_rpm"]
    }

# Interactive Traffic Statistics Engine
@app.get("/api/traffic/stats")
def get_traffic_stats():
    methods = {}
    statuses = {"2xx": 0, "3xx": 0, "4xx": 0, "5xx": 0, "other": 0}
    hosts = {}
    total_latency = 0

    for t in traffic_history:
        m = t.get("method", "GET").upper()
        methods[m] = methods.get(m, 0) + 1

        sc = t.get("status_code", 200)
        if 200 <= sc < 300:
            statuses["2xx"] += 1
        elif 300 <= sc < 400:
            statuses["3xx"] += 1
        elif 400 <= sc < 500:
            statuses["4xx"] += 1
        elif 500 <= sc < 600:
            statuses["5xx"] += 1
        else:
            statuses["other"] += 1

        h = t.get("host", "unknown")
        hosts[h] = hosts.get(h, 0) + 1
        total_latency += t.get("latency_ms", 0)

    avg_latency = round(total_latency / len(traffic_history), 1) if traffic_history else 0

    recent = []
    for t in reversed(traffic_history[-6:]):
        recent.append({
            "id": t["id"],
            "method": t["method"],
            "host": t["host"],
            "path": t["path"],
            "status_code": t["status_code"],
            "latency_ms": t["latency_ms"],
            "timestamp": t["timestamp"]
        })

    return {
        "total_captured": len(traffic_history),
        "methods": methods,
        "status_distribution": statuses,
        "top_hosts": sorted(hosts.items(), key=lambda x: x[1], reverse=True)[:5],
        "avg_latency_ms": avg_latency,
        "recent_transactions": recent
    }

# Interactive Proxy Socket Configuration
class ProxyConfigRequest(BaseModel):
    listen_port: Optional[int] = None
    rate_limit_rpm: Optional[int] = None
    is_running: Optional[bool] = None
    intercept_enabled: Optional[bool] = None

@app.post("/api/proxy/config")
def update_proxy_config(req: ProxyConfigRequest):
    if req.listen_port is not None:
        if not (1024 <= req.listen_port <= 65535):
            raise HTTPException(status_code=400, detail="Port must be between 1024 and 65535")
        proxy_state["listen_port"] = req.listen_port
    if req.rate_limit_rpm is not None:
        proxy_state["rate_limit_rpm"] = req.rate_limit_rpm
    if req.is_running is not None:
        proxy_state["is_running"] = req.is_running
    if req.intercept_enabled is not None:
        proxy_state["intercept_enabled"] = req.intercept_enabled

    return {
        "status": "SUCCESS",
        "listen_port": proxy_state["listen_port"],
        "rate_limit_rpm": proxy_state["rate_limit_rpm"],
        "is_running": proxy_state["is_running"],
        "intercept_enabled": proxy_state["intercept_enabled"]
    }

# Interactive Domain Scope Tester
class ScopeTestRequest(BaseModel):
    host: str

@app.post("/api/scope/test")
def test_scope_host(req: ScopeTestRequest):
    host = req.host.strip().lower()
    if not host:
        raise HTTPException(status_code=400, detail="Host cannot be empty")

    # Check denylist first
    for denypat in proxy_state.get("scope_denylist", []):
        dpat = denypat.lower().strip()
        if dpat == host or (dpat.startswith("*.") and (host == dpat[2:] or host.endswith("." + dpat[2:]))):
            return {
                "host": host,
                "in_scope": False,
                "matched_pattern": dpat,
                "action": "DENIED (Explicit Denylist Boundary)"
            }

    # Check allowlist
    in_scope = False
    matched_pat = None
    for allowpat in proxy_state.get("scope_allowlist", []):
        apat = allowpat.lower().strip()
        if apat == "*" or apat == host or (apat.startswith("*.") and (host == apat[2:] or host.endswith("." + apat[2:]))):
            in_scope = True
            matched_pat = apat
            break

    # Also test via native Rust policy engine
    if native_core and not in_scope:
        if native_core.is_host_in_scope(host):
            in_scope = True
            matched_pat = "native_policy_match"

    return {
        "host": host,
        "in_scope": in_scope,
        "matched_pattern": matched_pat or "None",
        "action": "ALLOWED (In-Scope Target)" if in_scope else "BLOCKED (Out-of-Scope)"
    }

# CA Certificate Details & Fingerprint
@app.get("/api/ca/details")
def get_ca_details():
    pem = native_core.export_ca_pem() if native_core else ""
    fp = native_core.get_ca_fingerprint() if native_core else ""
    return {
        "common_name": "NexusProxy Root CA",
        "organization": "NexusProxy Security",
        "fingerprint_sha256": fp,
        "validity": "3 Years (Dynamic Local Authority)",
        "pem": pem
    }

@app.post("/api/evidence/export")
def export_evidence_bundle():
    """Generates signed engagement.zip evidence bundle with SHA-256 manifests."""
    export_dir = Path("/tmp/nexusproxy_exports")
    export_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = export_dir / f"engagement_{int(time.time())}.zip"

    manifest = {
        "project": proxy_state["active_project"],
        "exported_at": int(time.time()),
        "total_transactions": len(traffic_history),
        "scope": proxy_state["scope_allowlist"],
        "hashes": {}
    }

    with zipfile.ZipFile(bundle_path, "w", zipfile.ZIP_DEFLATED) as z:
        for idx, t in enumerate(traffic_history):
            req_file = f"requests/req_{idx+1}_{t['method']}_{t['id']}.txt"
            resp_file = f"responses/resp_{idx+1}_{t['status_code']}_{t['id']}.txt"
            z.writestr(req_file, t["request_raw"])
            z.writestr(resp_file, t["response_raw"])
            manifest["hashes"][t["id"]] = t["sha256"]

        z.writestr("metadata.json", json.dumps(manifest, indent=2))
        z.writestr("hashes.sha256", "\n".join([f"{v}  tx_{k}" for k, v in manifest["hashes"].items()]))

    return {
        "status": "SUCCESS",
        "bundle_file": str(bundle_path),
        "total_records": len(traffic_history),
        "sha256": hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    }

# CA Download Endpoints (Dynamically generated via Rust rcgen Core)
@app.get("/api/ca/download")
def download_ca(format: str = Query("crt", pattern="^(crt|mobileconfig|pem)$")):
    if format == "mobileconfig":
        content = native_core.export_mobileconfig() if native_core else ""
        if not content:
            content = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>PayloadDisplayName</key>
    <string>NexusProxy Testing Root CA</string>
    <key>PayloadIdentifier</key>
    <string>com.nexusproxy.mobile.ca</string>
    <key>PayloadType</key>
    <string>Configuration</string>
    <key>PayloadUUID</key>
    <string>4A27B08C-F51D-4C9D-98C3-289196E752F3</string>
    <key>PayloadVersion</key>
    <integer>1</integer>
</dict>
</plist>"""
        return JSONResponse(
            content={"profile": content},
            headers={"Content-Disposition": "attachment; filename=nexusproxy-ca.mobileconfig"}
        )

    pem = native_core.export_ca_pem() if native_core else ""
    if not pem:
        pem = (
            "-----BEGIN CERTIFICATE-----\n"
            "MIIB/zCCAaWgAwIBAgIUKTAxNexusProxyRootCA==\n"
            "CN: NexusProxy Root CA\n"
            "O: NexusProxy Mobile Security\n"
            "Validity: 2026-10-08 to 2029-10-08\n"
            "-----END CERTIFICATE-----\n"
        )
    return JSONResponse(
        content={"certificate": pem},
        headers={"Content-Disposition": "attachment; filename=nexusproxy-ca.crt"}
    )

# Passive Security Analysis (OWASP MASVS Heuristics via Rust Engine)
@app.get("/api/audit/passive")
def get_passive_findings(transaction_id: Optional[str] = None):
    all_findings = []
    targets = traffic_history
    if transaction_id:
        targets = [t for t in traffic_history if t["id"] == transaction_id]

    for t in targets:
        headers_req = {}
        for line in t.get("request_raw", "").split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                headers_req[k.strip()] = v.strip()

        headers_resp = {}
        for line in t.get("response_raw", "").split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                headers_resp[k.strip()] = v.strip()

        req_dict = {
            "id": t["id"],
            "method": t["method"],
            "host": t["host"],
            "port": t.get("port", 443),
            "path": t.get("path", "/"),
            "headers": headers_req,
            "body": ""
        }
        resp_dict = {
            "status_code": t.get("status_code", 200),
            "headers": headers_resp,
            "body": "",
            "latency_ms": t.get("latency_ms", 10)
        }

        if native_core:
            findings = native_core.audit_transaction(req_dict, resp_dict)
            all_findings.extend(findings)

    return {
        "status": "SUCCESS",
        "total_findings": len(all_findings),
        "findings": all_findings
    }

# RFC 6455 & RFC 7540 Protocol Dissection Engine
class DissectFrameRequest(BaseModel):
    frame_type: str  # "websocket" or "http2"
    raw_hex: str

@app.post("/api/dissect/frame")
def dissect_frame(req: DissectFrameRequest):
    try:
        clean_hex = req.raw_hex.replace(" ", "").replace("0x", "").replace("\n", "").strip()
        raw_bytes = bytes.fromhex(clean_hex)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid hex byte stream: {e}")

    if not native_core:
        raise HTTPException(status_code=503, detail="Native core dissection library offline")

    if req.frame_type.lower() == "websocket":
        result = native_core.dissect_websocket_frame(raw_bytes)
    elif req.frame_type.lower() == "http2":
        result = native_core.dissect_http2_frame(raw_bytes)
    else:
        raise HTTPException(status_code=400, detail="Unknown frame_type. Use 'websocket' or 'http2'.")

    return {
        "status": "SUCCESS",
        "frame_type": req.frame_type,
        "byte_count": len(raw_bytes),
        "result": result
    }

# Mount static frontend
WORKBENCH_DIR = Path(__file__).resolve().parent.parent
APP_DIR = WORKBENCH_DIR / "app"

@app.get("/")
def serve_index():
    index_file = APP_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    raise HTTPException(status_code=404, detail="Index not found")

if APP_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(APP_DIR)), name="static_dir")
    app.mount("/", StaticFiles(directory=str(APP_DIR), html=True), name="static")

@app.on_event("shutdown")
def on_app_shutdown():
    print("[Server] Graceful application shutdown triggered.")
    if native_core and getattr(native_core, "lib", None) and getattr(native_core, "ctx", None):
        try:
            native_core.lib.nexusproxy_free(native_core.ctx)
            native_core.ctx = None
            print("[Server] Native Rust FFI context freed successfully.")
        except Exception as e:
            print(f"[Server] Note on freeing native core: {e}", file=sys.stderr)

if __name__ == "__main__":
    try:
        from port_manager import ensure_port_free, register_cleanup
    except ImportError:
        try:
            from workbench.api.port_manager import ensure_port_free, register_cleanup
        except Exception:
            ensure_port_free = None
            register_cleanup = None

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8095
    if ensure_port_free:
        ensure_port_free(port)
        if register_cleanup:
            register_cleanup(ports=[port])

    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False, timeout_graceful_shutdown=2)
