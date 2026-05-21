# GodsApp — Build Status

Honest checkbox status against the v1.0 spec. **Checked = wired up and actually does its real job. Unchecked = not in this build (queued for the next wave).** No "almost done" — if it isn't real, the box is empty.

Author: Joseph Sierengowski
App ID: `com.sierengowski.GodsApp`
Repo: <https://github.com/sierengowskisierengowski-cpu/Godsapp>

---

## Views

- [x] **Dashboard** — counts (workspaces / scans / findings / evidence), live system health, settings-cog shortcut, **clickable System-status card opens Missing Tools dialog (v0.5.0)**
- [x] **Missing Tools dialog** (v0.5.0) — per-tool install command, pkexec install-now, "Install all missing" batched per package manager, "I have this installed" file picker, skip-this-tool toggle, live re-detection
- [x] **Settings → Tool Paths** (v0.5.0) — per-tool override path with pick/test/clear, re-detect-all sweep
- [x] **Workspaces** — list, create, edit, delete (full CRUD against DB)
- [x] **Evidence Locker** — ingest, list, integrity verify (chain-of-custody rows written on every action)
- [x] **Settings (Master)** — REST API toggle/port/token, DB URL override, matrix-scramble toggle
- [x] **Generic Scan View** — auto-rendered per-tool form (target + options), live stdout/stderr, parsed findings list
- [ ] **Findings Manager** — promote tool result → Finding, severity/CVSS/CVE/MITRE tagging, status workflow
- [ ] **Replay Engine** — re-run past scan, diff against previous result
- [ ] **Scheduler UI** — cron-style recurring scans + notifications (schema row exists, UI/cron missing)
- [ ] **Plugins UI** — marketplace browser, enable/disable, source viewer (plugin loader works; UI missing)
- [ ] **API Console** — token mgmt + log viewer in UI (FastAPI server itself exists & runs)
- [ ] **Embedded Terminal** — VTE-based terminal tab(s)
- [ ] **Reports** — PDF / Markdown / DOCX / XLSX / HTML / JSON / SARIF
- [ ] **Per-category Settings sub-pages** (17 categories) — settings cog is wired on every page but currently jumps to the master Settings view; per-category sub-pages are queued

## Tool categories (sidebar)

Each tool below is a **real subprocess wrapper** with declarative options, parsed stdout into structured findings, and `requires_binary` set so the health probe surfaces missing tools instead of silently dead-ending.

### Recon (2)
- [x] Nmap (XML parse → open ports + service findings)
- [x] Subdomain brute (subfinder/amass-style wordlist)

### Web Application (3)
- [x] Gobuster dir (status-code findings)
- [x] Nikto (line-parsed `+` findings, severity by keyword)
- [x] WhatWeb (`--log-json` → tech plugin findings)
- [ ] SQLMap, WPScan, FFUF, JWT analyzer, SSL/TLS analyzer, Headers analyzer, HTTP proxy/inspector

### Network (3)
- [x] Masscan
- [x] Traceroute (icmp/udp/tcp)
- [x] `ss` listening sockets
- [ ] ARP scanner, DNS toolkit, Service fingerprinter (beyond nmap)

### Password & Hash (3)
- [x] Hashcat (10 modes, dictionary/brute/hybrid, parses cracked rows)
- [x] John the Ripper
- [x] Hydra (9 services, captures `[host] login: pwd:` lines as critical findings)
- [ ] Hash identifier, HIBP check, Wordlist manager

### Exploitation (2)
- [x] SearchSploit (Exploit-DB JSON → findings)
- [x] msfvenom (payload generator → artifact)
- [ ] Metasploit RPC bridge, Listener manager, Reverse-shell generator

### Wireless (2)
- [x] iwlist scan (block parse → BSSID/ESSID/signal/encryption findings)
- [x] airodump-ng (CSV capture parse)
- [ ] Bluetooth scanner, Deauth detector

### Forensics (3)
- [x] Binwalk (signature offset findings)
- [x] ExifTool (tag findings, GPS/owner flagged)
- [x] strings (filtered, password/secret heuristic)
- [ ] Volatility 3, PE/ELF/PDF/Office analyzers, Hash calculator UI

### Malware Analysis (2)
- [x] YARA (rule match findings)
- [x] ClamAV `clamscan` (FOUND line → critical findings)

### OSINT (3)
- [x] theHarvester (email + host findings)
- [x] whois (filtered key fields → findings)
- [x] Sherlock (per-site hit findings)
- [ ] Maigret, Email finder, Breach check, Company intel, Social recon

### Crypto & Encoding (3)
- [x] OpenSSL hash (10 algorithms)
- [x] OpenSSL cipher (encrypt/decrypt, PBKDF2 + passphrase, 5 ciphers)
- [x] Codec (base64/base32/hex/url/rot13/ascii85 — pure-Python, no binary)
- [ ] Certificate inspector

### Mobile (2)
- [x] adb (devices / packages / props / logcat / running, regex filter)
- [x] apktool (decode/build, manifest permission scan with severity)
- [ ] Frida, mobsf, ios-tools

### Cloud (2)
- [x] AWS STS + IAM enumeration (json output → findings)
- [x] gcloud info (auth + projects + config)
- [ ] Azure CLI probe, Scout suite, Prowler

### Vulnerability Scanner (own category — queued)
- [ ] Nuclei runner with templates
- [ ] CVE search, Vulners, Exploit-DB sync

### Threat Intelligence (own category — queued)
- [ ] Shodan, Censys, MISP, OTX, IP/Domain intel, Threat feed manager

---

## Core systems

- [x] Native GTK4 + libadwaita 1.4+ shell (NavigationSplitView, NavigationPage, ToolbarView)
- [x] SQLAlchemy 2.x ORM (Workspace / Scan / Finding / Evidence / Schedule / AuditLog)
- [x] SQLite default, PostgreSQL via `GODSAPP_DATABASE_URL`
- [x] Evidence locker (content-addressed `sha256[:2]/sha256.<ext>`, integrity verify, chain-of-custody)
- [x] ScanRunner with `CompletedScan` + `FindingDTO` (no `DetachedInstanceError`), pub/sub for live stdout
- [x] FastAPI REST server (off by default, 127.0.0.1, token auth via `~/.config/godsapp/api.token`)
- [x] Click CLI (`godsapp-cli workspace|tool|scan|evidence|api|health`)
- [x] Plugin loader (drop a package into `~/.local/share/godsapp/plugins/`)
- [x] Health probe surfaced in header dot + dashboard + tooltip
- [x] Settings persisted to `~/.config/godsapp/settings.toml`
- [x] Audit log written for every workspace/scan/evidence mutation (outside open sessions — no SQLite WAL deadlocks)

## Visual / UX

- [x] **Cloud-with-lightning-bolt logo** — packaged SVG in the title bar (replaces unicode glyph)
- [x] **Logo pulsates** — opacity keyframe animation
- [x] **Off-white / cream palette** — `#fdfaf2` / `#f0e0bc` / `#ebd7af` / `#d4b87a` on `#0e0a07–#251d15`
- [x] **Transparency + blur surfaces** — `alpha()` on window, sidebar, cards (compositor-side blur on KWin/COSMIC/Mutter)
- [x] **Matrix scramble hover** — sidebar category labels and pinned items scramble-resolve on pointer enter (honors Settings toggle)
- [x] **Active window border glow / pulse** — window border pulses with state-coloured `@keyframes` (`state-idle` cream, `state-running` blue, `state-ok` green, `state-err` red); flipped automatically by `MainWindow` subscribing to `ScanRunner` events
- [ ] **Per-sidebar-row severity pulse** — sidebar rows do not yet flash on scan events (only the window border does); queued
- [x] **Settings cog on every page** — top-right gear button on Dashboard, Workspaces, Evidence, and Scan views (jumps to master Settings; the Settings view itself does not need a cog, and per-category sub-pages are queued)
- [x] **Hover effects** — cream-tinted background + butter border on tool rows and pinned items
- [ ] **Auto-fade severity pulse** — pulse currently runs continuously while state is active; auto-fade with critical-stays-until-ack queued
- [ ] **Splash screen + lock screen** with pulsating logo
- [ ] **Smooth view transitions** — basic CrossFade is enabled; richer glide/slide animations queued

## Install & packaging

- [x] `install.sh` — venv at `/opt/godsapp/venv`, app at `/opt/godsapp/app`, launcher at `/usr/local/bin/godsapp`, systemd user unit installed into the *invoking user's* `~/.config/systemd/user/` (resolves `SUDO_USER` upfront)
- [x] All data directories created upfront (logs/, cache/, evidence/, workspaces/, plugins/)
- [x] `--user` install mode (no sudo, drops into `~/.local/`)
- [x] `uninstall.sh` with `--purge` flag
- [x] `.desktop` file + cloud+bolt SVG icon installed
- [x] systemd user unit (`godsapp-api.service`) with `Environment=PYTHONPATH=/opt/godsapp/app`
- [x] libadwaita 1.4+ / GTK 4.10+ version probe with actionable error on older distros
- [x] PKGBUILD (Arch), Debian/, AppImage recipe, Flatpak manifest — present
- [ ] Final binary AppImage built, .deb signed, Flatpak submitted to Flathub
- [x] `setuptools.build_meta` backend, `install.sh` runs `pip install .` (Meli lesson baked in)

---

## What ships in **this wave** (you're looking at it)

1. All 12 sidebar tool categories now populated with at least 2 real tools (30 total subprocess wrappers).
2. Cream/ivory palette with translucent `alpha()` surfaces.
3. Cloud + lightning-bolt SVG logo in the title bar with opacity pulse.
4. State-coloured animated window border (idle / running / ok / err) driven by scan runner events.
5. Matrix-scramble hover effect on sidebar labels.
6. Settings cog on every page.
7. All sidebar pinned items (Dashboard / Workspaces / Evidence / Settings) navigate to real, working views — no dead ends.

## What's queued for the **next wave** (in priority order)

1. **Vulnerability Scanner category** — Nuclei runner with template management.
2. **Threat Intelligence views** — Shodan, Censys, MISP, OTX, IP / Domain intel.
3. **Findings Manager** — promote scan result → Finding with CVSS / CVE / MITRE tagging.
4. **Per-category Settings sub-pages** — 17 sub-pages reachable from each page's cog.
5. **Reports generator** — HTML/Markdown/PDF aggregating scans + findings + evidence.
6. **Embedded Terminal** (VTE) and **API Console UI**.
7. **Scheduler UI + cron loop**, **Plugin marketplace UI**, **Replay Engine**.
8. **Auto-fading severity pulse** + splash/lock screen with logo.

If any priority should shift, tell me and I'll re-order the next push.
