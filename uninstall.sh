#!/usr/bin/env bash
set -euo pipefail

NATIVE_HOST="com.juanton.otpgrabber"
BIN_DIR="${HOME}/.local/bin"
DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"

systemctl --user disable --now otp-grabber.service 2>/dev/null || true
rm -f "${CONFIG_HOME}/systemd/user/otp-grabber.service"
systemctl --user daemon-reload 2>/dev/null || true

rm -f "${BIN_DIR}/otp-grabber" "${BIN_DIR}/otp-grabber-native" "${HOME}/bin/otp-grabber"
rm -rf "${DATA_HOME}/otp-grabber"

for nm_dir in \
  "${CONFIG_HOME}/wavebox/NativeMessagingHosts" \
  "${CONFIG_HOME}/google-chrome/NativeMessagingHosts" \
  "${CONFIG_HOME}/chromium/NativeMessagingHosts"
do
  rm -f "${nm_dir}/${NATIVE_HOST}.json"
done

SOCK="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}/otp-grabber.sock"
rm -f "${SOCK}"

echo "OTP Grabber has been uninstalled."
echo "Remove the Wavebox extension from wavebox://extensions if it is still listed."
