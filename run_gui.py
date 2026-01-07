from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path
import os

from rogueos_web.server import create_server, shutdown_server


def main():
    parser = argparse.ArgumentParser(description="Run the RogueOS Three.js viewer in a desktop window")
    parser.add_argument("root", type=Path, help="Directory to explore")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface for the embedded server (default: 127.0.0.1)")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port for the embedded server (default: 0 meaning choose a free port)",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Window width in pixels (default: 1280)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=800,
        help="Window height in pixels (default: 800)",
    )
    args = parser.parse_args()

    root = args.root.expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise SystemExit("Root must be an existing directory.")

    os.environ.setdefault("QT_API", "pyside6")
    try:
        import webview  # type: ignore
    except ImportError as exc:
        raise SystemExit(
            "pywebview is required for the desktop GUI. Install it with 'pip install pywebview'."
        ) from exc

    httpd, state = create_server(root, host=args.host, port=args.port)
    actual_host, actual_port = httpd.server_address
    url_host = "127.0.0.1" if actual_host in ("0.0.0.0", "::") else actual_host

    vendor_dir = Path(__file__).resolve().parent / "rogueos_web" / "static" / "vendor"
    required_vendor = [
        "three.min.js",
        "OrbitControls.js",
        "EffectComposer.js",
        "RenderPass.js",
        "UnrealBloomPass.js",
        "FilmPass.js",
        "ShaderPass.js",
        "FXAAShader.js",
        "LuminosityShader.js",
        "ColorCorrectionShader.js",
    ]
    missing_vendor = [name for name in required_vendor if not (vendor_dir / name).exists()]
    if missing_vendor:
        print("The following web assets are missing:")
        for name in missing_vendor:
            print(f"  - {name}")
        print("Run 'python3 scripts/fetch_web_assets.py' to download them before starting the GUI.")

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True, name="RogueOS-WebServer")
    server_thread.start()

    window_title = f"RogueOS Astral Navigator — {root}"
    window = webview.create_window(
        window_title,
        f"http://{url_host}:{actual_port}/",
        width=args.width,
        height=args.height,
        resizable=True,
    )

    closed_once = threading.Event()

    def _shutdown():
        if closed_once.is_set():
            return
        closed_once.set()
        shutdown_server(httpd, state)
        server_thread.join(timeout=2)

    window.events.closed += _shutdown

    try:
        webview.start(gui="qt")
    finally:
        _shutdown()


if __name__ == "__main__":
    sys.exit(main())
