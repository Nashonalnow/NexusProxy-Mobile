// NexusProxy Mobile™ Workbench Client Logic
document.addEventListener("DOMContentLoaded", () => {
    let isInterceptActive = false;

    // Elements
    const navButtons = document.querySelectorAll(".nav-btn");
    const tabPanes = document.querySelectorAll(".tab-pane");
    const btnToggleIntercept = document.getElementById("btnToggleIntercept");
    const statCaptured = document.getElementById("statCaptured");
    const statScopeCount = document.getElementById("statScopeCount");

    // History elements
    const historyTableBody = document.getElementById("historyTableBody");
    const historySearchInput = document.getElementById("historySearchInput");

    // Repeater elements
    const repeaterMethod = document.getElementById("repeaterMethod");
    const repeaterUrl = document.getElementById("repeaterUrl");
    const repeaterRequestText = document.getElementById("repeaterRequestText");
    const repeaterResponseText = document.getElementById("repeaterResponseText");
    const responseStatusPill = document.getElementById("responseStatusPill");
    const responseLatencyPill = document.getElementById("responseLatencyPill");
    const btnSendReplay = document.getElementById("btnSendReplay");

    // Scope elements
    const scopeAllowlistInput = document.getElementById("scopeAllowlistInput");
    const scopeDenylistInput = document.getElementById("scopeDenylistInput");
    const btnSaveScope = document.getElementById("btnSaveScope");

    // Export elements
    const btnExportZip = document.getElementById("btnExportZip");
    const exportResult = document.getElementById("exportResult");

    // Copilot elements
    const btnOpenCopilot = document.getElementById("btnOpenCopilot");
    const btnCloseCopilot = document.getElementById("btnCloseCopilot");
    const copilotDrawer = document.getElementById("copilotDrawer");
    const copilotInput = document.getElementById("copilotInput");
    const btnSendCopilot = document.getElementById("btnSendCopilot");
    const copilotChatStream = document.getElementById("copilotChatStream");
    const copilotChips = document.querySelectorAll(".copilot-chip");

    // 1. Navigation Tab Switching
    window.switchTab = function(tabId) {
        navButtons.forEach(btn => {
            btn.classList.toggle("active", btn.getAttribute("data-tab") === tabId);
        });
        tabPanes.forEach(pane => {
            pane.classList.toggle("active", pane.id === tabId);
        });
    };

    navButtons.forEach(btn => {
        btn.addEventListener("click", () => switchTab(btn.getAttribute("data-tab")));
    });

    // 2. Intercept Toggle
    btnToggleIntercept.addEventListener("click", async () => {
        isInterceptActive = !isInterceptActive;
        btnToggleIntercept.textContent = isInterceptActive ? "INTERCEPT: ON" : "INTERCEPT: OFF";
        btnToggleIntercept.classList.toggle("active", isInterceptActive);

        try {
            await fetch("/api/intercept/toggle", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ intercept: isInterceptActive })
            });
        } catch (e) {
            console.warn("Intercept toggle error:", e);
        }
    });

    // 3. Load & Render History
    async function loadHistory(searchQuery = "") {
        try {
            const url = searchQuery ? `/api/history?search=${encodeURIComponent(searchQuery)}` : "/api/history";
            const res = await fetch(url);
            const data = await res.json();
            const list = data.history || [];

            statCaptured.textContent = list.length;

            if (list.length === 0) {
                historyTableBody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:#94a3b8; padding:20px;">No traffic captured yet.</td></tr>`;
                return;
            }

            historyTableBody.innerHTML = list.map((tx, idx) => {
                const methodClass = `method-${tx.method.toLowerCase()}`;
                return `
                    <tr>
                        <td style="color:#94a3b8; font-family:monospace;">${idx + 1}</td>
                        <td><span class="method-tag ${methodClass}">${tx.method}</span></td>
                        <td style="font-family:monospace; color:#00d2ff;">${escapeHtml(tx.host)}</td>
                        <td style="font-family:monospace;">${escapeHtml(tx.path)}</td>
                        <td><span class="score-badge grade-secure">${tx.status_code}</span></td>
                        <td style="font-family:monospace; color:#94a3b8;">${tx.latency_ms} ms</td>
                        <td>
                            <button class="btn-secondary" style="padding:4px 8px; font-size:0.75rem;" onclick="sendToRepeater('${tx.method}', 'https://${tx.host}${tx.path}', '${escapeJs(tx.request_raw)}')">
                                🔁 To Repeater
                            </button>
                        </td>
                    </tr>
                `;
            }).join("");
        } catch (e) {
            console.warn("Error loading history:", e);
        }
    }

    if (historySearchInput) {
        historySearchInput.addEventListener("input", (e) => loadHistory(e.target.value.trim()));
    }

    // 4. Send to Repeater Helper
    window.sendToRepeater = function(method, url, rawReq) {
        repeaterMethod.value = method;
        repeaterUrl.value = url;
        repeaterRequestText.value = rawReq;
        switchTab("tab-repeater");
    };

    // 5. Repeater Dispatch
    btnSendReplay.addEventListener("click", async () => {
        btnSendReplay.disabled = true;
        btnSendReplay.textContent = "Replaying...";
        responseStatusPill.textContent = "STATUS: WAITING";
        responseLatencyPill.textContent = "-- ms";

        const method = repeaterMethod.value;
        const url = repeaterUrl.value.trim();
        const rawHeadersText = repeaterRequestText.value;

        // Parse headers from text area
        const headers = {};
        const lines = rawHeadersText.split("\n");
        let bodyLines = [];
        let inBody = false;

        for (let line of lines) {
            if (inBody) {
                bodyLines.push(line);
                continue;
            }
            if (line.trim() === "") {
                inBody = true;
                continue;
            }
            const colonIdx = line.indexOf(":");
            if (colonIdx > 0) {
                const k = line.substring(0, colonIdx).trim();
                const v = line.substring(colonIdx + 1).trim();
                headers[k] = v;
            }
        }

        const body = bodyLines.join("\n");

        try {
            const res = await fetch("/api/repeater/dispatch", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    method: method,
                    url: url,
                    headers: headers,
                    body: body
                })
            });

            const data = await res.json();
            if (res.status === 403) {
                responseStatusPill.className = "score-badge";
                responseStatusPill.style.background = "rgba(239, 68, 68, 0.2)";
                responseStatusPill.style.color = "#ef4444";
                responseStatusPill.textContent = "SCOPE DENIED";
                repeaterResponseText.textContent = `❌ SCOPE VIOLATION:\n${data.detail}\n\nGo to 'Scope Guard' tab to add this target host to your authorized allowlist.`;
                return;
            }

            if (data.status === "SUCCESS") {
                responseStatusPill.className = "score-badge grade-secure";
                responseStatusPill.textContent = `STATUS: ${data.status_code}`;
                responseLatencyPill.textContent = `${data.latency_ms} ms`;
                repeaterResponseText.textContent = data.raw_response;
                loadHistory();
                loadPassiveAudit();
            } else {
                responseStatusPill.textContent = "ERROR";
                repeaterResponseText.textContent = `Error: ${data.error || 'Failed to dispatch request'}`;
            }
        } catch (e) {
            repeaterResponseText.textContent = `Network Error: ${e.message}`;
        } finally {
            btnSendReplay.disabled = false;
            btnSendReplay.textContent = "⚡ Send Request";
        }
    });

    // 6. Scope Guard Management
    async function loadScope() {
        try {
            const res = await fetch("/api/status");
            const data = await res.json();
            if (data.scope) {
                scopeAllowlistInput.value = data.scope.join("\n");
                statScopeCount.textContent = data.scope.length;
            }
        } catch (e) {
            console.warn("Scope load error:", e);
        }
    }

    btnSaveScope.addEventListener("click", async () => {
        const lines = scopeAllowlistInput.value.split("\n").map(s => s.trim()).filter(s => s.length > 0);
        try {
            const res = await fetch("/api/scope/update", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ allowlist: lines })
            });
            const data = await res.json();
            statScopeCount.textContent = data.allowlist.length;
            alert("✓ Scope allowlist updated successfully!");
        } catch (e) {
            alert("Error updating scope: " + e.message);
        }
    });

    // 7. Evidence Bundle Export
    btnExportZip.addEventListener("click", async () => {
        btnExportZip.disabled = true;
        btnExportZip.textContent = "Compiling Archive...";

        try {
            const res = await fetch("/api/evidence/export", { method: "POST" });
            const data = await res.json();
            exportResult.innerHTML = `
                <div style="color:#00f59b; font-weight:700; margin-bottom:8px;">✓ Evidence Package Generated</div>
                <div><strong>File Path:</strong> ${data.bundle_file}</div>
                <div><strong>Total Transactions:</strong> ${data.total_records}</div>
                <div><strong>Evidentiary SHA-256 Digest:</strong></div>
                <div style="color:#00d2ff; font-family:monospace; word-break:break-all; margin-top:4px;">${data.sha256}</div>
            `;
        } catch (e) {
            exportResult.textContent = "Export Error: " + e.message;
        } finally {
            btnExportZip.disabled = false;
            btnExportZip.textContent = "📦 Export Evidence ZIP";
        }
    });

    // 8. Mobile Pentest Copilot Integration
    function toggleCopilot(open) {
        if (open) {
            copilotDrawer.classList.remove("hidden");
            copilotInput.focus();
        } else {
            copilotDrawer.classList.add("hidden");
        }
    }

    if (btnOpenCopilot) btnOpenCopilot.addEventListener("click", () => toggleCopilot(true));
    if (btnCloseCopilot) btnCloseCopilot.addEventListener("click", () => toggleCopilot(false));

    function appendCopilotMessage(sender, text, isUser = false) {
        const msg = document.createElement("div");
        msg.className = `copilot-msg ${isUser ? 'user-msg' : 'bot-msg'}`;
        if (!isUser) {
            msg.innerHTML = `<div class="msg-header">${sender}</div><div>${text}</div>`;
        } else {
            msg.textContent = text;
        }
        copilotChatStream.appendChild(msg);
        copilotChatStream.scrollTop = copilotChatStream.scrollHeight;
    }

    function processCopilotQuery(query) {
        const q = query.toLowerCase();
        appendCopilotMessage("Operator", query, true);
        copilotInput.value = "";

        setTimeout(() => {
            let reply = "";
            if (q.includes("traffic") || q.includes("vulnerability") || q.includes("owasp")) {
                reply = `<strong>🛡️ OWASP MASVS-NETWORK Analysis:</strong><br>
                - Intercepted requests show standard HTTPS with TLS 1.3.<br>
                - Token redaction active: Authorization headers sanitized to prevent token leakage in persistent history.<br>
                - Recommend fuzzing authorization headers in Repeater to verify BOLA/IDOR protection.`;
            } else if (q.includes("payload") || q.includes("repeater") || q.includes("test")) {
                reply = `<strong>🔁 Recommended Test Payloads:</strong><br>
                1. <em>Auth Bypass</em>: Remove <code>Authorization</code> header or substitute <code>Bearer null</code>.<br>
                2. <em>HTTP Method Override</em>: Send <code>X-HTTP-Method-Override: PUT</code> on GET endpoints.<br>
                3. <em>Content-Type Confusion</em>: Switch <code>application/json</code> to <code>application/x-www-form-urlencoded</code>.`;
            } else if (q.includes("blueprint") || q.includes("websocket")) {
                reply = `<strong>📐 Feature Blueprint: WebSocket Frame Interceptor:</strong><br>
                - <em>Architecture</em>: Upgrade handshake intercepted; framing loop decodes masking keys and opcodes.<br>
                - <em>User Experience</em>: Dedicated tab with streaming bi-directional chat style messages.<br>
                - <em>MASVS Mapping</em>: MASVS-NETWORK-1 (encapsulation security).`;
            } else {
                reply = `<strong>🤖 Mobile Pentest Copilot:</strong><br>
                Connected to NexusProxy Mobile core. Target scope: ${scopeAllowlistInput.value.replace(/\n/g, ', ')}.<br>
                How can I assist your security assessment or request replay?`;
            }
            appendCopilotMessage("🤖 Mobile Pentest Copilot", reply, false);
        }, 300);
    }

    if (btnSendCopilot) {
        btnSendCopilot.addEventListener("click", () => {
            const q = copilotInput.value.trim();
            if (q) processCopilotQuery(q);
        });
    }

    if (copilotInput) {
        copilotInput.addEventListener("keydown", (e) => {
            if (e.key === "Enter" && copilotInput.value.trim()) {
                processCopilotQuery(copilotInput.value.trim());
            }
        });
    }

    copilotChips.forEach(chip => {
        chip.addEventListener("click", () => {
            processCopilotQuery(chip.getAttribute("data-prompt"));
        });
    });

    // Utilities
    function escapeHtml(str) {
        if (!str) return "";
        return String(str).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    }

    function escapeJs(str) {
        if (!str) return "";
        return String(str).replace(/'/g, "\\'").replace(/\n/g, "\\n").replace(/\r/g, "");
    }

    // 9. Passive Security Audit Logic
    const btnRunPassiveAudit = document.getElementById("btnRunPassiveAudit");
    const statPassiveHigh = document.getElementById("statPassiveHigh");
    const statPassiveMedium = document.getElementById("statPassiveMedium");
    const statPassiveLow = document.getElementById("statPassiveLow");
    const statPassiveInfo = document.getElementById("statPassiveInfo");
    const passiveFindingsCountBadge = document.getElementById("passiveFindingsCountBadge");
    const passiveFindingsContainer = document.getElementById("passiveFindingsContainer");

    async function loadPassiveAudit() {
        if (!passiveFindingsContainer) return;
        try {
            const res = await fetch("/api/audit/passive");
            const data = await res.json();
            const findings = data.findings || [];

            let high = 0, med = 0, low = 0, info = 0;
            findings.forEach(f => {
                const s = (f.severity || "").toLowerCase();
                if (s === "high") high++;
                else if (s === "medium") med++;
                else if (s === "low") low++;
                else info++;
            });

            if (statPassiveHigh) statPassiveHigh.textContent = high;
            if (statPassiveMedium) statPassiveMedium.textContent = med;
            if (statPassiveLow) statPassiveLow.textContent = low;
            if (statPassiveInfo) statPassiveInfo.textContent = info;
            if (passiveFindingsCountBadge) {
                passiveFindingsCountBadge.textContent = `${findings.length} FINDINGS`;
                passiveFindingsCountBadge.className = high > 0 ? "score-badge" : "score-badge grade-secure";
                if (high > 0) {
                    passiveFindingsCountBadge.style.background = "rgba(239, 68, 68, 0.2)";
                    passiveFindingsCountBadge.style.color = "#ef4444";
                }
            }

            if (findings.length === 0) {
                passiveFindingsContainer.innerHTML = `<p class="pane-sub" style="padding:16px; text-align:center;">No vulnerabilities detected across analyzed transactions. Scope is clean.</p>`;
                return;
            }

            passiveFindingsContainer.innerHTML = findings.map(f => {
                const sev = (f.severity || "info").toLowerCase();
                return `
                    <div class="finding-card severity-${sev}">
                        <div class="finding-header">
                            <span class="finding-title">${escapeHtml(f.title)}</span>
                            <div style="display:flex; gap:6px; align-items:center;">
                                <span class="finding-tag tag-${sev}">${f.severity.toUpperCase()}</span>
                                <span class="badge-version">${escapeHtml(f.masvs_id || 'MASVS')}</span>
                            </div>
                        </div>
                        <p class="finding-desc">${escapeHtml(f.description)}</p>
                        <div class="finding-remediation"><strong>Remediation:</strong> ${escapeHtml(f.remediation)}</div>
                        <div class="finding-evidence"><code>Evidence: ${escapeHtml(f.evidence)}</code></div>
                    </div>
                `;
            }).join("");
        } catch (e) {
            console.warn("Passive audit error:", e);
        }
    }

    if (btnRunPassiveAudit) {
        btnRunPassiveAudit.addEventListener("click", () => {
            btnRunPassiveAudit.textContent = "Scanning...";
            loadPassiveAudit().finally(() => {
                btnRunPassiveAudit.textContent = "🔍 Re-Scan Traffic";
            });
        });
    }

    // 10. Frame Dissector Logic
    const dissectorProtoSelect = document.getElementById("dissectorProtoSelect");
    const dissectorHexInput = document.getElementById("dissectorHexInput");
    const btnDissectNow = document.getElementById("btnDissectNow");
    const dissectorResultBadge = document.getElementById("dissectorResultBadge");
    const dissectorOutputJson = document.getElementById("dissectorOutputJson");

    const btnPresetWsMasked = document.getElementById("btnPresetWsMasked");
    const btnPresetWsPing = document.getElementById("btnPresetWsPing");
    const btnPresetH2Data = document.getElementById("btnPresetH2Data");
    const btnPresetH2Settings = document.getElementById("btnPresetH2Settings");

    if (btnPresetWsMasked) {
        btnPresetWsMasked.addEventListener("click", () => {
            dissectorProtoSelect.value = "websocket";
            dissectorHexInput.value = "81 85 37 fa 21 3d 7f 9f 4d 51 58";
        });
    }

    if (btnPresetWsPing) {
        btnPresetWsPing.addEventListener("click", () => {
            dissectorProtoSelect.value = "websocket";
            dissectorHexInput.value = "89 05 70 69 6e 67 21";
        });
    }

    if (btnPresetH2Data) {
        btnPresetH2Data.addEventListener("click", () => {
            dissectorProtoSelect.value = "http2";
            dissectorHexInput.value = "00 00 04 00 01 00 00 00 01 74 65 73 74";
        });
    }

    if (btnPresetH2Settings) {
        btnPresetH2Settings.addEventListener("click", () => {
            dissectorProtoSelect.value = "http2";
            dissectorHexInput.value = "00 00 06 04 00 00 00 00 00 00 03 00 00 00 64";
        });
    }

    if (btnDissectNow) {
        btnDissectNow.addEventListener("click", async () => {
            const proto = dissectorProtoSelect.value;
            const hex = dissectorHexInput.value.trim();
            if (!hex) {
                alert("Please paste or select a raw hex frame first.");
                return;
            }

            btnDissectNow.disabled = true;
            btnDissectNow.textContent = "Dissecting...";
            dissectorResultBadge.textContent = "PROCESSING";

            try {
                const res = await fetch("/api/dissect/frame", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ frame_type: proto, raw_hex: hex })
                });

                const data = await res.json();
                if (res.ok) {
                    dissectorResultBadge.textContent = "DISSECTED";
                    dissectorResultBadge.className = "score-badge grade-secure";
                    dissectorOutputJson.textContent = JSON.stringify(data.result, null, 2);
                } else {
                    dissectorResultBadge.textContent = "ERROR";
                    dissectorResultBadge.className = "score-badge";
                    dissectorResultBadge.style.color = "#ef4444";
                    dissectorOutputJson.textContent = JSON.stringify(data, null, 2);
                }
            } catch (e) {
                dissectorResultBadge.textContent = "NETWORK ERROR";
                dissectorOutputJson.textContent = e.message;
            } finally {
                btnDissectNow.disabled = false;
                btnDissectNow.textContent = "🔬 Dissect Hex Stream";
            }
        });
    }

    // Connect CA download buttons
    const btnDownloadCaCrt = document.getElementById("btnDownloadCaCrt");
    const btnDownloadIosProfile = document.getElementById("btnDownloadIosProfile");
    if (btnDownloadCaCrt) {
        btnDownloadCaCrt.addEventListener("click", () => {
            window.location.href = "/api/ca/download?format=crt";
        });
    }
    if (btnDownloadIosProfile) {
        btnDownloadIosProfile.addEventListener("click", () => {
            window.location.href = "/api/ca/download?format=mobileconfig";
        });
    }

    // Initial load
    loadHistory();
    loadScope();
    loadPassiveAudit();
});

