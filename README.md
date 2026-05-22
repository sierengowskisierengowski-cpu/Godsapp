# GodsApp

**Professional security auditing & research suite — native GTK4 Linux desktop application.**

Author: Joseph Sierengowski · License: GPL-3.0-or-later

GodsApp unifies reconnaissance, web app testing, network analysis, password auditing, exploitation, OSINT, forensics, malware analysis, crypto, mobile and cloud auditing into one cohesive Adwaita desktop interface. Tools run as managed subprocesses with live output, structured findings, and a tamper-evident evidence locker.

> **Build status:** see [`STATUS.md`](../STATUS.md) at the repo root for the honest checkbox-by-checkbox status of every view, category, and tool. Boxes are only checked when the feature is actually wired up and does its real job — no placeholders.

Visual identity: warm cream / ivory foreground on a translucent deep-brown base, cloud-with-lightning-bolt logo (pulsates), state-coloured animated window border (idle / running / ok / error), matrix-scramble hover effect on navigation labels.

---

## ⚠️ Authorization, Intended Use & Legal Notice

GodsApp is a **defensive-security, research, and home-lab tool.** It is designed to be run by its operator against their own infrastructure — their own systems, their own network, their own devices, their own lab environment, or systems for which they hold explicit written authorization to test. That is the only use it is designed, intended, or supported for.

**Intended for:**
- Reconnaissance, web-application testing, network analysis, password auditing, exploitation research, OSINT, forensics, malware analysis, and related security work against infrastructure you own or are explicitly authorized to test.
- Capturing, analyzing, and visualizing traffic, devices, and activity on networks you own or administer.
- Organizing engagement evidence, findings, and reports for your own authorized security work.

**Not for:**
- Monitoring, capturing, or analyzing traffic on networks you do not own or are not explicitly authorized to monitor.
- Surveilling, tracking, or profiling other people, their devices, or their communications without their knowledge and consent.
- Scanning, probing, exploiting, or accessing any system, network, device, or account that you do not own or have explicit written authorization to test.
- Any activity that violates applicable local, state, federal, or international law.

**Your responsibility:** You — the operator — are solely responsible for ensuring your use of this software is lawful in your jurisdiction and authorized for the systems and networks you point it at. Laws governing network monitoring, packet capture, wireless interception, and security testing vary significantly by location. Active scanning, brute-force, or exploitation against systems you do not own is almost always a crime without prior written authorization. **When in doubt, don't** — get written authorization first, or limit the tool to infrastructure you unambiguously own.

**No warranty.** This software is provided "as is." The author is not liable for any misuse or for any damages arising from its use. Use entirely at your own risk.

Full notice: [**DISCLAIMER.md**](./DISCLAIMER.md). GPL-3.0-or-later license applies separately (see `LICENSE`).

---

## Install

### Quick install (Arch / Debian / Fedora)

```bash
git clone https://github.com/jsierengowski/godsapp
cd godsapp
sudo ./install.sh           # system install — /opt/godsapp
# or
./install.sh --user         # user-only install — ~/.local/opt/godsapp
```

The installer:

- Creates a venv at `/opt/godsapp/venv` with `--system-site-packages` (so PyGObject can see GTK4).
- Installs the `godsapp` package **into the venv** with `pip install` (not a `PYTHONPATH` hack).
- Drops launchers at `/usr/local/bin/godsapp` and `/usr/local/bin/godsapp-cli`.
- Installs a `.desktop` entry so GodsApp appears in your application menu.
- Creates every data directory upfront: `~/.local/share/godsapp/{logs,cache,evidence,workspaces,plugins}`.
- Writes a `godsapp-api.service` systemd **user** unit (disabled by default).

### System prerequisites (one-time per machine)

| Distro | Command |
| --- | --- |
| Arch | `sudo pacman -S python python-gobject gtk4 libadwaita` |
| Debian/Ubuntu | `sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1` |
| Fedora | `sudo dnf install python3 python3-gobject gtk4 libadwaita` |

### Arch (AUR)

```bash
# After AUR submission:
yay -S godsapp
```

### Debian package

```bash
cd godsapp
dpkg-buildpackage -us -uc -b
sudo dpkg -i ../godsapp_0.1.0-1_all.deb
```

### AppImage

```bash
cd godsapp/packaging/appimage
appimage-builder --recipe AppImageBuilder.yml
```

### Flatpak

```bash
cd godsapp/packaging/flatpak
flatpak-builder build com.sierengowski.GodsApp.yml --install --user
```

---

## Run

```bash
godsapp                       # launch GUI
godsapp-cli --help            # CLI mode
godsapp-cli health            # backend + tool availability snapshot
```

### REST API (optional, off by default)

```bash
systemctl --user enable --now godsapp-api
# Token is generated at ~/.config/godsapp/api.token (chmod 600)
curl -H "Authorization: Bearer $(cat ~/.config/godsapp/api.token)" \
  http://127.0.0.1:7842/v1/tools
```

---

## Storage layout

```
~/.config/godsapp/
    settings.toml          # user settings
    api.token              # 256-bit token for REST auth
~/.local/share/godsapp/
    godsapp.db             # SQLite (default backend)
    logs/                  # rotating logs
    evidence/              # content-addressed locker (sha256-named)
    workspaces/            # per-workspace working trees
    plugins/               # drop-in plugin packages
    cache/                 # transient tool caches
```

Power users with large datasets can switch to PostgreSQL:

```bash
export GODSAPP_DATABASE_URL='postgresql+psycopg://user:pass@localhost/godsapp'
godsapp
```

…or set `[database].url` in `~/.config/godsapp/settings.toml` and install the `psycopg` extra.

---

## CLI quickstart

```bash
godsapp-cli workspace create "ACME engagement" --target acme.example.com
godsapp-cli tools
godsapp-cli scan run --workspace "ACME engagement" --tool nmap \
    --target scanme.nmap.org --arg profile=default
godsapp-cli evidence ingest ~/captures/dump.pcap --workspace "ACME engagement"
godsapp-cli evidence list
```

---

## Plugins

A plugin is a Python package placed under `~/.local/share/godsapp/plugins/<name>/`.
Its `__init__.py` registers `Tool` subclasses via `godsapp.tools.registry.registry.register(...)`.
See `godsapp/plugins/__init__.py` for the documented contract and a minimal example.

---

## Uninstall

```bash
sudo ./uninstall.sh                 # remove app, keep data
sudo ./uninstall.sh --purge         # remove app AND ~/.local/share/godsapp + ~/.config/godsapp
```

---

## Project layout

```
godsapp/
    godsapp/                # Python package
        app/                # GTK Application bootstrap
        ui/                 # GTK4 + libadwaita views
        core/               # workspaces, evidence, scans, health, audit
        db/                 # SQLAlchemy models + engine
        api/                # FastAPI REST server
        cli/                # Click CLI
        tools/              # built-in tool implementations
        plugins/            # plugin authoring docs (user plugins live in ~/.local/share)
        resources/          # CSS, icons
    packaging/              # PKGBUILD, debian/, appimage/, flatpak/
    install.sh / uninstall.sh
    pyproject.toml
    README.md
```

---

## Status

Initial release wires the foundation, install path, packaging, and the **recon** tool category (nmap + DNS-based subdomain enumeration). Remaining 11 categories ship as plugins or additional built-ins in subsequent releases — the registry + UI handle them automatically once the tool subclass is registered.
