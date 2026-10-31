# OTP Grabber

A local sign-in code helper for this desktop. It watches **Betterbird** for
verification emails and **Google Messages** (`messages-gnome`) for SMS codes,
copies the code to the clipboard, shows a notification, and can fill the
website field in **Wavebox** with no paste.

Nothing is sent to a network service. Codes live in memory for two minutes.

## What you get

- Betterbird INBOX watcher (local mbox files, last two minutes, skips sent/spam/trash)
- SMS forwarding from Google Messages notifications
- Clipboard copy (`wl-copy` / Klipper) plus a desktop notification
- Wavebox / Chromium extension that fills OTP inputs over native messaging

## Requirements

- Python 3
- Betterbird with mail stored locally (Flatpak `eu.betterbird.Betterbird` or a native profile)
- [Google Messages for GNOME](https://github.com/juanton69/messages-gnome) for SMS
- Wavebox (or Chrome) for the companion extension
- `wl-copy` and `notify-send`

## Install

```bash
git clone https://github.com/juanton69/otp-grabber.git
cd otp-grabber
chmod +x install.sh uninstall.sh otp-grabber otp-grabber-native
./install.sh
```

That enables the user systemd service `otp-grabber.service`.

Then load the extension in Wavebox:

1. Open `wavebox://extensions` (Developer mode on)
2. **Load unpacked**
3. Choose `~/.local/share/otp-grabber/extension`

Install [Google Messages for GNOME](https://github.com/juanton69/messages-gnome) so SMS codes are forwarded:

```bash
git clone https://github.com/juanton69/messages-gnome.git
cd messages-gnome
./install.sh
```

Then log out and back in so GNOME Shell loads the extension. Incoming Messages
notifications are forwarded to `$XDG_RUNTIME_DIR/otp-grabber.sock`.

## Use

Keep the daemon running (it starts at login). When a site asks for a code:

1. The email or SMS arrives as usual.
2. A notification appears: `Sign-in code copied` with the digits.
3. Wavebox fills the OTP field if it can see one. Otherwise paste with Ctrl+V.

The extension popup shows whether the daemon, Betterbird watcher, and native host are up.

## Commands

```bash
otp-grabber status
otp-grabber peek --host accounts.google.com
otp-grabber ingest-text --source sms --text 'G-123456 is your Google verification code'
systemctl --user status otp-grabber.service
```

`peek` hides the digits unless you pass `--show-code`.

Override the Betterbird profile with `OTP_GRABBER_BETTERBIRD_PROFILE` if it is not
the Flatpak default (`~/.var/app/eu.betterbird.Betterbird/config/thunderbird`).

## Uninstall

```bash
./uninstall.sh
```

Then remove **OTP Grabber** from Wavebox’s extension page.

## Privacy

- Codes are not written to disk
- The Unix socket is mode `600` under `$XDG_RUNTIME_DIR`
- The extension talks only to the local native host, not to the open web
- Betterbird mailboxes are read-only

## License

MIT. See [LICENSE](LICENSE).
