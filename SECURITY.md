# Security Policy: NexusProxy Mobile

## 1. Authorized Assessment Boundary & Ethics
NexusProxy Mobile is engineered exclusively for **authorized security evaluations**, penetration testing of systems you own or have explicit written permission to assess, application debugging, and mobile API compliance validation.

- **Mandatory Authorization**: Users must operate exclusively within the bounds of a legally binding Rules of Engagement (RoE) or authorization agreement.
- **In-App Scope Enforcement**: NexusProxy Mobile enforces automated scope boundaries. Any request targeting an endpoint outside configured allowlists is blocked or dropped before dispatch.
- **Strict Non-Destructive Operation**: Automated attacks, denial-of-service payloads, brute-force saturations, and unauthorized exploitation capabilities are expressly forbidden and omitted from this project.

---

## 2. Supported Versions

| Version | Supported | Security Updates |
| :--- | :---: | :--- |
| `0.1.x` (MVP) | Yes | Current development branch |

---

## 3. Reporting a Vulnerability

We take the security of NexusProxy Mobile and its underlying traffic handling core seriously. If you identify a security vulnerability in NexusProxy Mobile (such as memory corruption, proxy leak, sensitive token disclosure, or scope bypass), please report it responsibly:

1. **Do NOT open a public GitHub issue.**
2. Send an advisory report with reproduction steps to **`security@nexusproxy.dev`** or open a private GitHub Security Advisory under the repository's Security tab.
3. Include:
   - Affected crate/component (`core/transport`, `core/tls`, `core/policy`, etc.).
   - Target operating system and version (Android 14+, iOS 17+, Linux).
   - Minimal proof-of-concept request or payload.
   - Potential impact (e.g. Scope bypass, memory unsafety).

We acknowledge receipt within 48 hours and provide a fix timeline within 7 days.

---

## 4. Cryptographic Standards & Key Zeroization
- **Ephemerality**: Dynamic root CA private keys generated during test sessions can be wiped and re-minted with one click.
- **Data Protection**: All intercepted traffic history is encrypted at rest using AES-256-GCM via SQLCipher.
- **Key Storage**: Root secrets are stored strictly within the host platform's hardware key store:
  - **Android**: Android Keystore Provider (Hardware-backed StrongBox / TEE).
  - **iOS**: Apple Keychain Services (`kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`) and Secure Enclave.
