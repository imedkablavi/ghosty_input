#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This helper is for Linux only." >&2
  exit 1
fi

if [[ "${EUID}" -eq 0 ]]; then
  echo "Run this helper as your normal desktop user. It will request sudo only for system setup." >&2
  exit 1
fi

GROUP_NAME="ghosty-input"
RULE_FILE="/etc/udev/rules.d/70-ghosty-input-uinput.rules"
CURRENT_USER="${USER:-$(id -un)}"

echo "Ghosty Input Linux setup"
echo "User: ${CURRENT_USER}"
echo "This enables access only to /dev/uinput for members of ${GROUP_NAME}."

sudo modprobe uinput
sudo groupadd --force "${GROUP_NAME}"
sudo usermod -aG "${GROUP_NAME}" "${CURRENT_USER}"

TMP_RULE="$(mktemp)"
trap 'rm -f "${TMP_RULE}"' EXIT
cat > "${TMP_RULE}" <<EOF
KERNEL=="uinput", GROUP="${GROUP_NAME}", MODE="0660", OPTIONS+="static_node=uinput"
EOF
sudo install -m 0644 "${TMP_RULE}" "${RULE_FILE}"
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=misc --action=add || true

if [[ ! -e /dev/uinput ]]; then
  echo "Warning: /dev/uinput is still missing. Reboot once, then run GhostyInput --diagnose." >&2
fi

cat <<EOF

Setup completed.

IMPORTANT:
  1. Sign out of your desktop session and sign back in (or reboot) so the new group membership applies.
  2. Do NOT run Ghosty Input as root.
  3. After signing back in, run:
       ./GhostyInput --diagnose
     It should report: uinput: ready
  4. Then start:
       ./run-ghosty.sh
EOF
