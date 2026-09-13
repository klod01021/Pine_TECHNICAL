"""Launch the option pricer in a local web browser."""

from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser

from option_pricer.bootstrap import reexec_if_needed


def main(argv: list[str] | None = None) -> None:
    raw = list(sys.argv[1:] if argv is None else argv)
    bootstrap = "--no-bootstrap" not in raw
    raw = [arg for arg in raw if arg != "--no-bootstrap"]
    if bootstrap:
        reexec_if_needed(raw)

    import uvicorn

    parser = argparse.ArgumentParser(description="Launch the web option pricer")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open a browser window",
    )
    args = parser.parse_args(raw)
    url = (
        f"http://127.0.0.1:{args.port}"
        if args.host in {"0.0.0.0", "::"}
        else f"http://{args.host}:{args.port}"
    )

    if not args.no_browser:
        def _open():
            time.sleep(0.6)
            webbrowser.open(url)

        threading.Thread(target=_open, daemon=True).start()

    print(f"Option pricer running at {url}")
    print("Press Ctrl+C in this window to stop.")
    uvicorn.run(
        "option_pricer.app:app",
        host=args.host,
        port=args.port,
        log_level="info",
        workers=1,
    )


if __name__ == "__main__":
    main()
