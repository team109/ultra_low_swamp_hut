"""Select one mineshaft template for a hut search."""

import argparse
import json
from pathlib import Path
import sys

from ultra_low_hut import ROOT
from ultra_low_hut.layouts.catalog import LAYOUT_CATALOG


def select(catalog, seed):
    text = catalog.read_text()
    rows = (
        json.loads(text)
        if text.lstrip().startswith("[")
        else [json.loads(line) for line in text.splitlines() if line.strip()]
    )
    matches = [row for row in rows if int(row["target"]) == seed]
    if len(matches) != 1:
        raise ValueError(
            f"Expected one template for layout seed {seed}; found {len(matches)}"
        )
    return matches[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument(
        "--catalog", type=Path, default=LAYOUT_CATALOG
    )
    parser.add_argument("--output", type=Path, required=True)
    options = parser.parse_args()
    try:
        template = select(options.catalog, options.seed)
    except (OSError, ValueError, KeyError) as error:
        parser.error(str(error))
    options.output.parent.mkdir(parents=True, exist_ok=True)
    options.output.write_text(json.dumps(template, indent=2) + "\n")
    print(json.dumps(dict(layout_seed=str(options.seed), output=str(options.output))))


if __name__ == "__main__":
    main()
