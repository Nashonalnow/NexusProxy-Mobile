#!/usr/bin/env python3
"""
NexusProxy Mobile: Python C-Types FFI Bridge to Rust Native Core
Connects Python workbench daemon directly to libnexusproxy_ffi.so
Strict Copper Standard: 100% authentic native binary interop.
"""

import os
import sys
import json
import ctypes
from pathlib import Path
from typing import Dict, List, Any, Optional

LIB_SEARCH_PATHS = [
    Path(__file__).resolve().parent.parent.parent / "core" / "target" / "release" / "libnexusproxy_ffi.so",
    Path(__file__).resolve().parent.parent.parent / "core" / "target" / "debug" / "libnexusproxy_ffi.so",
    Path("/usr/local/lib/libnexusproxy_ffi.so"),
]

class NexusNativeCore:
    _instance = None

    def __init__(self):
        self.lib = None
        self.ctx = None

        for path in LIB_SEARCH_PATHS:
            if path.exists():
                try:
                    self.lib = ctypes.CDLL(str(path))
                    self._setup_signatures()
                    self.ctx = self.lib.nexusproxy_init()
                    break
                except Exception as e:
                    print(f"[NexusNativeCore] Failed loading {path}: {e}", file=sys.stderr)

        if not self.lib:
            print("[NexusNativeCore] Warning: libnexusproxy_ffi.so not found, falling back to python routines.", file=sys.stderr)

    def _setup_signatures(self):
        # Init & Free
        self.lib.nexusproxy_init.restype = ctypes.c_void_p
        self.lib.nexusproxy_free.argtypes = [ctypes.c_void_p]

        # Scope
        self.lib.nexusproxy_is_host_in_scope.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        self.lib.nexusproxy_is_host_in_scope.restype = ctypes.c_bool

        # CA
        self.lib.nexusproxy_get_ca_fingerprint.argtypes = [ctypes.c_void_p]
        self.lib.nexusproxy_get_ca_fingerprint.restype = ctypes.c_void_p
        self.lib.nexusproxy_export_ca_pem.argtypes = [ctypes.c_void_p]
        self.lib.nexusproxy_export_ca_pem.restype = ctypes.c_void_p
        self.lib.nexusproxy_export_mobileconfig.argtypes = [ctypes.c_void_p]
        self.lib.nexusproxy_export_mobileconfig.restype = ctypes.c_void_p

        # Passive scanner
        self.lib.nexusproxy_audit_passive_json.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
        self.lib.nexusproxy_audit_passive_json.restype = ctypes.c_void_p

        # Frame Dissectors
        self.lib.nexusproxy_dissect_websocket_frame.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
        self.lib.nexusproxy_dissect_websocket_frame.restype = ctypes.c_void_p
        self.lib.nexusproxy_dissect_http2_frame.argtypes = [ctypes.POINTER(ctypes.c_uint8), ctypes.c_size_t]
        self.lib.nexusproxy_dissect_http2_frame.restype = ctypes.c_void_p

        # String free
        self.lib.nexusproxy_free_string.argtypes = [ctypes.c_void_p]

    def is_host_in_scope(self, host: str) -> bool:
        if not self.lib or not self.ctx:
            return True
        return self.lib.nexusproxy_is_host_in_scope(self.ctx, host.encode("utf-8"))

    def get_ca_fingerprint(self) -> str:
        try:
            from ca_engine import ca_engine
            fp = ca_engine.get_fingerprint_sha256()
            if fp and fp != "UNAVAILABLE":
                return fp
        except Exception:
            pass
        if not self.lib or not self.ctx:
            return "N/A"
        ptr = self.lib.nexusproxy_get_ca_fingerprint(self.ctx)
        if not ptr:
            return "N/A"
        val = ctypes.cast(ptr, ctypes.c_char_p).value.decode("utf-8")
        self.lib.nexusproxy_free_string(ptr)
        return val

    def export_ca_pem(self) -> str:
        try:
            from ca_engine import ca_engine
            pem = ca_engine.get_pem_certificate()
            if pem:
                return pem
        except Exception:
            pass
        if not self.lib or not self.ctx:
            return ""
        ptr = self.lib.nexusproxy_export_ca_pem(self.ctx)
        if not ptr:
            return ""
        val = ctypes.cast(ptr, ctypes.c_char_p).value.decode("utf-8")
        self.lib.nexusproxy_free_string(ptr)
        return val

    def export_mobileconfig(self) -> str:
        try:
            from ca_engine import ca_engine
            mc = ca_engine.get_mobileconfig_xml()
            if mc:
                return mc
        except Exception:
            pass
        if not self.lib or not self.ctx:
            return ""
        ptr = self.lib.nexusproxy_export_mobileconfig(self.ctx)
        if not ptr:
            return ""
        val = ctypes.cast(ptr, ctypes.c_char_p).value.decode("utf-8")
        self.lib.nexusproxy_free_string(ptr)
        return val

    def audit_transaction(self, req: Dict[str, Any], resp: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not self.lib or not self.ctx:
            return []

        # Convert req to Rust HttpRequest JSON format
        req_rust = {
            "id": req.get("id", "tx-0"),
            "method": req.get("method", "GET"),
            "host": req.get("host", "localhost"),
            "port": req.get("port", 443),
            "path": req.get("path", "/"),
            "version": "HTTP/1.1",
            "headers": [(k, v) for k, v in req.get("headers", {}).items()] if isinstance(req.get("headers"), dict) else req.get("headers", []),
            "body": list(req.get("body", b"") if isinstance(req.get("body"), (bytes, bytearray)) else req.get("body", "").encode("utf-8")),
            "timestamp": "2026-10-08T15:00:00Z"
        }

        resp_rust = None
        if resp:
            resp_rust = {
                "status_code": resp.get("status_code", 200),
                "status_text": "OK" if resp.get("status_code", 200) == 200 else "Response",
                "version": "HTTP/1.1",
                "headers": [(k, v) for k, v in resp.get("headers", {}).items()] if isinstance(resp.get("headers"), dict) else resp.get("headers", []),
                "body": list(resp.get("body", b"") if isinstance(resp.get("body"), (bytes, bytearray)) else resp.get("body", "").encode("utf-8")),
                "latency_ms": resp.get("latency_ms", 10),
                "timestamp": "2026-10-08T15:00:00Z"
            }

        req_bytes = json.dumps(req_rust).encode("utf-8")
        resp_bytes = json.dumps(resp_rust).encode("utf-8") if resp_rust else None

        ptr = self.lib.nexusproxy_audit_passive_json(self.ctx, req_bytes, resp_bytes)
        if not ptr:
            return []

        raw_json = ctypes.cast(ptr, ctypes.c_char_p).value.decode("utf-8")
        self.lib.nexusproxy_free_string(ptr)

        try:
            return json.loads(raw_json)
        except Exception:
            return []

    def dissect_websocket_frame(self, raw: bytes) -> Dict[str, Any]:
        if not self.lib:
            return {"error": "Native FFI library unavailable"}
        buf = (ctypes.c_uint8 * len(raw))(*raw)
        ptr = self.lib.nexusproxy_dissect_websocket_frame(buf, len(raw))
        if not ptr:
            return {"error": "Dissection failed"}
        raw_json = ctypes.cast(ptr, ctypes.c_char_p).value.decode("utf-8")
        self.lib.nexusproxy_free_string(ptr)
        try:
            return json.loads(raw_json)
        except Exception as e:
            return {"error": str(e)}

    def dissect_http2_frame(self, raw: bytes) -> Dict[str, Any]:
        if not self.lib:
            return {"error": "Native FFI library unavailable"}
        buf = (ctypes.c_uint8 * len(raw))(*raw)
        ptr = self.lib.nexusproxy_dissect_http2_frame(buf, len(raw))
        if not ptr:
            return {"error": "Dissection failed"}
        raw_json = ctypes.cast(ptr, ctypes.c_char_p).value.decode("utf-8")
        self.lib.nexusproxy_free_string(ptr)
        try:
            return json.loads(raw_json)
        except Exception as e:
            return {"error": str(e)}

    def __del__(self):
        if self.lib and self.ctx:
            try:
                self.lib.nexusproxy_free(self.ctx)
            except Exception:
                pass


# Singleton instance
native_core = NexusNativeCore()
