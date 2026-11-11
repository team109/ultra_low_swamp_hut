"""Catalog loading and persistent vanilla layout-placement transport."""

import json
import subprocess
import threading


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def read_layouts(path):
    text = path.read_text()
    rows = (
        json.loads(text)
        if text.lstrip().startswith("[")
        else [json.loads(line) for line in text.splitlines() if line.strip()]
    )
    layouts = {}
    for row in rows:
        target = str(row["target"])
        origin = row.get("geometry_origin", row.get("prior_origin"))
        if origin is None:
            raise ValueError(f"Layout {target} needs geometry_origin")

        def precision(anchor):
            magnitude = anchor if anchor >= 0 else -anchor - 1
            if magnitude < 2**23:
                return 0
            if magnitude < 2**24:
                return 1
            return 2

        region = 3 * precision(origin[0]) + precision(origin[1])
        layout = dict(row, target=target, test_origin=origin, test_region=region)
        if target in layouts and layouts[target] != layout:
            raise ValueError(f"Conflicting duplicate layout {target}")
        layouts[target] = layout
    return list(layouts.values())


class PlacementWorker:
    """One persistent vanilla placement process, owned by one executor thread."""

    def __init__(self, configuration, panel, java, directory):
        self.log = (directory / f"worker-{threading.get_ident()}.log").open("a")
        command = [
            java,
            "-XX:ActiveProcessorCount=1",
            "-Xmx2G",
            "-javaagent:" + configuration["agent"],
            "-cp",
            configuration["classpath"],
            "LayoutYieldService",
            str(panel),
        ]
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=self.log,
            text=True,
            bufsize=1,
            cwd=directory,
        )
        try:
            if not self.receive().get("ready"):
                raise RuntimeError("Vanilla placement worker did not become ready")
        except BaseException:
            self.close()
            raise

    def receive(self):
        for line in self.process.stdout:
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue  # Minecraft startup logging shares stdout.
            if isinstance(value, dict) and (value.get("ready") or "target" in value):
                return value
        raise RuntimeError(f"Placement worker exited with {self.process.poll()}")

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:
                self.process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                self.process.wait(timeout=20)
        self.process.stdout.close()
        self.log.close()
