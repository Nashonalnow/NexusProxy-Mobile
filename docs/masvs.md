# OWASP MASVS v2 Compliance Mapping: NexusProxy Mobile

NexusProxy Mobile is engineered to support security verification while itself adhering to the **OWASP Mobile Application Security Verification Standard (MASVS v2)**.

---

## 1. MASVS Verification Domains

### 🛡️ MASVS-STORAGE (Data Storage and Privacy)
- **MASVS-STORAGE-1**: System credentials, captured HTTP traffic, and evidentiary dossiers are encrypted using SQLCipher AES-256-GCM.
- **MASVS-STORAGE-2**: Sensitive data (Bearer tokens, Passwords, Session cookies) is automatically sanitized and redacted.

### 🔐 MASVS-CRYPTO (Cryptography)
- **MASVS-CRYPTO-1**: All cryptographic operations rely on modern, vetted algorithms (AES-256-GCM, SHA-256, RSA 4096 / ECDSA P-256).
- **MASVS-CRYPTO-2**: Cryptographic keys are generated with secure random number generators (`OsRng`) and stored in the Android Keystore or Apple Keychain.

### 🌐 MASVS-NETWORK (Network Communication)
- **MASVS-NETWORK-1**: Enforces TLS 1.3 / 1.2 for all upstream connections with support for forward-secret cipher suites.
- **MASVS-NETWORK-2**: Loopback proxy sockets bind strictly to `127.0.0.1` and are shielded from external LAN interface probing.

### 📱 MASVS-PLATFORM (Platform Interaction)
- **MASVS-PLATFORM-1**: Requests only minimal necessary permissions (`BIND_VPN_SERVICE`, `INTERNET`, `FOREGROUND_SERVICE`).
- **MASVS-PLATFORM-2**: Enforces strict Android component isolation (`android:exported="false"` on internal activities and services).

### 🔍 MASVS-CODE & MASVS-RESILIENCE
- **MASVS-CODE-1**: Core memory safety guaranteed by Rust's ownership and borrow checker, eliminating buffer overflows and use-after-free vulnerabilities.
- **MASVS-RESILIENCE-1**: Cryptographic SHA-256 sealing of all session exports guarantees data integrity and tamper evidence.
