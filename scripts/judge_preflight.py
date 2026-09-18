#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def main() -> int:
    run([sys.executable, "-m", "pytest", "-q"])
    dataset = Path("data/raw")
    if not dataset.exists():
        print("JUDGE PREFLIGHT BLOCKED: data/raw is missing. Unit tests passed; real-data evidence cannot be fabricated.")
        return 2
    run([sys.executable, "scripts/verify_dataset.py", str(dataset)])
    print("Core tests and dataset integrity checks passed. Run make research and make demo before submission.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
