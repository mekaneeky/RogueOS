from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    vendor_dir = repo_root / "rogueos_web" / "static" / "vendor"
    vendor_dir.mkdir(parents=True, exist_ok=True)

    print("Syncing Three.js assets via npm…")
    try:
        subprocess.run(
            ["npm", "run", "sync-three"],
            cwd=repo_root,
            check=True,
        )
    except FileNotFoundError:
        print("npm is required but not installed or not found in PATH.")
        print("Install Node.js, run `npm install`, then `npm run sync-three`.")
        return 1
    except subprocess.CalledProcessError as err:  # pragma: no cover - delegation
        print("npm failed; ensure dependencies are installed (`npm install`).")
        print(f"Command: {' '.join(err.cmd)}")
        print(f"Exit status: {err.returncode}")
        return err.returncode

    print(f"Assets synced into {vendor_dir}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
