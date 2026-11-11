"""Command entry for ultra_low_hut.layouts.prepare_yield."""

from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    sys.path[0] = str(Path(__file__).resolve().parents[2] / "src")
    runpy.run_module("ultra_low_hut.layouts.prepare_yield", run_name="__main__")
