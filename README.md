# NexusProxy Mobile™

> **Original, Mobile-Native Web Security Testing & Traffic Interception Workbench for Authorized iOS & Android Assessments.**

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Rust](https://img.shields.io/badge/Rust-1.80+-orange.svg)](https://www.rust-lang.org)
[![Android](https://img.shields.io/badge/Android-API_30+-green.svg)](https://developer.android.com)
[![iOS](https://img.shields.io/badge/iOS-16.0+-lightgrey.svg)](https://developer.apple.com/ios)
[![OWASP MASVS](https://img.shields.io/badge/OWASP-MASVS_v2-purple.svg)](https://mas.owasp.org)

---

## 🎯 Product Vision & Architecture

**NexusProxy Mobile** is an original, mobile-first cybersecurity workbench designed for authorized security consultants, mobile penetration testers, and application security engineers. 

Unlike legacy desktop proxies ported awkwardly to handheld screens, NexusProxy Mobile is designed from the ground up for on-device operation. It combines an ultra-fast **Rust core engine** with native platform packet routing (**Android VpnService** and **iOS NetworkExtension**) to provide complete L7 HTTP/HTTPS observability, interactive request replay, and forensic evidence generation without tethering to a laptop.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       NEXUSPROXY MOBILE WORKBENCH                           │
│                                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐ │
│  │   Dashboard   │  │ Proxy/Intercept│  │  HTTP History │  │   Repeater    │ │
│  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘  └───────┬───────┘ │
│          └──────────────────┼──────────────────┼──────────────────┘         │
│                             ▼                  ▼                            │
│                 ┌─────────────────────────────────────────┐                 │
│                 │       Policy & Scope Guard Engine       │                 │
│                 │   (Wildcard allowlists, rate limits)    │                 │
│                 └───────────────────┬─────────────────────┘                 │
│                                     │                                       │
│                 ┌───────────────────▼─────────────────────┐                 │
│                 │    Rust Transport & Parser Core (L7)    │                 │
│                 │   HTTP/1.1, HTTP/2, WebSocket, TLS MITM │                 │
│                 └───────────────────┬─────────────────────┘                 │
│                                     │                                       │
│          ┌──────────────────────────┴──────────────────────────┐            │
│          ▼                                                     ▼            │
│  ┌───────────────┐                                     ┌───────────────┐    │
│  │  SQLCipher DB │ (AES-256 Encrypted Traffic Store)   │ Cert Manager  │    │
│  └───────────────┘                                     └───────────────┘    │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
        ┌───────────────────────┐             ┌───────────────────────┐
        │  Android VpnService   │             │  iOS NetworkExtension │
        │  (Tun2Socks / Netty)  │             │ (PacketTunnelProvider)│
        └───────────────────────┘             └───────────────────────┘
```

---

## ⚡ Core Capabilities

### 1. Transparent Local Proxy & Live Intercept
- On-device HTTP/1.1 and HTTP/2 proxy listener.
- Real-time pause/edit/forward/drop capabilities for requests and responses.
- Per-app routing on Android via `VpnService.Builder.addAllowedApplication`.

### 2. Forensic Traffic History
- Searchable, filterable audit log of all intercepted transactions.
- Inspect raw HTTP request headers, query parameters, payloads, and response bodies.
- Cryptographic SHA-256 evidentiary hash calculated over every transaction for chain of custody.

### 3. Native Request Repeater
- Mobile-native split-pane request editor.
- Modify request methods, endpoints, authorization headers, or request bodies with one tap.
- Instant replay against target servers with detailed latency and status code telemetry.

### 4. Policy Guard & Scope Enforcement
- Strict domain allowlist matching (`*.company.com`, `api.internal`).
- Automated out-of-scope packet dropping to prevent accidental assessment boundary violations.
- Stop conditions on repeated HTTP 5xx server errors or manual abort triggers.

### 5. On-Device CA Certificate Provisioning
- High-entropy Root CA generator utilizing Rustls and OpenSSL cryptography.
- Simple one-click certificate installation profile for Android User Trust Store and Apple iOS profiles (`.mobileconfig`).

### 6. Extended Protocols & Wire Dissection
- **RFC 6455 WebSocket Engine**: Decodes frame opcodes (Text, Binary, Ping, Pong, Close), masking keys, and unmasked payload streams.
- **RFC 7540 HTTP/2 Frame Dissector**: Dissects raw frame length, type (DATA, HEADERS, SETTINGS, etc.), flags, stream IDs, and payloads.

### 7. Automated OWASP MASVS Passive Security Scanner
- Zero-interaction heuristic analysis checking in-flight HTTP/S traffic:
  - Missing HSTS (`MASVS-NETWORK-1`)
  - Missing CSP & X-Content-Type-Options (`MASVS-PLATFORM-2`)
  - Sensitive tokens in URL query parameters (`MASVS-STORAGE-2`)
  - Insecure cookies missing `Secure` or `HttpOnly` flags (`MASVS-STORAGE-2`)
  - Server technology banner disclosures (`MASVS-RESILIENCE-1`)

---

## 🛡️ Intellectual Property & Independence

NexusProxy Mobile is an **original implementation** built independently under the **Apache License 2.0**.
- **No PortSwigger Code or Assets**: Does not copy, decompile, or incorporate code, trademarks, or proprietary formats from Burp Suite Pro.
- **Original User Experience**: Streamlined for touch interfaces, gesture navigation, and mobile battery constraints.
- **Strict Compliance**: Adheres to OWASP Mobile Application Security Verification Standard (MASVS v2).

---

## 📂 Repository Layout

```
NexusProxy-Mobile/
├── .github/workflows/          # CI/CD pipelines (Rust, Android, iOS)
├── docs/                       # Architecture, threat models, MASVS mapping
│   ├── architecture.md
│   ├── threat-model.md
│   └── masvs.md
├── core/                       # Shared Rust Core Workspace
│   ├── Cargo.toml
│   ├── parser/                 # RFC 7230/9110 HTTP, RFC 6455 WS & RFC 7540 H2 parser
│   ├── policy/                 # Scope validation, rate limiting & Passive MASVS scanner
│   ├── tls/                    # CA generation & dynamic leaf cert forge
│   ├── storage/                # SQLCipher database & project models
│   ├── transport/              # TCP proxy, HTTP listener & Replay engine
│   └── ffi/                    # C-ABI and JNI hooks for Kotlin/Swift & Python ctypes
├── android/                    # Native Android (Kotlin + Jetpack Compose + VpnService)
├── ios/                        # Native iOS (Swift + NetworkExtension)
├── workbench/                  # Interactive Local Test Workbench & API (FastAPI + FFI)
│   ├── api/                    # Daemon endpoints & Python ctypes native bridge
│   └── app/                    # Mobile-responsive web UI (Cyberpunk HUD theme)
├── LICENSE                     # Apache 2.0
├── SECURITY.md                 # Vulnerability reporting & RoE boundaries
└── README.md
```

---

## 🚀 Quickstart & Building the Core

### 1. Compile the Rust Core Engine
```bash
cd core
cargo build --release
cargo test
```

### 2. Launch Local Interactive Workbench
```bash
python3 workbench/launch_workbench.py 8095
```
Visit `http://localhost:8095` to test the Proxy, Repeater, and Traffic History.

---

## 📜 License
Distributed under the **Apache License, Version 2.0**. See [`LICENSE`](LICENSE) for details.
