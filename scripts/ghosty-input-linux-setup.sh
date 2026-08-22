#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This helper is for Linux only." >&2
  exit 1
fi

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this helper as your normal desktop user. It requests sudo only for system setup." >&2
  exit 1
fi

GROUP_NAME="ghosty-input"
RULE_FILE="/etc/udev/rules.d/70-ghosty-input-uinput.rules"
MODULE_FILE="/etc/modules-load.d/ghosty-input-uinput.conf"
CURRENT_USER="${USER:-$(id -un)}"
ACTION="${1:-install}"

show_status() {
  echo "Ghosty Input Linux input status"
  echo "User: ${CURRENT_USER}"
  echo "Session: ${XDG_SESSION_TYPE:-unknown}"
  echo "uinput device: $( [[ -e /dev/uinput ]] && echo present || echo missing )"
  echo "uinput writable: $( [[ -w /dev/uinput ]] && echo yes || echo no )"
  echo "group exists: $( getent group "${GROUP_NAME}" >/dev/null 2>&1 && echo yes || echo no )"
  echo "user in group: $( id -nG "${CURRENT_USER}" | tr ' ' '\n' | grep -qx "${GROUP_NAME}" && echo yes || echo no )"
  echo "udev rule: $( [[ -f "${RULE_FILE}" ]] && echo installed || echo missing )"
  echo "module boot config: $( [[ -f "${MODULE_FILE}" ]] && echo installed || echo missing )"
}

install_uinput() {
  echo "Ghosty Input Linux setup"
  echo "User: ${CURRENT_USER}"
  echo "Enabling only /dev/uinput access for members of ${GROUP_NAME}."

  sudo modprobe uinput
  sudo groupadd --force "${GROUP_NAME}"
  sudo usermod -aG "${GROUP_NAME}" "${CURRENT_USER}"

  local tmp_rule tmp_module
  tmp_rule="$(mktemp)"
  tmp_module="$(mktemp)"
  trap 'rm -f "${tmp_rule:-}" "${tmp_module:-}"' EXIT

  cat > "${tmp_rule}" <<EOF
KERNEL=="uinput", GROUP="${GROUP_NAME}", MODE="0660", OPTIONS+="static_node=uinput"
EOF
  printf 'uinput\n' > "${tmp_module}"

  sudo install -m 0644 "${tmp_rule}" "${RULE_FILE}"
  sudo install -m 0644 "${tmp_module}" "${MODULE_FILE}"
  sudo udevadm control --reload-rules
  sudo udevadm trigger --subsystem-match=misc --action=add || true

  echo
  show_status
  cat <<EOF

Setup completed.

IMPORTANT:
  1. Sign out and back in (or reboot) so the new group membership applies.
  2. Do NOT run Ghosty Input as root.
  3. Then run:
       ./GhostyInput --diagnose
     It should report: uinput: ready
EOF
}

remove_uinput() {
  echo "Removing Ghosty Input uinput system configuration."
  sudo rm -f "${RULE_FILE}" "${MODULE_FILE}"
  if getent group "${GROUP_NAME}" >/dev/null 2>&1; then
    sudo gpasswd -d "${CURRENT_USER}" "${GROUP_NAME}" >/dev/null 2>&1 || true
  fi
  sudo udevadm control --reload-rules
  echo "Removed. Sign out and back in to refresh group membership."
}

case "${ACTION}" in
  install)
    install_uinput
    ;;
  status)
    show_status
    ;;
  remove|uninstall)
    remove_uinput
    ;;
  *)
    echo "Usage: $0 [install|status|remove]" >&2
    exit 2
    ;;
esac
