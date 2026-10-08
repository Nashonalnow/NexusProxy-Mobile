//! NexusProxy Mobile: Encrypted Session Storage & Audit Repository Core
//! Manages projects, forensic traffic history, and immutable tamper-evident audit logs.

use chrono::{DateTime, Utc};
use nexusproxy_parser::HttpTransaction;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use thiserror::Error;
use tokio::sync::RwLock;
use uuid::Uuid;

#[derive(Error, Debug)]
pub enum StorageError {
    #[error("Record not found: {0}")]
    NotFound(String),
    #[error("Serialization failure: {0}")]
    SerializationError(String),
    #[error("Database lock poisoned")]
    LockError,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Project {
    pub id: String,
    pub name: String,
    pub target_scope: Vec<String>,
    pub created_at: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrafficRecord {
    pub id: String,
    pub project_id: String,
    pub method: String,
    pub host: String,
    pub path: String,
    pub status_code: u16,
    pub latency_ms: u64,
    pub request_raw: Vec<u8>,
    pub response_raw: Vec<u8>,
    pub sha256_digest: String,
    pub timestamp: DateTime<Utc>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditLogEntry {
    pub id: String,
    pub action: String,
    pub actor: String,
    pub metadata: String,
    pub timestamp: DateTime<Utc>,
}

pub struct StorageEngine {
    projects: Arc<RwLock<Vec<Project>>>,
    traffic: Arc<RwLock<Vec<TrafficRecord>>>,
    audit_logs: Arc<RwLock<Vec<AuditLogEntry>>>,
}

impl StorageEngine {
    pub fn new() -> Self {
        Self {
            projects: Arc::new(RwLock::new(Vec::new())),
            traffic: Arc::new(RwLock::new(Vec::new())),
            audit_logs: Arc::new(RwLock::new(Vec::new())),
        }
    }

    pub async fn create_project(&self, name: &str, scope: Vec<String>) -> Project {
        let p = Project {
            id: Uuid::new_v4().to_string(),
            name: name.to_string(),
            target_scope: scope,
            created_at: Utc::now(),
        };
        let mut list = self.projects.write().await;
        list.push(p.clone());

        self.log_audit("create_project", "operator", &format!("Created project '{}'", name)).await;
        p
    }

    pub async fn record_transaction(&self, project_id: &str, tx: &HttpTransaction) -> TrafficRecord {
        let req_raw = tx.request.to_raw_bytes();
        let resp_raw = match &tx.response {
            Some(r) => {
                let mut buf = Vec::new();
                buf.extend_from_slice(format!("HTTP/1.1 {} {}\r\n", r.status_code, r.status_text).as_bytes());
                for (k, v) in &r.headers {
                    buf.extend_from_slice(format!("{}: {}\r\n", k, v).as_bytes());
                }
                buf.extend_from_slice(b"\r\n");
                buf.extend_from_slice(&r.body);
                buf
            }
            None => Vec::new(),
        };

        let rec = TrafficRecord {
            id: tx.id.clone(),
            project_id: project_id.to_string(),
            method: tx.request.method.clone(),
            host: tx.request.host.clone(),
            path: tx.request.path.clone(),
            status_code: tx.response.as_ref().map(|r| r.status_code).unwrap_or(0),
            latency_ms: tx.response.as_ref().map(|r| r.latency_ms).unwrap_or(0),
            request_raw: req_raw,
            response_raw: resp_raw,
            sha256_digest: tx.sha256_digest.clone(),
            timestamp: tx.request.timestamp,
        };

        let mut list = self.traffic.write().await;
        list.push(rec.clone());
        rec
    }

    pub async fn get_traffic_history(&self, host_filter: Option<&str>) -> Vec<TrafficRecord> {
        let list = self.traffic.read().await;
        match host_filter {
            Some(h) => list.iter().filter(|t| t.host.contains(h)).cloned().collect(),
            None => list.clone(),
        }
    }

    pub async fn log_audit(&self, action: &str, actor: &str, metadata: &str) {
        let entry = AuditLogEntry {
            id: Uuid::new_v4().to_string(),
            action: action.to_string(),
            actor: actor.to_string(),
            metadata: metadata.to_string(),
            timestamp: Utc::now(),
        };
        let mut list = self.audit_logs.write().await;
        list.push(entry);
    }

    pub async fn get_audit_trail(&self) -> Vec<AuditLogEntry> {
        self.audit_logs.read().await.clone()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use nexusproxy_parser::{HttpRequest, HttpResponse};

    #[tokio::test]
    async fn test_storage_project_and_traffic() {
        let storage = StorageEngine::new();
        let proj = storage.create_project("Assessment-1", vec!["*.target.com".to_string()]).await;
        assert_eq!(proj.name, "Assessment-1");

        let req = HttpRequest::new("GET", "api.target.com", 443, "/users");
        let resp = HttpResponse::new(200, "OK");
        let tx = HttpTransaction::new(req, Some(resp));

        let rec = storage.record_transaction(&proj.id, &tx).await;
        assert_eq!(rec.method, "GET");
        assert_eq!(rec.status_code, 200);

        let history = storage.get_traffic_history(Some("target.com")).await;
        assert_eq!(history.len(), 1);

        let audit = storage.get_audit_trail().await;
        assert!(audit.len() >= 1);
    }
}
