#!/usr/bin/env bash
# Remove GodsApp installed by install.sh. User data is preserved by default.
set -euo pipefail

USER_INSTALL=0
PURGE=0
for arg in "$@"; do
    case "$arg" in
        --user)  USER_INSTALL=1 ;;
        --purge) PURGE=1 ;;
    esac
done

APP_NAME="godsapp"
APP_ID="com.sierengowski.GodsApp"

if [[ $USER_INSTALL -eq 0 ]]; then
    [[ $EUID -eq 0 ]] || { echo "system uninstall needs sudo"; exit 1; }
    PREFIX="/opt/${APP_NAME}"
    BIN="/usr/local/bin/${APP_NAME}"
    BIN_CLI="/usr/local/bin/${APP_NAME}-cli"
    DESKTOP_DIR="/usr/share/applications"
    ICON_DIR="/usr/share/icons/hicolor/scalable/apps"
else
    PREFIX="${HOME}/.local/opt/${APP_NAME}"
    BIN="${HOME}/.local/bin/${APP_NAME}"
    BIN_CLI="${HOME}/.local/bin/${APP_NAME}-cli"
    DESKTOP_DIR="${HOME}/.local/share/applications"
    ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"
fi

systemctl --user disable --now godsapp-api 2>/dev/null || true
rm -f "${BIN}" "${BIN_CLI}"
rm -f "${DESKTOP_DIR}/${APP_ID}.desktop"
rm -f "${ICON_DIR}/${APP_ID}.svg"
rm -rf "${PREFIX}"

if [[ $PURGE -eq 1 ]]; then
    USER_HOME="${HOME:-$(getent passwd "${SUDO_USER:-$USER}" | cut -d: -f6)}"
    rm -rf "${USER_HOME}/.config/${APP_NAME}" "${USER_HOME}/.local/share/${APP_NAME}"
    echo "user data purged."
fi

echo "GodsApp removed."
