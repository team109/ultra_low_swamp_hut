"""Submit one JSON request or a batch to a running terrain service."""

import argparse
import json
from pathlib import Path
import time
import uuid


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--service", type=Path, required=True)
    p.add_argument("--request", type=Path, required=True)
    p.add_argument("--timeout", type=float, default=300)
    a = p.parse_args()
    payload = json.loads(a.request.read_text())
    deadline = time.monotonic() + a.timeout
    ready = a.service / "ready.json"
    while not ready.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(str(ready))
        time.sleep(0.02)
    name = uuid.uuid4().hex + ".json"
    inbox = a.service / "inbox"
    tmp = inbox / (name + ".tmp")
    tmp.write_text(json.dumps(payload))
    tmp.replace(inbox / name)
    response = a.service / "outbox" / name
    while not response.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(str(response))
        time.sleep(0.02)
    print(json.dumps(json.loads(response.read_text()), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
