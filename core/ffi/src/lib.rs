//! NexusProxy Mobile: C-ABI & Native Mobile Bridge (Android JNI & iOS Swift)
//! Exposes thread-safe FFI functions for native mobile containers.

use libc::c_char;
use nexusproxy_parser::{Http2Frame, HttpRequest, HttpResponse, WebSocketFrame};
use nexusproxy_policy::{PassiveScanner, PolicyEngine, ScopePolicy};
use nexusproxy_storage::StorageEngine;
use nexusproxy_tls::CertificateAuthority;
use nexusproxy_transport::ReplayEngine;
use std::ffi::{CStr, CString};
use std::sync::Arc;
use tokio::runtime::Runtime;

pub struct NexusProxyContext {
    pub runtime: Runtime,
    pub policy: Arc<PolicyEngine>,
    pub storage: Arc<StorageEngine>,
    pub replay: Arc<ReplayEngine>,
    pub ca: Option<CertificateAuthority>,
}

#[no_mangle]
pub extern "C" fn nexusproxy_init() -> *mut NexusProxyContext {
    let rt = match Runtime::new() {
        Ok(r) => r,
        Err(_) => return std::ptr::null_mut(),
    };

    let policy = Arc::new(PolicyEngine::new(ScopePolicy::default()));
    let storage = Arc::new(StorageEngine::new());
    let replay = Arc::new(ReplayEngine::new(policy.clone(), storage.clone()));

    let ctx = Box::new(NexusProxyContext {
        runtime: rt,
        policy,
        storage,
        replay,
        ca: CertificateAuthority::generate("NexusProxy Root CA", "NexusProxy Security").ok(),
    });

    Box::into_raw(ctx)
}

#[no_mangle]
pub extern "C" fn nexusproxy_free(ctx: *mut NexusProxyContext) {
    if !ctx.is_null() {
        unsafe {
            drop(Box::from_raw(ctx));
        }
    }
}

#[no_mangle]
pub extern "C" fn nexusproxy_get_ca_fingerprint(ctx: *mut NexusProxyContext) -> *mut c_char {
    if ctx.is_null() {
        return std::ptr::null_mut();
    }
    let context = unsafe { &*ctx };
    let fp = context
        .ca
        .as_ref()
        .map(|ca| ca.sha256_fingerprint.clone())
        .unwrap_or_else(|| "NONE".to_string());

    CString::new(fp).unwrap_or_default().into_raw()
}

#[no_mangle]
pub extern "C" fn nexusproxy_is_host_in_scope(ctx: *mut NexusProxyContext, host: *const c_char) -> bool {
    if ctx.is_null() || host.is_null() {
        return false;
    }
    let context = unsafe { &*ctx };
    let host_str = match unsafe { CStr::from_ptr(host) }.to_str() {
        Ok(s) => s,
        Err(_) => return false,
    };
    context.policy.is_host_in_scope(host_str)
}

#[no_mangle]
pub extern "C" fn nexusproxy_export_ca_pem(ctx: *mut NexusProxyContext) -> *mut c_char {
    if ctx.is_null() {
        return std::ptr::null_mut();
    }
    let context = unsafe { &*ctx };
    let pem = context
        .ca
        .as_ref()
        .map(|ca| ca.cert_pem.clone())
        .unwrap_or_default();
    CString::new(pem).unwrap_or_default().into_raw()
}

#[no_mangle]
pub extern "C" fn nexusproxy_export_mobileconfig(ctx: *mut NexusProxyContext) -> *mut c_char {
    if ctx.is_null() {
        return std::ptr::null_mut();
    }
    let context = unsafe { &*ctx };
    let profile = context
        .ca
        .as_ref()
        .map(|ca| ca.generate_ios_mobileconfig())
        .unwrap_or_default();
    CString::new(profile).unwrap_or_default().into_raw()
}

#[no_mangle]
pub extern "C" fn nexusproxy_audit_passive_json(
    _ctx: *mut NexusProxyContext,
    req_json: *const c_char,
    resp_json: *const c_char,
) -> *mut c_char {
    if req_json.is_null() {
        return std::ptr::null_mut();
    }

    let req_str = match unsafe { CStr::from_ptr(req_json) }.to_str() {
        Ok(s) => s,
        Err(_) => return std::ptr::null_mut(),
    };

    let req: HttpRequest = match serde_json::from_str(req_str) {
        Ok(r) => r,
        Err(_) => return std::ptr::null_mut(),
    };

    let resp: Option<HttpResponse> = if !resp_json.is_null() {
        let resp_str = match unsafe { CStr::from_ptr(resp_json) }.to_str() {
            Ok(s) => s,
            Err(_) => return std::ptr::null_mut(),
        };
        serde_json::from_str(resp_str).ok()
    } else {
        None
    };

    let findings = PassiveScanner::audit_transaction(&req, resp.as_ref());
    let out = serde_json::to_string(&findings).unwrap_or_else(|_| "[]".to_string());
    CString::new(out).unwrap_or_default().into_raw()
}

#[no_mangle]
pub extern "C" fn nexusproxy_dissect_websocket_frame(
    raw_bytes: *const u8,
    len: libc::size_t,
) -> *mut c_char {
    if raw_bytes.is_null() || len == 0 {
        return std::ptr::null_mut();
    }
    let slice = unsafe { std::slice::from_raw_parts(raw_bytes, len) };
    match WebSocketFrame::parse(slice) {
        Ok(frame) => {
            let json = serde_json::to_string(&frame).unwrap_or_else(|_| "{}".to_string());
            CString::new(json).unwrap_or_default().into_raw()
        }
        Err(e) => {
            let err_json = format!("{{\"error\": \"{}\"}}", e);
            CString::new(err_json).unwrap_or_default().into_raw()
        }
    }
}

#[no_mangle]
pub extern "C" fn nexusproxy_dissect_http2_frame(
    raw_bytes: *const u8,
    len: libc::size_t,
) -> *mut c_char {
    if raw_bytes.is_null() || len == 0 {
        return std::ptr::null_mut();
    }
    let slice = unsafe { std::slice::from_raw_parts(raw_bytes, len) };
    match Http2Frame::parse(slice) {
        Ok(frame) => {
            let json = serde_json::to_string(&frame).unwrap_or_else(|_| "{}".to_string());
            CString::new(json).unwrap_or_default().into_raw()
        }
        Err(e) => {
            let err_json = format!("{{\"error\": \"{}\"}}", e);
            CString::new(err_json).unwrap_or_default().into_raw()
        }
    }
}

#[no_mangle]
pub extern "C" fn nexusproxy_free_string(s: *mut c_char) {
    if !s.is_null() {
        unsafe {
            drop(CString::from_raw(s));
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ffi_lifecycle_and_scope() {
        let ctx = nexusproxy_init();
        assert!(!ctx.is_null());

        let host = CString::new("api.target.com").unwrap();
        let in_scope = nexusproxy_is_host_in_scope(ctx, host.as_ptr());
        assert!(in_scope);

        let out_host = CString::new("evil.com").unwrap();
        let out_scope = nexusproxy_is_host_in_scope(ctx, out_host.as_ptr());
        assert!(!out_scope);

        let fp = nexusproxy_get_ca_fingerprint(ctx);
        assert!(!fp.is_null());
        nexusproxy_free_string(fp);

        let pem = nexusproxy_export_ca_pem(ctx);
        assert!(!pem.is_null());
        nexusproxy_free_string(pem);

        nexusproxy_free(ctx);
    }

    #[test]
    fn test_ffi_websocket_dissection() {
        let raw = [0x81, 0x05, 0x48, 0x65, 0x6C, 0x6C, 0x6F]; // unmasked text frame "Hello"
        let res = nexusproxy_dissect_websocket_frame(raw.as_ptr(), raw.len());
        assert!(!res.is_null());
        let res_str = unsafe { CStr::from_ptr(res) }.to_str().unwrap();
        assert!(res_str.contains("\"is_final\":true"));
        assert!(res_str.contains("\"opcode\":\"Text\""));
        nexusproxy_free_string(res);
    }

    #[test]
    fn test_ffi_http2_dissection() {
        let raw = [
            0x00, 0x00, 0x04, // length = 4
            0x00,             // type = DATA
            0x01,             // flags = END_STREAM
            0x00, 0x00, 0x00, 0x01, // stream ID = 1
            0x74, 0x65, 0x73, 0x74, // payload "test"
        ];
        let res = nexusproxy_dissect_http2_frame(raw.as_ptr(), raw.len());
        assert!(!res.is_null());
        let res_str = unsafe { CStr::from_ptr(res) }.to_str().unwrap();
        assert!(res_str.contains("\"stream_id\":1"));
        assert!(res_str.contains("\"frame_type\":\"Data\""));
        nexusproxy_free_string(res);
    }
}

