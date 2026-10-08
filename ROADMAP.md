# NexusProxy Mobile™ Development Roadmap

This roadmap is prioritized using the **Weighted Shortest Job First (WSJF)** framework:
$$\text{WSJF} = \frac{\text{User Value} + \text{Time Criticality} + \text{Risk Reduction}}{\text{Job Size / Effort}}$$

---

## 🏆 Prioritized Milestone Overview

| Phase | Milestone | Focus Areas | Target Delivery |
| :---: | :--- | :--- | :---: |
| **Phase 0** | **Foundation & Architecture** | Open-source setup, Rust workspace, CI/CD, Documentation | Completed (Sprint 1) |
| **Phase 1** | **Core Interception MVP** | Proxy listener, HTTP parser, Scope enforcement, History | Sprint 2 |
| **Phase 2** | **Repeater & Replay Engine** | Mobile request editor, Replay dispatch, Diff viewer | Sprint 3 |
| **Phase 3** | **Native Platform Rigs** | Android VpnService, iOS NetworkExtension, Cert manager | Sprint 4 |
| **Phase 4** | **Advanced Protocol Support**| WebSocket inspector, HTTP/2 framing, JWT dissector | Sprint 5 |
| **Phase 5** | **Forensics & AI Copilot** | Signed evidence packages, Mobile Pentest Copilot integration | Sprint 6 |

---

## 📋 Detailed Engineering Tasks

### Phase 0: Repository & Scaffolding (Current)
- [x] Apache 2.0 License, Security Policy, Code of Conduct, Contributing guide.
- [x] Rust workspace structure (`parser`, `policy`, `tls`, `storage`, `transport`, `ffi`).
- [x] System architecture & threat modeling documentation.
- [x] GitHub Actions automated CI workflows.

### Phase 1: Core Interception & Traffic History
- [ ] Implement RFC 9110 compliant HTTP/1.1 request & response streaming parser.
- [ ] Build in-memory & SQLite-backed persistent traffic history store with SHA-256 digests.
- [ ] Implement Scope Policy Engine with wildcard domain matching (`*.example.com`).
- [ ] Add auto-redaction rules for sensitive headers (`Authorization`, `Cookie`, `X-Api-Key`).

### Phase 2: Repeater & Request Mutation
- [ ] Build high-velocity request replay engine with configurable timeout and retry logic.
- [ ] Implement split-pane request/response visualizer with syntax highlighting.
- [ ] Add side-by-side response diff comparator.
- [ ] Implement automated Content-Length and Host header synchronization.

### Phase 3: Android & iOS Platform Integration
- [ ] Android `VpnService` implementation capturing local device loopback traffic.
- [ ] On-device dynamic Root CA generation with `.crt` export and Android user cert installer.
- [ ] iOS `PacketTunnelProvider` extension with local SOCKS5/HTTP redirector.
- [ ] Integration with Android Keystore and iOS Keychain for project database encryption.

### Phase 4: Extended Protocols & Specialized Tools
- [ ] WebSocket frame interception, opcode decoding (text, binary, ping/pong), and re-assembly.
- [ ] HTTP/2 stream multiplexing and HPACK header decompression.
- [ ] Interactive JWT token decoder and signature verification inspector.
- [ ] GraphQL query and mutation beautifier and introspection analyzer.

### Phase 5: Forensics, Export & Copilot Integration
- [ ] Single-click Evidence Dossier export (`engagement.zip` with SHA-256 cryptographic manifest).
- [ ] Real-time telemetry feed to Mobile Pentest Copilot for automated passive vulnerability analysis.
- [ ] Integration with NetVanguard and PortSentinel suites for unified mobile defense.
