from __future__ import annotations

import argparse
import json
import sys

from otp_grabber import __version__
from otp_grabber.client import request
from otp_grabber.daemon import run_daemon
from otp_grabber.native_host import main as native_main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="otp-grabber", description="Grab email/SMS sign-in codes")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("daemon", help="run the background grabber (default)")
    sub.add_parser("native-host", help="Chrome/Wavebox native messaging host")
    sub.add_parser("status", help="show daemon status without printing codes")
    peek = sub.add_parser("peek", help="fetch the current code for a site")
    peek.add_argument("--host", default="")
    peek.add_argument("--show-code", action="store_true")
    consume = sub.add_parser("consume", help="fetch and consume the current code")
    consume.add_argument("--host", default="")
    consume.add_argument("--show-code", action="store_true")
    ingest = sub.add_parser("ingest-text", help="feed a message to the running daemon")
    ingest.add_argument("--source", choices=("sms", "email"), default="sms")
    ingest.add_argument("--title", default="")
    ingest.add_argument("--text", required=True)

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])
    cmd = args.cmd or "daemon"
    if cmd == "daemon":
        return run_daemon()
    if cmd == "native-host":
        return native_main()
    if cmd == "status":
        reply = request({"op": "status"})
        if reply is None:
            print("daemon is not running", file=sys.stderr)
            return 1
        print(json.dumps(reply, indent=2))
        return 0
    if cmd in {"peek", "consume"}:
        reply = request({"op": cmd, "host": args.host or None})
        if reply is None:
            print("daemon is not running", file=sys.stderr)
            return 1
        if not args.show_code:
            reply = {k: v for k, v in reply.items() if k != "code"} | {
                "has_code": bool(reply.get("code")),
                "len": len(reply.get("code") or ""),
            }
        print(json.dumps(reply, indent=2))
        return 0 if reply.get("code") or reply.get("has_code") else 2
    if cmd == "ingest-text":
        reply = request(
            {
                "op": "ingest_text",
                "source": args.source,
                "title": args.title,
                "text": args.text,
            }
        )
        if reply is None:
            print("daemon is not running", file=sys.stderr)
            return 1
        print(json.dumps({k: v for k, v in reply.items() if k != "code"} | {"has_code": bool(reply.get("code"))}, indent=2))
        return 0 if reply.get("ok") else 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
