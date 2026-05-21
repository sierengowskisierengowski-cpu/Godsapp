# Changelog

All notable changes to GodsApp.

## [0.2.0] — 2026-05-21

### Added — Tool categories
- **All 11 previously-empty tool categories now ship with real subprocess wrappers.** 30 tools total across 12 categories — every sidebar header now opens with at least 2 tools, no more `0` counts.
  - **Web**: gobuster-dir, nikto, whatweb
  - **Network**: masscan, traceroute, ss-listen
  - **Password**: hashcat (10 hash modes), john, hydra (9 services)
  - **Exploit**: searchsploit, msfvenom
  - **Wireless**: iwlist-scan, airodump-ng
  - **Forensics**: binwalk, exiftool, strings
  - **Malware**: yara, clamscan
  - **OSINT**: theharvester, whois, sherlock
  - **Crypto**: openssl-hash, openssl-cipher, codec (pure-Python: base64/32/hex/url/rot13/ascii85)
  - **Mobile**: adb, apktool (with manifest permission scan)
  - **Cloud**: aws-sts (+ IAM enumeration), gcloud-info
- Each tool: real binary check (`requires_binary`), declarative `ToolOption`s auto-rendered by `ScanView`, live stdout/stderr stream, regex-parsed findings with severity heuristics, artifact paths captured.

### Added — Visual / UX
- **Cloud-with-lightning-bolt SVG logo** — packaged at `godsapp/resources/icons/godsapp-logo.svg` and `packaging/com.sierengowski.GodsApp.svg`. Rendered in the title bar via `Gtk.Image` with an opacity-pulse CSS animation.
- **Cream / ivory palette on translucent dark base** — `#fdfaf2 / #f0e0bc / #ebd7af / #d4b87a` foregrounds, `alpha()` on window/sidebar/cards so blur-capable compositors (KWin, COSMIC, Mutter) frost the panels.
- **State-coloured animated window border** — `state-idle` (cream), `state-running` (blue), `state-ok` (green), `state-err` (red) with `@keyframes` border-pulse animations. `MainWindow` subscribes to `ScanRunner` events and swaps the class automatically.
- **Matrix-scramble text effect on hover** — sidebar category labels and pinned items scramble-resolve when the pointer enters. Reads `Settings.ui.matrix_scramble` each hover so toggling Settings takes effect immediately.
- **Active sidebar row pulse** — selected tool rows pulse cream/butter to indicate the live view.
- **Settings cog on every page** — `page_header()` helper adds a top-right gear that navigates to the master Settings view (per-category sub-pages queued).
- **Toast overlay** — wired around the content stack so views can surface non-blocking notifications.

### Added — Status & docs
- `STATUS.md` at repo root: honest implementation checklist for every view, category, and tool.
- This changelog.
- `replit.md` updated with v0.2.0 milestone.

### Fixed
- `EvidenceView._toast_overlay` reference now resolves — `MainWindow` exposes `_toast_overlay`.
- Pinned sidebar items refresh their backing view on entry (workspaces/evidence/dashboard re-query the DB) so the page never displays stale data.

## [0.1.0] — 2026-05-20

### Added — Foundation
- Native GTK4 + libadwaita 1.4+ shell: header bar, sidebar with 12 tool categories, content stack, dashboard, workspaces, evidence, settings, per-tool scan view.
- SQLAlchemy 2.x DB layer with Workspace / Scan / Finding / Evidence / Schedule / AuditLog models. SQLite default, PostgreSQL via `GODSAPP_DATABASE_URL`.
- Core services: workspaces CRUD, evidence ingest with SHA-256 content-addressing + chain-of-custody, scan runner with `CompletedScan` / `FindingDTO` (no DetachedInstanceError), audit log, health probe, settings (`settings.toml`).
- Recon tools: Nmap (XML parse), subdomain brute.
- FastAPI REST server (off by default, 127.0.0.1, token auth via `~/.config/godsapp/api.token`).
- Click CLI: `godsapp-cli workspace|tool|scan|evidence|api|health`.
- `install.sh` (Meli-pattern: `SUDO_USER`-aware, venv at `/opt/godsapp/venv`, all data dirs created upfront, libadwaita 1.4+ probe), `uninstall.sh`, `.desktop`, launcher, systemd user unit.
- Packaging recipes: PKGBUILD (Arch), debian/, AppImage, Flatpak.
- README, CONTRIBUTING, smoke tests.
