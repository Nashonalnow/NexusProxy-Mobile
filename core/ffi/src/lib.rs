//! NexusProxy Mobile: C-ABI & Native Mobile Bridge (Android JNI & iOS Swift)
//! Exposes thread-safe FFI functions for native mobile containers.

use libc::c_char;
use nexusproxy_policy::{PolicyEngine, ScopePolicy};
use nexusproxy_storage::StorageEngine;
use nexusproxy_tls::CertificateAuthority;
use nexusproxy_transport::ReplayEngine;
use std::ffi::CString;
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
pub extern "C" fn nexusproxy_free_string(s: *mut c_char) {
    if !s.is_null() {
        unsafe {
            drop(CString::from_raw(s));
        }
    }
}
