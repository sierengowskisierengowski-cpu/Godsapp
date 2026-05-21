#!/usr/bin/env bash
# GodsApp installer — installs into /opt/godsapp with a private venv,
# wires up systemd user services, .desktop entry, and a CLI launcher.
#
# Usage:
#   sudo ./install.sh            # system install
#   ./install.sh --user          # user install under ~/.local
#
set -euo pipefail

USER_INSTALL=0
if [[ "${1:-}" == "--user" ]]; then
    USER_INSTALL=1
fi

APP_NAME="godsapp"
APP_ID="com.sierengowski.GodsApp"

# Resolve the *invoking* user (the human, not root) and their home directory
# upfront. Under `sudo ./install.sh`, $HOME is root's home — using it would
# create data dirs and systemd units in the wrong place.
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    TARGET_USER="${SUDO_USER}"
    TARGET_HOME="$(getent passwd "${SUDO_USER}" | cut -d: -f6)"
else
    TARGET_USER="${USER:-$(id -un)}"
    TARGET_HOME="${HOME}"
fi
if [[ -z "${TARGET_HOME}" || ! -d "${TARGET_HOME}" ]]; then
    echo "Error: could not resolve target user's home directory." >&2
    exit 1
fi

if [[ $USER_INSTALL -eq 0 ]]; then
    if [[ $EUID -ne 0 ]]; then
        echo "Error: system install needs root. Use sudo ./install.sh or pass --user." >&2
        exit 1
    fi
    PREFIX="/opt/${APP_NAME}"
    BIN="/usr/local/bin/${APP_NAME}"
    BIN_CLI="/usr/local/bin/${APP_NAME}-cli"
    DESKTOP_DIR="/usr/share/applications"
    ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
else
    PREFIX="${TARGET_HOME}/.local/opt/${APP_NAME}"
    BIN="${TARGET_HOME}/.local/bin/${APP_NAME}"
    BIN_CLI="${TARGET_HOME}/.local/bin/${APP_NAME}-cli"
    DESKTOP_DIR="${TARGET_HOME}/.local/share/applications"
    ICON_DIR="${TARGET_HOME}/.local/share/icons/hicolor/scalable/apps"
fi
# Always install the systemd unit into the *invoking* user's config dir so
# `systemctl --user enable --now godsapp-api` works for them on first try.
SYSTEMD_USER_DIR="${TARGET_HOME}/.config/systemd/user"

VENV="${PREFIX}/venv"
APP_DIR="${PREFIX}/app"

echo "==> Installing GodsApp to ${PREFIX}"

command -v python3 >/dev/null || { echo "python3 not found"; exit 1; }
PYTHON="$(command -v python3)"

# 1. Check GTK4 + libadwaita system deps are present
missing=()
for binlib in gtk4-launch; do
    command -v "$binlib" >/dev/null 2>&1 || missing+=("$binlib")
done
if ! "$PYTHON" -c "import gi; gi.require_version('Gtk','4.0'); gi.require_version('Adw','1')" 2>/dev/null; then
    cat >&2 <<EOF
Error: PyGObject can't load GTK4 + libadwaita.

Install system packages first:
  Arch:    sudo pacman -S python python-gobject gtk4 libadwaita
  Debian:  sudo apt install python3 python3-gi gir1.2-gtk-4.0 gir1.2-adw-1
  Fedora:  sudo dnf install python3 python3-gobject gtk4 libadwaita
EOF
    exit 1
fi

# GodsApp's UI uses Adw.NavigationSplitView / Adw.ToolbarView (libadwaita 1.4+)
# and Gtk.FileDialog (GTK 4.10+). Bail early with an actionable error rather
# than crash at first launch.
if ! "$PYTHON" - <<'PY' 2>/dev/null
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk
missing = []
for name in ('NavigationSplitView', 'NavigationPage', 'ToolbarView'):
    if not hasattr(Adw, name):
        missing.append(f'Adw.{name}')
if not hasattr(Gtk, 'FileDialog'):
    missing.append('Gtk.FileDialog')
import sys
sys.exit(1 if missing else 0)
PY
then
    cat >&2 <<EOF
Error: your GTK4 / libadwaita is too old for GodsApp.

GodsApp requires:
  - libadwaita >= 1.4   (ships in Arch, Fedora 39+, Ubuntu 24.04+, Debian 13/trixie)
  - GTK >= 4.10         (same baseline)

On Debian 12 (bookworm) the libadwaita is 1.2 and lacks NavigationSplitView.
Upgrade your distro, use the Flatpak build, or use the AppImage build instead.
EOF
    exit 1
fi

# 2. Layout
mkdir -p "${APP_DIR}" "${VENV%/*}"
echo "==> Copying source to ${APP_DIR}"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"
rsync -a --delete --exclude '__pycache__' --exclude '*.egg-info' --exclude 'dist' --exclude 'build' \
    "${SRC_DIR}/godsapp/" "${APP_DIR}/godsapp/"
cp "${SRC_DIR}/pyproject.toml" "${APP_DIR}/pyproject.toml"
cp "${SRC_DIR}/README.md" "${APP_DIR}/README.md" 2>/dev/null || true

# 3. Build venv with system GTK access AND install the package into it
echo "==> Creating venv (with system site-packages for PyGObject)"
"$PYTHON" -m venv --system-site-packages "${VENV}"
"${VENV}/bin/pip" install --upgrade pip wheel setuptools
echo "==> Uninstalling any prior godsapp wheel from the venv (clean slate)"
"${VENV}/bin/pip" uninstall -y godsapp 2>/dev/null || true
echo "==> Installing godsapp into the venv"
"${VENV}/bin/pip" install --force-reinstall --no-deps --no-cache-dir "${APP_DIR}"
"${VENV}/bin/pip" install --no-cache-dir "${APP_DIR}"

# 3a. VERIFY the non-Python resources (CSS, SVG) actually landed in the wheel.
# If package-data isn't being shipped properly the in-app theme silently
# falls back to default Adwaita — looks broken without any error message.
SITE_PKG="$("${VENV}/bin/python" -c 'import godsapp, os; print(os.path.dirname(godsapp.__file__))')"
echo "==> Installed package dir: ${SITE_PKG}"
MISSING_RES=0
for res in resources/css/style.css resources/icons/godsapp-logo.svg; do
    if [[ -f "${SITE_PKG}/${res}" ]]; then
        echo "    ✓ ${res}"
    else
        echo "    ✗ MISSING: ${res}"
        MISSING_RES=1
    fi
done
if [[ ${MISSING_RES} -eq 1 ]]; then
    echo "==> package-data missing — copying resources directly into ${SITE_PKG}"
    cp -r "${APP_DIR}/godsapp/resources/"* "${SITE_PKG}/resources/" 2>/dev/null || \
        cp -r "${APP_DIR}/godsapp/resources" "${SITE_PKG}/"
fi
# Always also nuke stale bytecode so an older cached CSS path isn't replayed
find "${SITE_PKG}" -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
INSTALLED_VERSION="$("${VENV}/bin/python" -c 'import godsapp; print(godsapp.__version__)')"
echo "==> Installed version: ${INSTALLED_VERSION}"

# 4. Launcher scripts (so users never need PYTHONPATH)
mkdir -p "$(dirname "${BIN}")"
cat > "${BIN}" <<EOF
#!/usr/bin/env bash
exec "${VENV}/bin/godsapp" "\$@"
EOF
chmod 0755 "${BIN}"

cat > "${BIN_CLI}" <<EOF
#!/usr/bin/env bash
exec "${VENV}/bin/godsapp-cli" "\$@"
EOF
chmod 0755 "${BIN_CLI}"

# 5. .desktop entry
mkdir -p "${DESKTOP_DIR}" "${ICON_DIR}"
cat > "${DESKTOP_DIR}/${APP_ID}.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=GodsApp
GenericName=Security Research Suite
Comment=Professional security auditing and research suite
Exec=${BIN} %U
Icon=${APP_ID}
Categories=Security;Network;System;
Terminal=false
StartupNotify=true
StartupWMClass=${APP_ID}
Keywords=security;pentest;audit;recon;forensics;
EOF
cp "${SRC_DIR}/packaging/${APP_ID}.svg" "${ICON_DIR}/${APP_ID}.svg" 2>/dev/null || true
command -v gtk-update-icon-cache >/dev/null && gtk-update-icon-cache -q -t -f "${ICON_DIR%/scalable/apps}" 2>/dev/null || true
command -v update-desktop-database >/dev/null && update-desktop-database -q "${DESKTOP_DIR}" 2>/dev/null || true

# 6. Data directories — every directory the app needs, upfront (Meli lesson)
for sub in logs cache evidence workspaces plugins; do
    mkdir -p "${TARGET_HOME}/.local/share/${APP_NAME}/${sub}"
done
mkdir -p "${TARGET_HOME}/.config/${APP_NAME}"

# 7. systemd user unit — API server (off by default; user can enable)
mkdir -p "${SYSTEMD_USER_DIR}"
cat > "${SYSTEMD_USER_DIR}/godsapp-api.service" <<EOF
[Unit]
Description=GodsApp REST API
After=default.target

[Service]
Type=simple
ExecStart=${BIN_CLI} api start
Restart=on-failure
RestartSec=3
Environment=PYTHONPATH=${APP_DIR}
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF

# 8. Hand everything in the user's tree back to them (system install runs as root)
if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    chown -R "${SUDO_USER}:" \
        "${TARGET_HOME}/.local/share/${APP_NAME}" \
        "${TARGET_HOME}/.config/${APP_NAME}" \
        "${SYSTEMD_USER_DIR}/godsapp-api.service" 2>/dev/null || true
    # daemon-reload as the target user so they can `systemctl --user enable` next
    sudo -u "${SUDO_USER}" XDG_RUNTIME_DIR="/run/user/$(id -u "${SUDO_USER}")" \
        systemctl --user daemon-reload 2>/dev/null || true
else
    systemctl --user daemon-reload 2>/dev/null || true
fi

cat <<EOF

✔ GodsApp installed.

  Launch GUI:        ${BIN}
  CLI:               ${BIN_CLI} --help
  Enable REST API:   systemctl --user enable --now godsapp-api
                     (token at ~/.config/godsapp/api.token)
  Config:            ~/.config/godsapp/
  Data:              ~/.local/share/godsapp/
  Logs:              ~/.local/share/godsapp/logs/godsapp.log

EOF
