# OTP Grabber

A local sign-in code helper for this Plasma desktop. It watches **Melia** for
verification emails and **Google Messages** (`messages-kde`) for SMS codes,
copies the code to the clipboard, shows a Plasma notification, and can fill the
website field in **Wavebox** with no paste.

Nothing is sent to a network service. Codes live in memory for two minutes.

## What you get

- Melia inbox watcher (local SQLite, last two minutes, skips sent/spam/trash)
- SMS forwarding from Google Messages notifications
- Clipboard copy (`wl-copy` / Klipper) plus a Plasma popup
- Wavebox / Chromium extension that fills OTP inputs over native messaging

## Requirements

- KDE Plasma 6, Python 3
- Melia with mail synced locally (`~/.config/melia/melia.db`)
- `messages-kde` 1.0.1+ for SMS
- Wavebox (or Chrome) for the companion extension
- `wl-copy` and `notify-send` (already on this machine)

## Install

```bash
chmod +x install.sh uninstall.sh otp-grabber otp-grabber-native
./install.sh
```

That enables the user systemd service `otp-grabber.service`.

Then load the extension in Wavebox:

1. Open `wavebox://extensions` (Developer mode on)
2. **Load unpacked**
3. Choose `~/.local/share/otp-grabber/extension`

Reinstall Google Messages so SMS codes are forwarded:

```bash
cd ~/messages-kde
./install.sh
```

Restart the Google Messages app after that.

## Use

Keep the daemon running (it starts at login). When a site asks for a code:

1. The email or SMS arrives as usual.
2. A notification appears: `Sign-in code copied` with the digits.
3. Wavebox fills the OTP field if it can see one. Otherwise paste with Ctrl+V.

The extension popup shows whether the daemon, Melia watcher, and native host are up.

## Commands

```bash
otp-grabber status
otp-grabber peek --host accounts.google.com
otp-grabber ingest-text --source sms --text 'G-123456 is your Google verification code'
systemctl --user status otp-grabber.service
```

`peek` hides the digits unless you pass `--show-code`.

## Uninstall

```bash
./uninstall.sh
```

Then remove **OTP Grabber** from Wavebox’s extension page.

## Privacy

- Codes are not written to disk
- The Unix socket is mode `600` under `$XDG_RUNTIME_DIR`
- The extension talks only to the local native host, not to the open web
- Melia is read-only

## License

MIT. See [LICENSE](LICENSE).
