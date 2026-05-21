# GodsApp

Native GTK4 + libadwaita desktop application providing a unified interface for security auditing & research (recon, web app testing, network analysis, password auditing, exploitation, OSINT, forensics, malware analysis, crypto, mobile, cloud, wireless). Built by Joseph Sierengowski. This Replit workspace is the source-of-truth repository — the app itself is installed and run on a Linux desktop (COSMIC, GNOME, KDE — anything with GTK4 + libadwaita).

## Source of truth

All app code lives at `./godsapp/`:

```
godsapp/
    pyproject.toml          # setuptools.build_meta backend
    install.sh              # installs into /opt/godsapp/{venv,app}
    uninstall.sh
    godsapp/                # the actual Python package
        app/                # GTK Adw.Application bootstrap
        ui/                 # GTK4 + libadwaita views
        core/               # workspaces, evidence, scans, health, audit, settings, paths
        db/                 # SQLAlchemy 2.x models + engine + migrations
        api/                # FastAPI REST server (off by default, 127.0.0.1)
        cli/                # Click CLI
        tools/              # built-in tools (recon/nmap, recon/subdomain-brute)
        plugins/            # plugin authoring contract
        resources/css/      # Adwaita CSS overrides (cream/ivory on dark)
    packaging/              # PKGBUILD, debian/, appimage/, flatpak/
    tests/                  # pytest smoke tests
```

## Run & operate (on the user's Linux box)

- Install:        `sudo ./install.sh` (or `./install.sh --user`)
- Launch GUI:     `godsapp`
- CLI:            `godsapp-cli --help`
- Health probe:   `godsapp-cli health`
- Enable API:     `systemctl --user enable --now godsapp-api`
- Uninstall:      `sudo ./uninstall.sh` (add `--purge` to wipe user data)

System prereqs (one-time): `python3 (>=3.12) python-gobject gtk4 libadwaita`.

## Storage

- Config:  `~/.config/godsapp/` (settings.toml, api.token)
- Data:    `~/.local/share/godsapp/` (godsapp.db, logs/, evidence/, workspaces/, plugins/, cache/)
- DB:      SQLite (default) or PostgreSQL via `GODSAPP_DATABASE_URL`

## Architecture decisions

- **`setuptools.build_meta` backend** in pyproject (Meli lesson: `flit_core` blows up on packages with native deps in transitive trees).
- **install.sh runs `pip install .`** into the venv. Never relies on `PYTHONPATH` for the app code — only for systemd units. (Meli lesson.)
- **`json.dumps(..., default=str)` centralised in `core/jsonx.py`** — every datetime, Path, UUID renders safely. (Meli lesson.)
- **install.sh creates every data directory upfront** so first launch never hits a missing-dir error. (Meli lesson.)
- **Backend health is surfaced in the header bar and dashboard** so the user can see DB/API/tool availability instead of buttons silently doing nothing. (Meli lesson.)
- **Evidence locker is content-addressed (`sha256[:2]/sha256.<ext>`)** so duplicate ingests collapse and integrity is verifiable; every action lands in a chain-of-custody row.
- **Generic `ScanView` auto-renders forms from `tool.options`** — adding a new tool means subclassing `Tool` and registering; UI/CLI/API pick it up automatically.
- **`ScanRunner.run()` returns a `CompletedScan` dataclass (not the ORM row)** with findings eagerly snapshotted to `FindingDTO`s inside the session. Returning the live `Scan` row after the session closed caused `DetachedInstanceError` whenever the UI/CLI/API touched `.findings`.
- **All `audit()` calls happen AFTER the originating `with get_session():` block closes.** SQLite is single-writer; nesting `audit()` (which opens its own session) inside an open transaction reliably deadlocks under WAL.
- **install.sh resolves the *invoking* user via `SUDO_USER` upfront** and writes data dirs + the systemd user unit directly into that user's `~/.config/systemd/user/`. Writing to `/etc/skel` only seeds *future* users; existing users would never find the unit.
- **Baseline is libadwaita 1.4+ / GTK 4.10+** (Arch, Fedora 39+, Ubuntu 24.04+, Debian 13). The UI uses `Adw.NavigationSplitView`, `Adw.NavigationPage`, `Adw.ToolbarView`, and `Gtk.FileDialog` — all introduced in that range. install.sh probes for those symbols and bails with an actionable error on older stacks (Debian 12 → use the Flatpak or AppImage).

## Replit workspace notes

The only other thing in the workspace is `artifacts/mockup-sandbox/` — Replit canvas infrastructure, untouched. The Python app cannot render in Replit's preview pane (GTK4 needs an X/Wayland display); development feedback loop is: the user installs locally on their COSMIC machine and reports bugs.

## User preferences

- Author: Joseph Sierengowski
- App ID: `com.sierengowski.GodsApp`
- License: GPL-3.0-or-later
- Aesthetic: warm cream/ivory on a deep dark base; bolt-glyph branding
- Quality bar: real implementations only — no placeholders, no "coming soon"
- Distribution: install.sh + PKGBUILD + .deb + AppImage + Flatpak (all paths supported)

## Gotchas

- Venv MUST be created with `--system-site-packages` so PyGObject can see the distro's GTK4 typelibs. The installer does this automatically.
- The systemd user unit needs `Environment=PYTHONPATH=/opt/godsapp/app` if the launcher is bypassed; the bundled launcher (`/usr/local/bin/godsapp`) calls the venv binary directly, so PYTHONPATH is only used as a belt-and-suspenders.
- On Debian/Ubuntu, `gir1.2-adw-1` is sometimes named `gir1.2-libadwaita-1` on older releases; the installer surfaces a clear error if it can't import `Adw`.

## Status — v0.6.0 (latest)

**In-app updater.**

- **`core/updater.py`** — stdlib-only (urllib) check against the GitHub Releases feed for `sierengowskisierengowski-cpu/Godsapp`. Override via `Settings.updates.feed_url` for self-hosted mirrors. Picks first non-draft release matching the channel (stable or include-prereleases), grabs the `godsapp-*.tar.gz` asset, optionally verifies a sibling `.sha256`, and runs `install.sh` under `pkexec` (or `--user` if `updates.user_scope`). Pre-release-aware semver comparator (`is_newer`). `should_auto_check()` throttles checks by `check_interval_hours` (default 24 h).
- **`ui/updater_dialog.py`** — three states (idle / up-to-date / update-available). Worker thread does HTTP + tarball download + extraction + install spawn; main loop polls subprocess every 500 ms via `GLib.timeout_add` and pulses an `Adw.ProgressBar`. Closing the dialog cancels everything (`InstallProcess.cancel()`). Safe extraction refuses path-traversing tar entries.
- **App startup** does a background check after scheduler init. When newer than the running build (and not equal to `updates.skipped_version`) it surfaces an `Adw.Toast` with an "Update…" button → opens the dialog with the result preloaded.
- **Settings → Updates** sub-page: auto-check toggle, interval (1–720h), include-prereleases, user-scope install, custom feed URL, read-only fields for last-checked / last-seen / skipped-version.
- **CLI**: `godsapp-cli update check` (exit 0 up-to-date, 2 on error) and `godsapp-cli update install [--user] [--include-prereleases]` — same backend, with progress printed to stderr.
- **GAction `app.check-for-updates`** registered so palette / menu / slash commands can trigger the dialog.

Tarballs: `./dist/godsapp-0.6.0.tar.gz` and `./dist/godsapp-0.6.0.zip`.

## Status — v0.5.0

**Missing-tools UX: install guidance + per-tool overrides.**

- **Tool catalog** (`core/tool_catalog.py`): 38 entries with acceptable binary names (tuple, not string), per-distro install commands (pacman/apt/dnf/zypper/xbps/brew/pipx/pip/go), category, difficulty, unlocks, alternatives, and gotcha notes. Solves the `metasploit → msfconsole` mismatch and similar cases (tshark/wireshark-cli, yara/yarac, aws/aws-cli, theHarvester casing, sherlock-project pip name).
- **Detection** (`core/tool_detect.py`): walks override path → `$PATH` for every catalog binary → standard install dirs (`/usr/bin`, `/usr/local/bin`, `/usr/sbin`, `/opt/bin`, `~/.local/bin`, `~/go/bin`, `~/.cargo/bin`, `/snap/bin`, `/var/lib/flatpak/exports/bin`, pipx venv `*/bin`). `test_binary()` runs `--version`/`-V`/`-v`/`--help` to verify. `detect_pkg_manager()` reads `/etc/os-release` (ID + ID_LIKE) and maps to a package manager.
- **Missing Tools dialog** (`ui/missing_tools_dialog.py`): grid of expandable cards per tool with badges (category, difficulty, status), live re-detection after every action. Per-tool: **Install now** (pkexec sh -c, live subprocess polling), **Copy** install command, **Other package managers** expander, **I have this installed…** (file picker → writes to `settings.tool_paths.overrides[tool_id]`), **Skip this tool** (writes to `settings.tool_paths.skipped`). **Install all missing** groups commands by package manager and runs them as `pkexec sh -c 'cmd1 && cmd2'` — one privilege prompt per manager.
- **Dashboard system-status card is clickable** (Gtk.GestureClick) → opens Missing Tools dialog. Skipped tools hidden from the missing counter; shows `(N skipped)` suffix and `➜ click to install` hint when applicable.
- **ScanView shows an Adw.Banner** under the header whenever the selected tool's binary is missing, with an **Install…** button opening the dialog focused on that exact tool. Closing the dialog re-detects and hides the banner.
- **Settings → Tool Paths** sub-page: every catalog tool listed with its resolved path (`✓ <path> [override|extra-dir|PATH]` or `✗ missing`), with per-row pick/test/clear buttons and a global "Re-detect all tools" action.
- **`core/health.py`** rewritten — delegates entirely to the catalog + detector. `HealthReport` gained `tool_paths` and `skipped` fields. `EXTERNAL_TOOLS` is derived from the catalog now, so it stays in sync without manual edits.
- **`ToolPathsSettings`** added to `core/settings.py` (`overrides: dict[str,str]`, `skipped: list[str]`).

Tarballs: `./dist/godsapp-0.5.0.tar.gz` and `./dist/godsapp-0.5.0.zip`.

## Status — v0.4.1

**Polish pass: terminal + storm.**

- **Terminal**: always-visible header toggle button (⚡ + `utilities-terminal-symbolic`), occupies the full workspace area (moved into the content pane's `Gtk.Overlay` so it spans everything below the header and to the right of the sidebar, resizing dynamically), pinned ASCII header + status line, persistent shell session on hide, one-click VTE install via `pkexec` with per-distro package detection (Arch / Fedora / Debian / openSUSE / Void).
- **Storm audio**: `core/audio.play_async(name, volume=…)` now passes backend-native volume flags (`paplay --volume`, `pw-play --volume`, `ffplay -volume`, `mpv --volume`). Close strikes pull from `thunder_strike|crackle|close.wav` at the strike-volume slider; distant strikes pull from `thunder_distant|rumble|rolling.wav` at the rumble-volume slider. Frame-accurate audio↔visual sync — the sound fires the same monotonic tick the bolt is born. Per-strike ±10% jitter so it never repeats. Silent when slider × preset multiplier ≤ 0.005.
- **Storm visuals**: 5-layer composite with razor-thin sub-pixel core for close strikes, 3-layer paler/narrower for distant; brief retinal-burn afterglow after each bolt dies. Close vs distant variation — ~80% distant (upper-third, soft top-down sky glow) / 20% close (full window, warm white veil flash 30–65% inten · 320 ms). Auto-pauses during scans (configurable).
- **Settings → General**: new dropdowns/sliders for Storm preset (Whisper/Drizzle/Standard/Heavy), Strike frequency (Sparse/Moderate/Frequent), Strike volume, Rumble volume, Distance variation toggle, Auto-pause-during-scans toggle, and a Terminal `auto_install_vte` toggle.
- `LightningOverlay` polls settings every 10s so changes take effect live without restarting.

Tarballs: `./dist/godsapp-0.4.1.tar.gz` and `./dist/godsapp-0.4.1.zip`.

## Status — v0.4.0

**Five-feature push: discoverability + accuracy.**

- **First-launch onboarding tour** (`ui/onboarding.py`) — 8-step centred card walking through Workspaces, sidebar search, Findings, Evidence, command palette, terminal summoning. Skippable, persists `onboarding.completed`, re-launchable from Settings or `/tour` slash command. Singleton-guarded so the CTAs ("Open Workspaces", "Focus sidebar", "Open palette") can interact with the live main window without stacking duplicates.
- **Learn Mode framework** (`core/learn.py`) — structured `LearnEntry` (summary, when, how, options, examples, pitfalls, references) with shipped content for `nmap`, `sqlmap`, `hydra`, `subdomain-brute`, `hashcat`, `gobuster`. Difficulty levels (beginner/intermediate/expert) render as coloured dots in the sidebar. Settings toggle. Tools fall back to `name` as the Learn key when `learn_key` is blank.
- **Workspace templates** (`core/templates.py`) — 10 starters: Blank, Bug Bounty, External Pentest, Internal Pentest, Red Team, Threat Hunt, Forensics, CTF, Compliance, Home Lab. Each ships default target, tags, recommended tools, and a markdown welcome note written as the workspace's `README.md`. Picker dropdown in the new-workspace dialog auto-fills empty fields.
- **Findings dedup + chaining** (`core/dedup.py` + new `FindingLink` table) — weighted score: host 0.20, port 0.10, CVE overlap 0.25, MITRE technique 0.10, title similarity 0.25, description tokens 0.10. Each finding row gets a 🔗 button opening a dialog with ranked matches, per-match reasons, and a kind picker (duplicate / related / chain / supersedes). Duplicate links auto-mark the newer finding `status=duplicate`. Canonical (min,max) ID ordering avoids storing both directions. Thresholds stored as 0–100 ints in Settings → Findings Dedup.
- **Command palette enhancements** (`ui/command_palette.py`) — now indexes live workspaces + most-recent 200 findings, six slash commands (`/tour /learn /terminal /refresh /dashboard /help`), `#tag` filter syntax (`#critical`, `#high`, `#beginner`, `#expert`, status tags). Static commands cached at first open; dynamic DB-backed sources fetched in a worker thread and appended via `extend_commands()` so the palette never blocks on disk I/O. The cached static list is copied per-open so the palette never pollutes the cache.

`FindingLink` table is created via `init_db()`'s `create_all` on next launch — no Alembic migration required. v0.4.0 release lives in `./dist/godsapp-0.4.0.tar.gz` and `./dist/godsapp-0.4.0.zip`.

## Status — v0.3.1

**OLYMPUS polish pass.** Aesthetic shifted to "Mount Olympus": cloud-white foregrounds + sky-blue mid-tones + divine-gold (`#f0d27a`) accents on a deep twilight base. Animated 4-layer radial-gradient aurora drifts across the window every 28s. Sidebar gets a gold/cloud fluted-column edge (inset box-shadows); cards get a gold capital + column-stripe flourish. SVG logo rebuilt with radial cloud + sky halo + gold bolt.

**New muscle.**
- Command palette (`Ctrl+K`) with fuzzy search across every page, tool, and settings anchor (`ui/command_palette.py`). Down/Up to navigate, Enter to jump.
- Header-bar search trigger button (clickable + shortcut hint) opens the palette.
- Sidebar live-search filter at the top — type to narrow the tool list.
- Bottom status bar: STATUS · TOOLS · DB · API + shortcut hint, kept in sync with health probe and scan-runner events.
- Keyboard shortcuts: `Ctrl+K` palette, `Ctrl+,` settings, `Ctrl+F` focus sidebar search, `F5` refresh, `Esc` dashboard, `Ctrl+1..9` jump to pinned items.
- Dashboard 2.0: KPI tiles with 7-day deltas, severity-distribution bars, recent-activity feed (latest 12 scans across all workspaces), quick-action launcher tiles, system status card.
- Findings → CSV export button: writes filtered findings to `~/.local/share/godsapp/evidence/exports/findings-<UTC>.csv` and surfaces a toast.

Bumped to v0.3.1; install.sh still uses `--force-reinstall --no-deps`.

## Status — v0.2.0

- All 12 sidebar tool categories populated with **real subprocess wrappers** (30 tools total). Web, network, password, exploit, wireless, forensics, malware, osint, crypto, mobile, cloud all ship.
- Cream / ivory off-white palette on translucent dark base; `alpha()` surfaces on window, sidebar, cards (compositor-side blur on KWin/COSMIC/Mutter).
- Cloud-with-lightning-bolt SVG logo in the title bar with opacity-pulse keyframe animation. Same SVG used as the app icon.
- State-coloured animated window border (`state-idle` cream / `state-running` blue / `state-ok` green / `state-err` red) driven by `ScanRunner` event subscription.
- Matrix-scramble hover effect on sidebar category labels and pinned items (reads `Settings.ui.matrix_scramble` each hover).
- Settings cog on every page (Dashboard / Workspaces / Evidence / Scan views) → jumps to master Settings. Per-category sub-pages queued.
- Pinned items refresh their underlying view on entry so the data is never stale.
- `STATUS.md` at repo root tracks every view / category / tool with honest checkboxes. `CHANGELOG.md` documents both v0.1.0 and v0.2.0.

See `STATUS.md` for the full implementation matrix and the prioritised next-wave list.

## Status — v0.1.0

Foundation complete:
- Wipe of legacy Node/web GodsApp ✓
- Python project skeleton + pyproject ✓
- SQLAlchemy DB layer ✓
- Core services (workspaces, evidence, scans, health, audit, registry) ✓
- GTK4 + Adwaita shell (header, sidebar, 12 category sections, dashboard, workspaces, evidence, settings) ✓
- Recon category fully wired (nmap + subdomain-brute) ✓
- FastAPI REST server (off by default, token auth) ✓
- Click CLI (workspace, tool, scan, evidence, api, health) ✓
- install.sh + uninstall.sh + .desktop + launcher + systemd user unit ✓
- PKGBUILD, debian/, AppImage recipe, Flatpak manifest ✓
- README + CONTRIBUTING ✓
- Smoke tests ✓

Follow-ups (planned after install verification on COSMIC):
- Remaining 11 tool categories (web, network, password, exploit, wireless, forensics, malware, osint, crypto, mobile, cloud) — each follows the proven pattern (`Tool` subclass → register → auto-rendered in UI/CLI/API).
- Report generator (HTML/PDF/markdown export aggregating scans + findings + evidence per workspace).
- Scheduler executing the `schedules` table on a cron-like timer.
- Plugin marketplace UI (install/uninstall plugins from a curated index).
