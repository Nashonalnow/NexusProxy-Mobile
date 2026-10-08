# NexusProxy Mobile™ Threat Model (STRIDE)

This threat model assesses potential risks associated with running an on-device HTTP/HTTPS interception proxy and traffic replay engine on mobile platforms.

---

## 1. System Assets & Security Boundaries
- **Asset 1: Root CA Private Key**: High-entropy key minting forged TLS certificates.
- **Asset 2: Decrypted Session Telemetry**: Captured HTTP requests/responses containing cookies, bearer tokens, PII.
- **Asset 3: Replay Engine Controls**: Ability to generate and send custom HTTP network traffic.
- **Boundary 1**: Device Localhost / Loopback Socket (`127.0.0.1`).
- **Boundary 2**: Operating System Sandbox / Container.
- **Boundary 3**: Upstream Network / Internet Gateway.

---

## 2. STRIDE Threat Analysis & Mitigations

| Threat Category | Potential Vector | Mitigation in NexusProxy Mobile |
| :--- | :--- | :--- |
| **Spoofing** | Rogue on-device app spoofing NexusProxy proxy socket. | Proxy listener binds strictly to isolated ephemeral loopback sockets or virtual TUN interfaces with internal authentication tokens. |
| **Tampering** | Malicious local app attempting to alter intercepted traffic database. | Database is encrypted using SQLCipher AES-256 with keys stored in hardware Keystore / Secure Enclave. |
| **Repudiation** | Operator denying testing actions or sending requests out-of-scope. | Immutable audit trail (`audit_log` table) recording every replay action, timestamp, and target hash. |
| **Information Disclosure** | Leakage of sensitive tokens (JWT, Session Cookies, Passwords) in exported logs. | Automated redaction rules mask `Authorization`, `Cookie`, `Set-Cookie`, and custom API keys before persistence unless explicitly overridden. |
| **Denial of Service** | Upstream server DoS caused by runaway replay loops or scanner threads. | Rate limiter enforces hard ceiling (default 60 requests/minute) and halts automatically upon consecutive HTTP 5xx responses. |
| **Elevation of Privilege** | Using proxy to bypass OS security boundaries or app sandboxes. | Operates entirely within standard userspace permissions (Android `VpnService`, iOS `NetworkExtension`) without requiring root/jailbreak. |

---

## 3. Scope Leakage Prevention
To prevent accidental interception or replaying against third-party production infrastructure:
1. **Explicit Scope Gate**: Out-of-scope requests cannot be dispatched via the Repeater.
2. **DNS Resolution Check**: Target domains are verified against scope allowlists before socket allocation.
3. **Emergency Stop Button**: Instant one-tap kill switch drops all active sockets, flushes the tunnel, and terminates the proxy listener.
