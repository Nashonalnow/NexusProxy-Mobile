//! NexusProxy Mobile: High-Performance Transport, Proxy & Request Repeater Core
//! Manages async TCP listeners, intercept queues, and the high-velocity request replay engine.

use nexusproxy_parser::{HttpRequest, HttpResponse, HttpTransaction};
use nexusproxy_policy::{PolicyEngine, PolicyViolation};
use nexusproxy_storage::StorageEngine;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Instant;
use thiserror::Error;
use tokio::io::{AsyncReadExt, AsyncWriteExt};
use tokio::net::TcpStream;
use tokio::sync::Mutex;

#[derive(Error, Debug)]
pub enum TransportError {
    #[error("Scope policy violation: {0}")]
    PolicyError(#[from] PolicyViolation),
    #[error("Upstream connection failed: {0}")]
    UpstreamConnectError(String),
    #[error("I/O error during transmission: {0}")]
    IoError(#[from] std::io::Error),
    #[error("Response parsing error")]
    ParseError,
}

pub struct ReplayEngine {
    policy: Arc<PolicyEngine>,
    storage: Arc<StorageEngine>,
}

impl ReplayEngine {
    pub fn new(policy: Arc<PolicyEngine>, storage: Arc<StorageEngine>) -> Self {
        Self { policy, storage }
    }

    /// Replays an arbitrary HTTP request against an authorized target and returns live response
    pub async fn dispatch_request(
        &self,
        project_id: &str,
        request: &HttpRequest,
    ) -> Result<HttpResponse, TransportError> {
        // 1. Enforce strict scope & rate limits
        self.policy.validate_request(request).await?;

        let start_time = Instant::now();
        let target_addr = format!("{}:{}", request.host, request.port);

        // 2. Transmit raw request across TCP stream
        let mut stream = TcpStream::connect(&target_addr)
            .await
            .map_err(|e| TransportError::UpstreamConnectError(format!("{}: {}", target_addr, e)))?;

        let raw_req = request.to_raw_bytes();
        stream.write_all(&raw_req).await?;

        // 3. Read upstream response
        let mut response_buffer = Vec::new();
        let mut temp_buf = [0u8; 8192];

        // Read initial chunk
        let n = stream.read(&mut temp_buf).await?;
        if n > 0 {
            response_buffer.extend_from_slice(&temp_buf[..n]);
        }

        let latency_ms = start_time.elapsed().as_millis() as u64;

        // 4. Parse response
        let http_response = HttpResponse::parse(&response_buffer, latency_ms)
            .unwrap_or_else(|_| HttpResponse {
                status_code: 200,
                status_text: "OK (Raw Stream)".to_string(),
                version: "HTTP/1.1".to_string(),
                headers: Vec::new(),
                body: response_buffer,
                latency_ms,
                timestamp: chrono::Utc::now(),
            });

        // 5. Update safety monitor and persist
        self.policy.record_response_status(http_response.status_code);
        let tx = HttpTransaction::new(request.clone(), Some(http_response.clone()));
        self.storage.record_transaction(project_id, &tx).await;
        self.storage
            .log_audit("replay_request", "operator", &format!("Replayed {} to {}", request.method, request.host))
            .await;

        Ok(http_response)
    }
}

pub struct ProxyState {
    pub is_running: AtomicBool,
    pub intercept_enabled: AtomicBool,
    pub pending_intercepts: Mutex<Vec<HttpRequest>>,
}

impl ProxyState {
    pub fn new() -> Self {
        Self {
            is_running: AtomicBool::new(false),
            intercept_enabled: AtomicBool::new(false),
            pending_intercepts: Mutex::new(Vec::new()),
        }
    }

    pub fn set_intercept(&self, enabled: bool) {
        self.intercept_enabled.store(enabled, Ordering::Relaxed);
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nexusproxy_policy::ScopePolicy;

    #[tokio::test]
    async fn test_replay_scope_blocking() {
        let policy = Arc::new(PolicyEngine::new(ScopePolicy {
            allowlist: vec!["authorized.test".to_string()],
            denylist: vec![],
            max_requests_per_minute: 10,
            enforce_strict_scope: true,
            auto_redact_sensitive_headers: true,
        }));
        let storage = Arc::new(StorageEngine::new());
        let engine = ReplayEngine::new(policy, storage);

        let out_of_scope_req = HttpRequest::new("GET", "unauthorized-target.com", 80, "/");
        let result = engine.dispatch_request("proj-1", &out_of_scope_req).await;

        assert!(result.is_err());
        match result.unwrap_err() {
            TransportError::PolicyError(PolicyViolation::OutOfScope(host)) => {
                assert_eq!(host, "unauthorized-target.com");
            }
            _ => panic!("Expected OutOfScope error"),
        }
    }
}
