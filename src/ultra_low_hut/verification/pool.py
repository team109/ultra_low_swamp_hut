"""Host parallel vanilla query workers, each with isolated Minecraft state."""

import argparse
import concurrent.futures
import json
import os
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
import time
import uuid

from ultra_low_hut import ROOT
from ultra_low_hut.verification.loading_orders import APPROACHES, LOADING_POLICY, FEATURES_POLICY, ORDER_SPEC, aggregate_loading_orders, normalize_verification_mode
from ultra_low_hut.verification.service import start_single


def atomic(path, value):
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value))
    temporary.replace(path)


class QueryPool:
    def __init__(self, root, version, java, workers, exact=False, *, generation_mode="features", jar=None):
        self.root = Path(root)
        self.version, self.java, self.workers, self.exact = version, java, workers, exact
        self.generation_mode, self.jar = generation_mode, jar
        self.order_spec = ORDER_SPEC if generation_mode == "features" else None
        self.processes = []
        self.available = queue.Queue()
        self.stop = threading.Event()
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=workers)

    def start(self):
        for name in ("inbox", "outbox", "processed", "workers"):
            (self.root / name).mkdir(exist_ok=True)
        for index in range(self.workers):
            folder = self.root / "workers" / str(index)
            process, record = start_single(self.version, folder, self.java, self.exact,
                                          generation_mode=self.generation_mode, jar=self.jar)
            self.processes.append(process)
            self.available.put(folder)
        deadline = time.monotonic() + 180
        folders = [self.root / "workers" / str(i) for i in range(self.workers)]
        while not all((folder / "ready.json").exists() for folder in folders):
            self.check()
            if time.monotonic() > deadline:
                raise TimeoutError("Vanilla query workers did not become ready")
            self.stop.wait(.02)
        policy = self.order_spec["id"] if self.order_spec else LOADING_POLICY
        worker_ready = [json.loads((folder / "ready.json").read_text()) for folder in folders]
        for ready in worker_ready:
            if ready.get("loading_policy") != policy:
                raise RuntimeError("Rebuild the query service before starting the worker pool")
        atomic(self.root / "ready.json", dict(engine="vanilla-memory-generation", loading_policy=policy,
                                              generation_mode=self.generation_mode,
                                              orders=self.order_spec["orders"] if self.order_spec else list(APPROACHES),
                                              biomes=worker_ready[0].get("biomes"),
                                              workers=self.workers, pid=os.getpid()))

    def check(self):
        if self.stop.is_set():
            raise RuntimeError("Query pool stopped")
        if any(p.poll() is not None for p in self.processes):
            raise RuntimeError("Vanilla query worker exited; see workers/*/server.log")

    def query(self, request):
        folder = None
        while folder is None:
            self.check()
            try:
                folder = self.available.get(timeout=.1)
            except queue.Empty:
                pass
        try:
            name = uuid.uuid4().hex + ".json"
            atomic(folder / "inbox" / name, request)
            response = folder / "outbox" / name
            deadline = time.monotonic() + 180
            while not response.exists():
                self.check()
                if time.monotonic() > deadline:
                    raise TimeoutError("Vanilla query timed out: " + str(response))
                self.stop.wait(.02)
            result = json.loads(response.read_text())
            # The public response retains all evidence; avoid unbounded duplicate files.
            response.unlink()
            (folder / "processed" / name).unlink(missing_ok=True)
            if "error" in result:
                raise RuntimeError(result["error"])
            return result
        finally:
            self.available.put(folder)

    def submit(self, request):
        if "requests" in request:
            return dict(batch=[self.submit(r) for r in request["requests"]])
        started = time.monotonic()
        if request.get("loading_orders"):
            if request.get("reuse"):
                raise ValueError("Loading-order verification requires independent chunk states")
            if (normalize_verification_mode(request.get("verification_mode", "on")) != "on"
                    or normalize_verification_mode(request.get("loading_order_profile", "on")) != "on"):
                raise ValueError("Loading-order verification mode must be on")
            orders = self.order_spec["orders"] if self.order_spec else [dict(id=a) for a in APPROACHES]
            futures = {}
            for order in orders:
                branch = dict(request, approach=order["id"], reuse=False, loading_orders=False)
                if "offsets" in order:
                    branch["chunk_order"] = order["offsets"]
                futures[order["id"]] = self.executor.submit(self.query, branch)
            return dict(started=started, approaches=futures)
        else:
            if request.get("reuse") and self.workers != 1:
                raise ValueError("World reuse requires --workers 1")
            return dict(started=started, single=self.executor.submit(self.query, request))

    def resolve(self, submitted):
        if "batch" in submitted:
            return dict(responses=[self.resolve(r) for r in submitted["batch"]])
        if "approaches" in submitted:
            result = aggregate_loading_orders({a: f.result() for a, f in submitted["approaches"].items()})
            result["verification_mode"] = "on"
        else:
            result = submitted["single"].result()
        result["wall_seconds"] = time.monotonic() - submitted["started"]
        return result

    def process(self, request):
        return self.resolve(self.submit(request))

    def close(self):
        self.stop.set()
        (self.root / "ready.json").unlink(missing_ok=True)
        for process in self.processes:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
        for process in self.processes:
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        self.executor.shutdown(wait=True, cancel_futures=True)
        atomic(self.root / "stopped.json", dict(at=time.time(), workers=[dict(pid=p.pid, exit_code=p.returncode) for p in self.processes]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--java", required=True)
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--exact", action="store_true")
    parser.add_argument("--generation-mode", choices=("full", "features"), default="features")
    parser.add_argument("--jar", type=Path)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error("--workers must be positive")
    pool = QueryPool(args.output, args.version, args.java, args.workers, args.exact,
                     generation_mode=args.generation_mode, jar=args.jar)

    def interrupted(*_):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    try:
        pool.start()
        while True:
            pool.check()
            request = next(iter(sorted((args.output / "inbox").glob("*.json"))), None)
            if request is None:
                pool.stop.wait(.02)
                continue
            try:
                result = pool.process(json.loads(request.read_text()))
            except Exception as error:
                atomic(args.output / "outbox" / request.name, dict(error=repr(error)))
                raise
            atomic(args.output / "outbox" / request.name, result)
            request.replace(args.output / "processed" / request.name)
    except KeyboardInterrupt:
        pass
    finally:
        pool.close()


if __name__ == "__main__":
    main()
