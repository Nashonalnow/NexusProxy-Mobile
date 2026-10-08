//! NexusProxy Mobile: Scope Enforcement, Redaction & Safety Guard Engine
//! Enforces lawful authorized assessment boundaries and protects against out-of-scope leakage.

use nexusproxy_parser::HttpRequest;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicU32, Ordering};
use std::sync::Arc;
use thiserror::Error;

#[derive(Error, Debug, PartialEq)]
pub enum PolicyViolation {
    #[error("Target host '{0}' is out of authorized scope")]
    OutOfScope(String),
    #[error("Target host '{0}' is explicitly blacklisted")]
    ExplicitlyDenied(String),
    #[error("Rate limit exceeded for host '{0}': max {1} req/min")]
    RateLimitExceeded(String, u32),
    #[error("Emergency stop triggered: {0}")]
    EmergencyStop(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScopePolicy {
    pub allowlist: Vec<String>,
    pub denylist: Vec<String>,
    pub max_requests_per_minute: u32,
    pub enforce_strict_scope: bool,
    pub auto_redact_sensitive_headers: bool,
}

impl Default for ScopePolicy {
    fn default() -> Self {
        Self {
            allowlist: vec!["*.target.com".to_string(), "api.target.com".to_string()],
            denylist: vec!["*.apple.com".to_string(), "*.google.com".to_string()],
            max_requests_per_minute: 60,
            enforce_strict_scope: true,
            auto_redact_sensitive_headers: true,
        }
    }
}

pub struct PolicyEngine {
    policy: ScopePolicy,
    request_counters: Arc<tokio::sync::Mutex<HashMap<String, Vec<i64>>>>,
    consecutive_5xx_count: AtomicU32,
    is_aborted: std::sync::atomic::AtomicBool,
}

impl PolicyEngine {
    pub fn new(policy: ScopePolicy) -> Self {
        Self {
            policy,
            request_counters: Arc::new(tokio::sync::Mutex::new(HashMap::new())),
            consecutive_5xx_count: AtomicU32::new(0),
            is_aborted: std::sync::atomic::AtomicBool::new(false),
        }
    }

    pub fn is_host_in_scope(&self, host: &str) -> bool {
        let host_lower = host.to_lowercase();

        // 1. Check Denylist first
        for pattern in &self.policy.denylist {
            if Self::matches_pattern(&host_lower, &pattern.to_lowercase()) {
                return false;
            }
        }

        // 2. If allowlist is empty and strict scope is disabled, permit all
        if self.policy.allowlist.is_empty() && !self.policy.enforce_strict_scope {
            return true;
        }

        // 3. Match against Allowlist
        for pattern in &self.policy.allowlist {
            if Self::matches_pattern(&host_lower, &pattern.to_lowercase()) {
                return true;
            }
        }

        false
    }

    fn matches_pattern(host: &str, pattern: &str) -> bool {
        if pattern == "*" || pattern == host {
            return true;
        }
        if pattern.starts_with("*.") {
            let suffix = &pattern[2..];
            if host == suffix || host.ends_with(&format!(".{}", suffix)) {
                return true;
            }
        }
        false
    }

    pub async fn validate_request(&self, req: &HttpRequest) -> Result<(), PolicyViolation> {
        if self.is_aborted.load(Ordering::Relaxed) {
            return Err(PolicyViolation::EmergencyStop("Assessment aborted by operator".to_string()));
        }

        if self.consecutive_5xx_count.load(Ordering::Relaxed) >= 5 {
            return Err(PolicyViolation::EmergencyStop(
                "Triggered stop condition: 5 consecutive upstream HTTP 5xx server errors".to_string()
            ));
        }

        // Check scope
        if !self.is_host_in_scope(&req.host) {
            return Err(PolicyViolation::OutOfScope(req.host.clone()));
        }

        // Check rate limit
        let now = chrono::Utc::now().timestamp();
        let mut counters = self.request_counters.lock().await;
        let timestamps = counters.entry(req.host.clone()).or_insert_with(Vec::new);

        // Prune older than 60 seconds
        timestamps.retain(|&ts| now - ts < 60);

        if timestamps.len() as u32 >= self.policy.max_requests_per_minute {
            return Err(PolicyViolation::RateLimitExceeded(req.host.clone(), self.policy.max_requests_per_minute));
        }

        timestamps.push(now);
        Ok(())
    }

    pub fn record_response_status(&self, status: u16) {
        if status >= 500 && status <= 599 {
            self.consecutive_5xx_count.fetch_add(1, Ordering::Relaxed);
        } else {
            self.consecutive_5xx_count.store(0, Ordering::Relaxed);
        }
    }

    pub fn abort(&self) {
        self.is_aborted.store(true, Ordering::Relaxed);
    }

    pub fn sanitize_headers(&self, headers: &[(String, String)]) -> Vec<(String, String)> {
        if !self.policy.auto_redact_sensitive_headers {
            return headers.to_vec();
        }

        headers
            .iter()
            .map(|(k, v)| {
                let k_lower = k.to_lowercase();
                if k_lower == "authorization"
                    || k_lower == "cookie"
                    || k_lower == "set-cookie"
                    || k_lower == "x-api-key"
                    || k_lower.contains("token")
                    || k_lower.contains("secret")
                {
                    (k.clone(), "[REDACTED_BY_NEXUSPROXY]".to_string())
                } else {
                    (k.clone(), v.clone())
                }
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[tokio::test]
    async fn test_scope_wildcard_matching() {
        let policy = ScopePolicy {
            allowlist: vec!["*.target.com".to_string(), "api.company.com".to_string()],
            denylist: vec!["admin.target.com".to_string()],
            max_requests_per_minute: 10,
            enforce_strict_scope: true,
            auto_redact_sensitive_headers: true,
        };
        let engine = PolicyEngine::new(policy);

        assert!(engine.is_host_in_scope("target.com"));
        assert!(engine.is_host_in_scope("sub.target.com"));
        assert!(engine.is_host_in_scope("api.company.com"));
        assert!(!engine.is_host_in_scope("admin.target.com")); // Denylisted
        assert!(!engine.is_host_in_scope("google.com")); // Out of scope
    }

    #[test]
    fn test_header_redaction() {
        let engine = PolicyEngine::new(ScopePolicy::default());
        let headers = vec![
            ("Authorization".to_string(), "Bearer secret_jwt_123".to_string()),
            ("User-Agent".to_string(), "Mozilla/5.0".to_string()),
            ("X-Api-Key".to_string(), "apikey_999".to_string()),
        ];
        let sanitized = engine.sanitize_headers(&headers);
        assert_eq!(sanitized[0].1, "[REDACTED_BY_NEXUSPROXY]");
        assert_eq!(sanitized[1].1, "Mozilla/5.0");
        assert_eq!(sanitized[2].1, "[REDACTED_BY_NEXUSPROXY]");
    }
}
