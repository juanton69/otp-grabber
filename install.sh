#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ID="org.juanton.otp-grabber"
NATIVE_HOST="com.juanton.otpgrabber"
EXT_ID="imncmaklnbofomaclblofommoknldgge"
BIN_DIR="${HOME}/.local/bin"
DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
APP_DIR="${DATA_HOME}/otp-grabber"
UNIT_DIR="${CONFIG_HOME}/systemd/user"

mkdir -p "${BIN_DIR}" "${APP_DIR}" "${UNIT_DIR}"

echo "Installing OTP Grabber from ${ROOT}"
rsync -a --delete \
  --exclude '.git/' \
  --exclude '__pycache__/' \
  --exclude '*.pyc' \
  --exclude 'tests/' \
  "${ROOT}/otp_grabber/" "${APP_DIR}/otp_grabber/"
rsync -a --delete \
  --exclude '__pycache__/' \
  "${ROOT}/extension/" "${APP_DIR}/extension/"
install -m 0755 "${ROOT}/otp-grabber" "${APP_DIR}/otp-grabber"
install -m 0755 "${ROOT}/otp-grabber-native" "${APP_DIR}/otp-grabber-native"

cat > "${BIN_DIR}/otp-grabber" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${APP_DIR}\${PYTHONPATH:+:\${PYTHONPATH}}"
exec /usr/bin/python3 "${APP_DIR}/otp-grabber" "\$@"
EOF
cat > "${BIN_DIR}/otp-grabber-native" <<EOF
#!/usr/bin/env bash
export PYTHONPATH="${APP_DIR}\${PYTHONPATH:+:\${PYTHONPATH}}"
exec /usr/bin/python3 "${APP_DIR}/otp-grabber-native" "\$@"
EOF
chmod 0755 "${BIN_DIR}/otp-grabber" "${BIN_DIR}/otp-grabber-native"

if [[ -d "${HOME}/bin" ]]; then
  ln -sfn "${BIN_DIR}/otp-grabber" "${HOME}/bin/otp-grabber"
fi

HOST_JSON="$(mktemp)"
cat > "${HOST_JSON}" <<EOF
{
  "name": "${NATIVE_HOST}",
  "description": "OTP grabber native host",
  "path": "${BIN_DIR}/otp-grabber-native",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://${EXT_ID}/"
  ]
}
EOF

for nm_dir in \
  "${CONFIG_HOME}/wavebox/NativeMessagingHosts" \
  "${CONFIG_HOME}/google-chrome/NativeMessagingHosts" \
  "${CONFIG_HOME}/chromium/NativeMessagingHosts"
do
  mkdir -p "${nm_dir}"
  install -m 0644 "${HOST_JSON}" "${nm_dir}/${NATIVE_HOST}.json"
done
rm -f "${HOST_JSON}"

install -m 0644 "${ROOT}/systemd/otp-grabber.service" "${UNIT_DIR}/otp-grabber.service"

systemctl --user daemon-reload
systemctl --user enable --now otp-grabber.service

echo
echo "Installed OTP Grabber"
echo "  Daemon     : ${BIN_DIR}/otp-grabber"
echo "  Extension  : ${APP_DIR}/extension"
echo "  Service    : systemctl --user status otp-grabber.service"
echo
echo "Load the Wavebox companion once:"
echo "  1. Open Wavebox and go to wavebox://extensions  (or chrome://extensions)"
echo "  2. Enable Developer mode"
echo "  3. Load unpacked → ${APP_DIR}/extension"
echo
echo "Google Messages forwarding needs the updated messages-kde app."
echo "From ~/messages-kde run: ./install.sh   then restart Google Messages."
