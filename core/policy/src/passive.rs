//! NexusProxy Mobile: Passive Security Analysis & Heuristics Core
//! Performs non-intrusive security audits against captured HTTP traffic adhering to OWASP MASVS v2.

use nexusproxy_parser::{HttpRequest, HttpResponse};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum FindingSeverity {
    Info,
    Low,
    Medium,
    High,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct PassiveFinding {
    pub id: String,
    pub title: String,
    pub severity: FindingSeverity,
    pub masvs_id: String,
    pub description: String,
    pub remediation: String,
    pub evidence: String,
}

pub struct PassiveScanner;

impl PassiveScanner {
    pub fn audit_transaction(req: &HttpRequest, resp: Option<&HttpResponse>) -> Vec<PassiveFinding> {
        let mut findings = Vec::new();

        // 1. Audit Request Query Parameters for Sensitive Token Leaks
        if req.path.contains('?') {
            let lower_path = req.path.to_lowercase();
            for keyword in &["token=", "password=", "secret=", "api_key=", "apikey=", "auth="] {
                if lower_path.contains(keyword) {
                    findings.push(PassiveFinding {
                        id: format!("LEAK-PARAM-{}", req.id),
                        title: "Sensitive Token Leaked in URL Query String".to_string(),
                        severity: FindingSeverity::High,
                        masvs_id: "MASVS-STORAGE-2".to_string(),
                        description: "Sensitive credential or access token passed in URL query parameters, exposing it to server access logs and browser history.".to_string(),
                        remediation: "Pass tokens and credentials within the Authorization header or encrypted request body rather than URL query parameters.".to_string(),
                        evidence: format!("URL Path: {}", req.path),
                    });
                    break;
                }
            }
        }

        // 2. Audit Response Headers
        if let Some(r) = resp {
            let headers_lower: Vec<(String, String)> = r
                .headers
                .iter()
                .map(|(k, v)| (k.to_lowercase(), v.clone()))
                .collect();

            let has_header = |name: &str| headers_lower.iter().any(|(k, _)| k == name);
            let get_header = |name: &str| headers_lower.iter().find(|(k, _)| k == name).map(|(_, v)| v.as_str());

            // A. Strict-Transport-Security (HSTS)
            if !has_header("strict-transport-security") {
                findings.push(PassiveFinding {
                    id: format!("SEC-HSTS-{}", req.id),
                    title: "Missing HTTP Strict Transport Security (HSTS) Header".to_string(),
                    severity: FindingSeverity::Medium,
                    masvs_id: "MASVS-NETWORK-1".to_string(),
                    description: "Server response lacks Strict-Transport-Security header, allowing potential SSL-stripping MITM downgrades.".to_string(),
                    remediation: "Add 'Strict-Transport-Security: max-age=31536000; includeSubDomains' to all HTTPS responses.".to_string(),
                    evidence: format!("Host: {}", req.host),
                });
            }

            // B. Content-Security-Policy (CSP)
            if !has_header("content-security-policy") {
                findings.push(PassiveFinding {
                    id: format!("SEC-CSP-{}", req.id),
                    title: "Missing Content Security Policy (CSP) Header".to_string(),
                    severity: FindingSeverity::Low,
                    masvs_id: "MASVS-PLATFORM-2".to_string(),
                    description: "Response does not restrict script origins or framing via Content-Security-Policy.".to_string(),
                    remediation: "Define a robust Content-Security-Policy header restricting script and object sources.".to_string(),
                    evidence: format!("Status: {}", r.status_code),
                });
            }

            // C. X-Content-Type-Options
            if !has_header("x-content-type-options") {
                findings.push(PassiveFinding {
                    id: format!("SEC-MIME-{}", req.id),
                    title: "Missing X-Content-Type-Options Header".to_string(),
                    severity: FindingSeverity::Low,
                    masvs_id: "MASVS-NETWORK-1".to_string(),
                    description: "Missing 'X-Content-Type-Options: nosniff' header exposes clients to MIME-sniffing drive-by execution.".to_string(),
                    remediation: "Set 'X-Content-Type-Options: nosniff' on all API responses.".to_string(),
                    evidence: "X-Content-Type-Options missing".to_string(),
                });
            }

            // D. Insecure Cookie Flags Audit
            for (k, v) in &headers_lower {
                if k == "set-cookie" {
                    let v_lower = v.to_lowercase();
                    if !v_lower.contains("secure") {
                        findings.push(PassiveFinding {
                            id: format!("COOKIE-SEC-{}", req.id),
                            title: "Insecure Cookie: Missing 'Secure' Flag".to_string(),
                            severity: FindingSeverity::Medium,
                            masvs_id: "MASVS-STORAGE-2".to_string(),
                            description: "Cookie transmitted without the Secure flag can be sent across unencrypted HTTP channels.".to_string(),
                            remediation: "Append '; Secure' to all Set-Cookie directives.".to_string(),
                            evidence: v.clone(),
                        });
                    }
                    if !v_lower.contains("httponly") {
                        findings.push(PassiveFinding {
                            id: format!("COOKIE-HTTPONLY-{}", req.id),
                            title: "Cookie Accessible to JavaScript: Missing 'HttpOnly' Flag".to_string(),
                            severity: FindingSeverity::Medium,
                            masvs_id: "MASVS-STORAGE-2".to_string(),
                            description: "Cookie lacks HttpOnly flag and can be accessed by malicious scripts via document.cookie.".to_string(),
                            remediation: "Append '; HttpOnly' to protect session tokens from client-side script theft.".to_string(),
                            evidence: v.clone(),
                        });
                    }
                }
            }

            // E. Server Banner Information Disclosure
            if let Some(srv) = get_header("server") {
                if srv.contains('/') {
                    findings.push(PassiveFinding {
                        id: format!("INFO-SRV-{}", req.id),
                        title: "Server Technology & Version Banner Disclosed".to_string(),
                        severity: FindingSeverity::Info,
                        masvs_id: "MASVS-RESILIENCE-1".to_string(),
                        description: format!("Server header leaks exact software and version: '{}'.", srv),
                        remediation: "Suppress or genericize the Server response header to prevent fingerprinting.".to_string(),
                        evidence: format!("Server: {}", srv),
                    });
                }
            }
        }

        findings
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_passive_audit_hsts_and_cookie() {
        let req = HttpRequest::new("GET", "api.target.com", 443, "/api/v1/user?token=secret123");
        let mut resp = HttpResponse::new(200, "OK");
        resp.headers.push(("Set-Cookie".to_string(), "session_id=abc12345".to_string()));

        let findings = PassiveScanner::audit_transaction(&req, Some(&resp));

        // Expect: URL token leak, missing HSTS, missing CSP, missing X-Content-Type-Options, missing Secure, missing HttpOnly
        assert!(findings.iter().any(|f| f.title.contains("Sensitive Token Leaked")));
        assert!(findings.iter().any(|f| f.title.contains("HSTS")));
        assert!(findings.iter().any(|f| f.title.contains("Missing 'Secure' Flag")));
        assert!(findings.iter().any(|f| f.title.contains("Missing 'HttpOnly' Flag")));
    }
}
