//! NexusProxy Mobile: High-Velocity RFC 9110 / 7230 HTTP Parser Core
//! Zero-copy header inspection and raw packet re-serialization.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use thiserror::Error;
use uuid::Uuid;

#[derive(Error, Debug, PartialEq)]
pub enum ParserError {
    #[error("Incomplete HTTP message header")]
    IncompleteHeader,
    #[error("Malformed request line: {0}")]
    MalformedRequestLine(String),
    #[error("Malformed response status line: {0}")]
    MalformedStatusLine(String),
    #[error("Invalid header format: {0}")]
    InvalidHeader(String),
    #[error("Invalid character encoding in header")]
    EncodingError,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct HttpRequest {
    pub id: String,
    pub method: String,
    pub host: String,
    pub port: u16,
    pub path: String,
    pub version: String,
    pub headers: Vec<(String, String)>,
    pub body: Vec<u8>,
    pub timestamp: DateTime<Utc>,
}

impl HttpRequest {
    pub fn new(method: &str, host: &str, port: u16, path: &str) -> Self {
        Self {
            id: Uuid::new_v4().to_string(),
            method: method.to_uppercase(),
            host: host.to_string(),
            port,
            path: if path.is_empty() { "/".to_string() } else { path.to_string() },
            version: "HTTP/1.1".to_string(),
            headers: Vec::new(),
            body: Vec::new(),
            timestamp: Utc::now(),
        }
    }

    pub fn add_header(&mut self, key: &str, value: &str) {
        self.headers.push((key.to_string(), value.to_string()));
    }

    pub fn get_header(&self, key: &str) -> Option<&str> {
        self.headers
            .iter()
            .find(|(k, _)| k.eq_ignore_ascii_case(key))
            .map(|(_, v)| v.as_str())
    }

    pub fn to_raw_bytes(&self) -> Vec<u8> {
        let mut buf = Vec::new();
        let req_line = format!("{} {} {}\r\n", self.method, self.path, self.version);
        buf.extend_from_slice(req_line.as_bytes());

        let mut has_host = false;
        let mut has_content_length = false;

        for (k, v) in &self.headers {
            if k.eq_ignore_ascii_case("host") {
                has_host = true;
            }
            if k.eq_ignore_ascii_case("content-length") {
                has_content_length = true;
            }
            buf.extend_from_slice(format!("{}: {}\r\n", k, v).as_bytes());
        }

        if !has_host && !self.host.is_empty() {
            let host_header = if self.port == 80 || self.port == 443 {
                format!("Host: {}\r\n", self.host)
            } else {
                format!("Host: {}:{}\r\n", self.host, self.port)
            };
            buf.extend_from_slice(host_header.as_bytes());
        }

        if !has_content_length && !self.body.is_empty() {
            buf.extend_from_slice(format!("Content-Length: {}\r\n", self.body.len()).as_bytes());
        }

        buf.extend_from_slice(b"\r\n");
        buf.extend_from_slice(&self.body);
        buf
    }

    pub fn parse(raw: &[u8], host_hint: &str, port_hint: u16) -> Result<Self, ParserError> {
        let s = std::str::from_utf8(raw).map_err(|_| ParserError::EncodingError)?;
        let header_end = s.find("\r\n\r\n").ok_or(ParserError::IncompleteHeader)?;
        let header_part = &s[..header_end];
        let body_bytes = &raw[header_end + 4..];

        let mut lines = header_part.split("\r\n");
        let req_line = lines.next().ok_or(ParserError::IncompleteHeader)?;
        let parts: Vec<&str> = req_line.split_whitespace().collect();
        if parts.len() < 3 {
            return Err(ParserError::MalformedRequestLine(req_line.to_string()));
        }

        let method = parts[0].to_uppercase();
        let path = parts[1].to_string();
        let version = parts[2].to_string();

        let mut headers = Vec::new();
        let mut host = host_hint.to_string();
        let mut port = port_hint;

        for line in lines {
            if let Some((k, v)) = line.split_once(':') {
                let k = k.trim().to_string();
                let v = v.trim().to_string();
                if k.eq_ignore_ascii_case("host") {
                    if let Some((h, p)) = v.split_once(':') {
                        host = h.to_string();
                        if let Ok(parsed_port) = p.parse::<u16>() {
                            port = parsed_port;
                        }
                    } else {
                        host = v.clone();
                    }
                }
                headers.push((k, v));
            }
        }

        Ok(Self {
            id: Uuid::new_v4().to_string(),
            method,
            host,
            port,
            path,
            version,
            headers,
            body: body_bytes.to_vec(),
            timestamp: Utc::now(),
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct HttpResponse {
    pub status_code: u16,
    pub status_text: String,
    pub version: String,
    pub headers: Vec<(String, String)>,
    pub body: Vec<u8>,
    pub latency_ms: u64,
    pub timestamp: DateTime<Utc>,
}

impl HttpResponse {
    pub fn new(status_code: u16, status_text: &str) -> Self {
        Self {
            status_code,
            status_text: status_text.to_string(),
            version: "HTTP/1.1".to_string(),
            headers: Vec::new(),
            body: Vec::new(),
            latency_ms: 0,
            timestamp: Utc::now(),
        }
    }

    pub fn parse(raw: &[u8], latency_ms: u64) -> Result<Self, ParserError> {
        let s = std::str::from_utf8(raw).map_err(|_| ParserError::EncodingError)?;
        let header_end = s.find("\r\n\r\n").ok_or(ParserError::IncompleteHeader)?;
        let header_part = &s[..header_end];
        let body_bytes = &raw[header_end + 4..];

        let mut lines = header_part.split("\r\n");
        let status_line = lines.next().ok_or(ParserError::IncompleteHeader)?;
        let parts: Vec<&str> = status_line.split_whitespace().collect();
        if parts.len() < 2 {
            return Err(ParserError::MalformedStatusLine(status_line.to_string()));
        }

        let version = parts[0].to_string();
        let status_code: u16 = parts[1]
            .parse()
            .map_err(|_| ParserError::MalformedStatusLine(status_line.to_string()))?;
        let status_text = parts[2..].join(" ");

        let mut headers = Vec::new();
        for line in lines {
            if let Some((k, v)) = line.split_once(':') {
                headers.push((k.trim().to_string(), v.trim().to_string()));
            }
        }

        Ok(Self {
            status_code,
            status_text,
            version,
            headers,
            body: body_bytes.to_vec(),
            latency_ms,
            timestamp: Utc::now(),
        })
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HttpTransaction {
    pub id: String,
    pub request: HttpRequest,
    pub response: Option<HttpResponse>,
    pub sha256_digest: String,
}

impl HttpTransaction {
    pub fn new(request: HttpRequest, response: Option<HttpResponse>) -> Self {
        let digest = Self::calculate_seal(&request, response.as_ref());
        Self {
            id: request.id.clone(),
            request,
            response,
            sha256_digest: digest,
        }
    }

    pub fn calculate_seal(req: &HttpRequest, resp: Option<&HttpResponse>) -> String {
        let mut hasher = Sha256::new();
        hasher.update(req.method.as_bytes());
        hasher.update(b" ");
        hasher.update(req.host.as_bytes());
        hasher.update(req.path.as_bytes());
        hasher.update(&req.body);

        if let Some(r) = resp {
            hasher.update(r.status_code.to_string().as_bytes());
            hasher.update(&r.body);
        }

        hex::encode(hasher.finalize())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_http_request() {
        let raw = b"GET /api/v1/auth?user=eric HTTP/1.1\r\nHost: api.target.com\r\nUser-Agent: NexusProxy\r\n\r\n";
        let req = HttpRequest::parse(raw, "api.target.com", 443).unwrap();
        assert_eq!(req.method, "GET");
        assert_eq!(req.path, "/api/v1/auth?user=eric");
        assert_eq!(req.host, "api.target.com");
        assert_eq!(req.get_header("User-Agent"), Some("NexusProxy"));
    }

    #[test]
    fn test_parse_http_response() {
        let raw = b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 13\r\n\r\n{\"status\":\"ok\"}";
        let resp = HttpResponse::parse(raw, 42).unwrap();
        assert_eq!(resp.status_code, 200);
        assert_eq!(resp.status_text, "OK");
        assert_eq!(resp.body, b"{\"status\":\"ok\"}");
        assert_eq!(resp.latency_ms, 42);
    }

    #[test]
    fn test_transaction_sealing() {
        let req = HttpRequest::new("POST", "api.target.com", 443, "/login");
        let resp = HttpResponse::new(200, "OK");
        let tx = HttpTransaction::new(req, Some(resp));
        assert_eq!(tx.sha256_digest.len(), 64);
    }
}
