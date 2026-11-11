"""Command entry for ultra_low_hut.verification.service."""

from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    sys.path[0] = str(Path(__file__).resolve().parents[1] / "src")
    runpy.run_module("ultra_low_hut.verification.service", run_name="__main__")
