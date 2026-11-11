"""Persistent single-GPU screening with cached layout probes and CPU/GPU overlap."""

import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ultra_low_hut import ROOT

from ultra_low_hut.search.gpu.batch import BatchCascade
from ultra_low_hut.search.progress import SearchProgress, write_progress_atomic


class ScreeningPipeline:
    def __init__(
        self,
        device,
        version,
        room_budget,
        noise_library,
        cpu_library,
        batch=256,
        config=None,
        specs=None,
        terrain_sampler=None,
        world_type="normal",
        biome=None,
    ):
        self.cpu_library = cpu_library
        from ultra_low_hut.search.reference.native import Context
        from ultra_low_hut.layouts.geometry import room_geometry
        from ultra_low_hut.search.reference.diagnostics import (
            evaluate_excavation_bound,
            check_room_boundary_fluids,
            calculate_excavation_gains,
        )

        self.Context = Context
        self.room_geometry = room_geometry
        self.evaluate_excavation_bound = evaluate_excavation_bound
        self.check_room_boundary_fluids = check_room_boundary_fluids
        self.calculate_excavation_gains = calculate_excavation_gains
        if config is None:
            from ultra_low_hut.versions import resolve_hunt

            config = resolve_hunt(version, -62, True)
        from ultra_low_hut.world_types import world_config

        self.world = world_config(world_type, biome)
        self.config = dict(config, room_budget=room_budget, **self.world)
        self.device, self.batch = device, batch
        self.terrain_sampler = terrain_sampler
        if specs is None:
            root = ROOT
            specs = {
                v["name"].split(":")[1]: v
                for v in json.loads(
                    (root / "data/noises/seed-specs26.json").read_text()
                )["noises"]
            }
        self.cascade = BatchCascade(device, specs, noise_library, world_type)
        self.executor = ThreadPoolExecutor(max_workers=1)

    def close(self):
        self.executor.shutdown(wait=True)
        self.cascade.close()
        if self.terrain_sampler is not None:
            self.terrain_sampler.close()

    def screen(self, rows):
        cascade, executor = self.cascade, self.executor
        Context, config, batch = self.Context, self.config, self.batch
        devices, slot = [self.device], 0
        room_geometry = self.room_geometry
        evaluate_excavation_bound = self.evaluate_excavation_bound
        check_room_boundary_fluids = self.check_room_boundary_fluids
        calculate_excavation_gains = self.calculate_excavation_gains

        def screen_group(group):
            t = time.perf_counter()
            result = cascade.batch(
                [(root, root["hutCandidates"][0]) for _, root in group]
            )
            return result, time.perf_counter() - t

        future = executor.submit(screen_group, rows[:batch]) if rows else None
        for begin in range(0, len(rows), batch):
            group = rows[begin : begin + batch]
            assert all(len(root["hutCandidates"]) == 1 for _, root in group)
            screened, gpu_seconds = future.result()
            gpu_seconds /= len(group)
            following = rows[begin + batch : begin + 2 * batch]
            if following:
                future = executor.submit(screen_group, following)
            for (index, root), (screen, found) in zip(group, screened):
                sampler = self.terrain_sampler
                sample_root = sampler is not None and sampler.start_root()
                natural_samples = []
                refined = []
                low = []
                ref_seconds = 0.0
                room_rejected = 0
                room_stages = {}
                geometry = None
                for candidate in found:
                    t = time.perf_counter()
                    with Context(
                        int(candidate["seed"]), config["requested_version"], -1,
                        cpu_library=self.cpu_library, **self.world,
                    ) as ctx:
                        if sample_root:
                            sample = sampler.observe(ctx, candidate)
                            if sample is not None:
                                sample.update(self.world)
                                natural_samples.append(sample)
                        gate = None
                        if config.get("room_budget") is not None:
                            if geometry is None:
                                geometry = room_geometry(
                                    int(root["template"]["target"]),
                                    candidate["x"],
                                    candidate["z"],
                                    width=root["template"]["width"],
                                    relx=root["template"]["relx"],
                                    relz=root["template"]["relz"],
                                )
                            gate = ctx.room_budget(
                                candidate["x"],
                                candidate["z"],
                                geometry,
                                config["room_budget"],
                            )
                            room_stages[str(gate["stage"])] = (
                                room_stages.get(str(gate["stage"]), 0) + 1
                            )
                            if not gate["passed"]:
                                room_rejected += 1
                                ref_seconds += time.perf_counter() - t
                                continue
                        ref = ctx.hut(
                            candidate["x"],
                            candidate["z"],
                            config["screen"]["reference_max_y"],
                        )
                        depth_bound = (
                            evaluate_excavation_bound(
                                ctx, candidate["x"], candidate["z"], geometry, -58
                            )
                            if geometry is not None
                            else None
                        )
                        if depth_bound and not depth_bound["passed"]:
                            depth_bound.pop("columns")
                        liquid_check = (
                            check_room_boundary_fluids(
                                ctx, candidate["x"], candidate["z"], geometry
                            )
                            if geometry is not None
                            and (
                                ref["accepted"]
                                or (depth_bound and depth_bound["passed"])
                            )
                            else None
                        )
                        if geometry is not None:
                            candidate = {
                                **candidate,
                                "geometry": {
                                    **candidate["geometry"],
                                    **calculate_excavation_gains(geometry),
                                },
                            }
                    ref_seconds += time.perf_counter() - t
                    result = {
                        **candidate,
                        **self.world,
                        "reference": ref,
                        "template": root["template"],
                        "room_gate": gate,
                        "depth_bound": depth_bound,
                        "room_liquid_check": liquid_check,
                    }
                    refined.append(result)
                    if (
                        ref["accepted"]
                        and ref["y"] <= config["screen"]["reference_max_y"]
                    ):
                        low.append(result)
                report = dict(
                    index=index,
                    device=devices[slot],
                    root=root,
                    screens=[screen],
                    refined=refined,
                    noise_candidates=len(found),
                    room_rejected=room_rejected,
                    room_gate_stages=room_stages,
                    shortlisted=len(low),
                    reference_min_y=min(
                        (r["reference"]["y"] for r in refined), default=None
                    ),
                    seconds=gpu_seconds + ref_seconds,
                    gpu_and_transfer_seconds=gpu_seconds,
                    reference_seconds=ref_seconds,
                )
                if natural_samples:
                    report["natural_samples"] = natural_samples
                yield report, low

    def run_job(self, geometry_path, output, skip_path=None):
        output = Path(output)
        output.mkdir(exist_ok=False)
        sampler = getattr(self, "terrain_sampler", None)
        if sampler is not None:
            sampler.register_job(output)
        skip = set(json.loads(Path(skip_path).read_text())) if skip_path else set()
        rows = [
            (i, row)
            for i, row in enumerate(json.loads(Path(geometry_path).read_text()))
            if i not in skip
        ]
        metrics = SearchProgress()
        last_progress = 0.0
        errors = []
        finished = False
        try:
            with (output / "completed.jsonl").open("w") as completed, (
                output / "shortlist.jsonl"
            ).open("w") as shortlist, (output / "conditioned-noise.jsonl").open(
                "w"
            ) as conditioned:
                for report, low in self.screen(rows):
                    metrics.add(report, low)
                    count = metrics.values["layouts"]
                    accounting = dict(
                        completed_roots=count,
                        seed_position_trials=count * 65536,
                        emitted_at=time.time(),
                        elapsed_seconds=time.perf_counter() - metrics.started_clock,
                    )
                    report["accounting"] = accounting
                    for candidate in report["refined"]:
                        if (
                            candidate.get("depth_bound")
                            and candidate["depth_bound"]["passed"]
                        ):
                            conditioned.write(json.dumps(candidate) + "\n")
                            conditioned.flush()
                    for candidate in low:
                        candidate["discovery"] = dict(
                            accounting, root_index=report["index"], source=str(output)
                        )
                        shortlist.write(json.dumps(candidate) + "\n")
                    if low:
                        shortlist.flush()
                    completed.write(
                        json.dumps(
                            report
                            if report["refined"] or report.get("natural_samples")
                            else dict(index=report["index"])
                        )
                        + "\n"
                    )
                    completed.flush()
                    if sampler is not None:
                        sampler.commit(report.get("natural_samples", []))
                    if (
                        time.monotonic() - last_progress >= 1
                        or count % 1000 == 0
                        or low
                    ):
                        write_progress_atomic(
                            output / "live-progress.json",
                            metrics.snapshot("running", errors),
                        )
                        last_progress = time.monotonic()
            finished = True
        except Exception as error:
            errors.append(dict(device=self.device, error=repr(error)))
            raise
        finally:
            status = "completed" if finished else "failed" if errors else "interrupted"
            report = metrics.snapshot(status, errors)
            write_progress_atomic(output / "live-progress.json", report)
            write_progress_atomic(output / "summary.json", report)
        return report
