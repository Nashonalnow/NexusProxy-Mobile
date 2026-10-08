# NexusProxy Mobile™ Architecture Whitepaper

## 1. System Overview
NexusProxy Mobile is a mobile-first web application security testing workbench. The system decouples platform-specific packet routing from core protocol parsing, scope validation, dynamic TLS MITM forging, and encrypted session storage.

```
+-------------------------------------------------------------------------------+
|                             CLIENT APPLICATION LAYER                          |
|                                                                               |
|  [ Android Jetpack Compose UI ]           [ iOS SwiftUI Container ]           |
|  [ Interactive Web Workbench ]            [ Headless Automation Daemon ]      |
+---------------------------------------┬---------------------------------------+
                                        │ IPC / C-ABI / FFI
+---------------------------------------▼---------------------------------------+
|                      RUST CORE ENGINE (SHARED RUNTIME)                        |
|                                                                               |
|  1. nexusproxy-policy:                                                        |
|     - Scope Validator (Regex, Wildcard, CIDR matching)                        |
|     - Rate Limiter (Token bucket per domain)                                  |
|     - Redaction Engine (Masks bearer tokens & session cookies)                |
|                                                                               |
|  2. nexusproxy-transport:                                                     |
|     - Local Async TCP Proxy Listener (tokio)                                  |
|     - HTTP CONNECT Tunnel Handler                                             |
|     - Upstream Dispatch & Request Replay Engine (Repeater)                    |
|                                                                               |
|  3. nexusproxy-parser:                                                        |
|     - Zero-Copy HTTP/1.1 & Chunked Transfer Parser                            |
|     - HTTP/2 Frame Dissector                                                  |
|     - WebSocket Frame Reassembler                                             |
|                                                                               |
|  4. nexusproxy-tls:                                                           |
|     - Dedicated Testing Root CA Generation (rcgen / OpenSSL)                  |
|     - Dynamic Per-Host Leaf Certificate Forging                               |
|     - TLS 1.3 / 1.2 Handshake Termination & Upstream Re-encryption            |
|                                                                               |
|  5. nexusproxy-storage:                                                       |
|     - SQLCipher (AES-256-GCM) Local Database                                  |
|     - Project Management, Searchable Traffic History, Audit Trail             |
|     - SHA-256 Evidentiary Sealing                                             |
+---------------------------------------┬---------------------------------------+
                                        │ Native OS Packet Interception
+---------------------------------------▼---------------------------------------+
|                         PLATFORM NETWORK DRIVER LAYER                         |
|                                                                               |
|  [ Android VpnService ]                   [ iOS NetworkExtension ]           |
|  - Virtual TUN Interface                  - PacketTunnelProvider              |
|  - Per-app routing rules                  - NEPacketTunnelNetworkSettings     |
+-------------------------------------------------------------------------------+
```

---

## 2. Subsystem Deep-Dive

### A. Scope Enforcement Engine (`nexusproxy-policy`)
The Policy Engine guarantees that only explicitly authorized target endpoints receive traffic or replay requests.
```rust
pub struct ScopePolicy {
    pub allowlist: Vec<String>,     // e.g. ["*.target.com", "api.target.com"]
    pub denylist: Vec<String>,      // e.g. ["auth.sso.com", "*.thirdparty.com"]
    pub max_rpm: u32,               // Rate limit: Max Requests Per Minute
    pub enforce_strict_scope: bool,
}
```
- **Allowlist Wildcard Matching**: Subdomains are parsed using hierarchical domain tree lookups to prevent path traversal or regex injection bypasses.
- **Fail-Safe Disposition**: If a request violates scope, it is dropped immediately and logged to the security audit trail.

### B. High-Velocity Transport & Repeater (`nexusproxy-transport`)
- Built on top of `tokio` asynchronous I/O.
- Handles transparent proxying for standard HTTP and dynamic TLS tunneling for HTTPS via HTTP `CONNECT`.
- **Repeater Replay Architecture**: Takes an arbitrary modified raw HTTP request, recalculates `Content-Length`, validates target host resolution, dispatches across an isolated connection pool, and returns exact timing and raw response bytes without mutating historical logs.

### C. TLS Dynamic Certificate Forging (`nexusproxy-tls`)
- In order to inspect encrypted HTTPS traffic on authorized devices, NexusProxy Mobile generates a dedicated Root Certificate Authority (CA) upon first launch.
- When an HTTPS connection to `api.target.com:443` is negotiated:
  1. The proxy terminates the client TLS handshake using a dynamically minted leaf certificate matching `CN=api.target.com` and `SAN=DNS:api.target.com`.
  2. The proxy initiates an upstream TLS handshake with the authentic remote server.
  3. Decrypted cleartext flows through the Parser and Policy engines before re-encryption.

### D. Secure Storage & Evidentiary Dossier (`nexusproxy-storage`)
- Intercepted traffic is persisted using SQLCipher with AES-256-GCM encryption.
- Master keys are never hardcoded and are held exclusively in the Android Keystore or iOS Keychain.
- Every captured transaction is cryptographically sealed with a SHA-256 digest:
  $$\text{SHA256}(\text{Method} \parallel \text{URL} \parallel \text{ReqBody} \parallel \text{RespStatus} \parallel \text{RespBody} \parallel \text{Timestamp})$$
