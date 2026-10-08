# Contributing to NexusProxy Mobile

Thank you for your interest in contributing to **NexusProxy Mobile**! We welcome contributions that improve performance, enhance platform integration, add protocol parsing capabilities, or harden security controls.

---

## 1. Development Principles
- **Originality**: All code must be 100% original. Do not copy, disassemble, or import code, signatures, or proprietary formats from third-party tools (including Burp Suite / PortSwigger).
- **Authorized Testing Only**: No destructive exploits or automated vulnerability scanning scripts that violate legal assessment boundaries.
- **Copper Standard**: Never introduce fake or placeholder telemetry. Everything must be empirically verified from real network sockets.
- **Memory Safety**: The core engine is written in Rust. Avoid `unsafe` blocks unless strictly required for FFI bindings with documented safety invariants.

---

## 2. Setting Up the Development Environment

### Prerequisites
- **Rust Toolchain**: `rustup` with Rust 1.80+ (`cargo`, `clippy`, `rustfmt`).
- **Android**: Android Studio Hedgehog / Iguana, Android NDK 26+, Kotlin 1.9+.
- **iOS**: Xcode 15+ with Swift 5.9+, macOS Sonoma (for building iOS extension).

### Building the Core Engine
```bash
cd core
cargo test
cargo clippy --all-targets -- -D warnings
cargo fmt --check
```

---

## 3. Pull Request Workflow
1. Fork the repository and create a feature branch (`git checkout -b feature/repeater-split-view`).
2. Write unit tests for all new parsers, policies, or cryptographic operations.
3. Verify formatting and linting:
   ```bash
   cargo fmt
   cargo clippy
   ```
4. Commit your changes with conventional commit messages (`feat: add HTTP/2 frame dissecting`, `fix: enforce wildcard scope regex`).
5. Open a Pull Request referencing the corresponding issue.
