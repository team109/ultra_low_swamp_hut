import json
from pathlib import Path
import signal
import sys
from types import SimpleNamespace

import unittest
import tempfile
from unittest.mock import patch
from contextlib import ExitStack

from ultra_low_hut.search import run as search_huts, campaign as search_layout_pool


def candidate(height=-60):
    return dict(seed="123", x=16, z=32, reference=dict(accepted=True, y=height),
                discovery={}, geometry=dict(width=7))


def check_native_record_keeps_native_estimate_without_vanilla_fields():
    source = dict(candidate(), HPos=-61, verified_at=1, versions=["1.21"],
                  responses={}, loading_policy="old")
    row = search_huts.native_record(source, dict(version="1.21"), 65536)
    assert row["native_y"] == -60
    assert row["reference"] == source["reference"]
    assert row["verification_mode"] == "off"
    assert not {"HPos", "verified_at", "versions", "responses", "loading_policy"} & row.keys()
    assert source["HPos"] == -61


def check_modes_resume_and_forbid_switching_populated_runs(tmp_path):
    assert search_huts.verification_mode(tmp_path) == "on"
    assert search_huts.verification_mode(tmp_path, {}) == "on"
    assert search_huts.verification_mode(tmp_path, dict(verification_mode="off")) == "off"
    assert search_huts.verification_mode(tmp_path, {}, "off") == "off"
    with unittest.TestCase().assertRaisesRegex(ValueError, "on or off"):
        search_huts.verification_mode(tmp_path, {}, "unsupported")
    (tmp_path / "shortlist.jsonl").write_text('{"seed":"1"}\n')
    assert search_huts.verification_mode(tmp_path, dict(verification_mode="full"), "on") == "on"
    assert search_huts.verification_mode(tmp_path, dict(verification_mode="none"), "off") == "off"
    with unittest.TestCase().assertRaisesRegex(ValueError, "different verification mode"):
        search_huts.verification_mode(tmp_path, dict(verification_mode="off"), "on")


def check_off_search_runs_native_worker_without_java_or_eula(tmp_path, monkeypatch, world_type="normal", biome=None):
    config = dict(version="1.21", verification_mode="off", devices=[0], started_at=1,
                  record_height=-55, target_height=-59, qualified_search=dict(template={}))
    config["world_type"] = world_type
    if biome is not None:
        config["biome"] = biome
    (tmp_path / "config.json").write_text(json.dumps(config))
    monkeypatch.setattr(sys, "argv", ["search_huts", "--root", str(tmp_path), "--resume"])
    monkeypatch.setattr(search_huts, "require_natural_template", lambda *_: None)
    monkeypatch.setattr(search_huts, "require_layout_version", lambda *_: None)
    monkeypatch.setattr(search_huts, "resume_worker", lambda path, *_: path.mkdir(exist_ok=True))
    def forbidden(*args, **kwargs):
        raise AssertionError("off mode attempted vanilla setup or result logging")
    for name in ("VerificationGroup", "start", "get_order_spec", "SearchLog"):
        monkeypatch.setattr(search_huts, name, forbidden)
    monkeypatch.setattr(search_huts, "SearchMetrics", lambda *_: SimpleNamespace(snapshot=lambda *_: {}))
    monkeypatch.setattr(search_huts.time, "sleep", lambda *_: None)
    class Worker:
        pid = 123
        stopped = False
        def poll(self):
            return 0 if self.stopped else None
    worker = Worker()
    def launch(command, **kwargs):
        assert command[1].endswith("scripts/search/worker.py")
        output = tmp_path / "gpu0/search000000"
        output.mkdir()
        (output / "shortlist.jsonl").write_text(json.dumps(candidate()) + "\n")
        return worker
    monkeypatch.setattr(search_huts.subprocess, "Popen", launch)
    monkeypatch.setattr(search_huts, "terminate", lambda process: setattr(process, "stopped", True))
    old_handler = signal.getsignal(signal.SIGTERM)
    try:
        search_huts.main()
    finally:
        signal.signal(signal.SIGTERM, old_handler)
    row = json.loads((tmp_path / "low-huts.jsonl").read_text())
    assert row["native_y"] == -60 and "HPos" not in row
    assert row["world_type"] == world_type
    if biome is not None:
        assert row["biome"] == biome
    assert (tmp_path / "NATIVE_TARGET_REACHED.json").exists()
    assert json.loads((tmp_path / "STOPPED.json").read_text())["reason"] == "native-target-height"
    assert not any((tmp_path / name).exists() for name in ("verified-huts.jsonl", "results.jsonl", "validation.jsonl", "TARGET_REACHED.json"))
    assert not list(tmp_path.glob("verifier-*"))




def check_native_campaign_collect_and_recovery_never_publish_verified_huts(tmp_path):
    phase = dict(index=0, directory="phase", identity=[1], status="running", seed_position_trials=0)
    run = tmp_path / "phase/run"
    run.mkdir(parents=True)
    config = dict(version="1.21", verification_mode="off", record_height=-55, target_height=-59)
    row = search_huts.native_record(candidate(), config, 65536)
    (run / "shortlist.jsonl").write_text(json.dumps(row) + "\n")
    (run / "progress.json").write_text(json.dumps(dict(seed_position_trials=65536)))
    state = dict(status="running", phases=[phase])
    seen, first = set(), {}
    assert search_layout_pool.collect(tmp_path, state, config, seen, first)["native_y"] == -60
    assert search_layout_pool.collect(tmp_path, state, config, seen, first) is None
    assert len((tmp_path / "shortlist.jsonl").read_text().splitlines()) == 1
    restored, recovered = search_layout_pool.recover_results(tmp_path, config)
    assert restored == seen and recovered == first
    assert (tmp_path / "NATIVE_TARGET_REACHED.json").exists()
    assert not (tmp_path / "TARGET_REACHED.json").exists()
    assert not (tmp_path / "verified-huts.jsonl").exists()


class Patches:
    def __init__(self):
        self.stack = ExitStack()
    def setattr(self, target, name, value):
        self.stack.enter_context(patch.object(target, name, value))


class SearchVerificationModeTests(unittest.TestCase):
    def test_native_record(self):
        check_native_record_keeps_native_estimate_without_vanilla_fields()

    def test_resume_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            check_modes_resume_and_forbid_switching_populated_runs(Path(directory))

    def test_off_without_java(self):
        for world_type, biome in (("normal", None), ("large_biomes", None),
                                  ("single_biome", "minecraft:swamp")):
            with self.subTest(world_type=world_type):
                patches = Patches()
                try:
                    with tempfile.TemporaryDirectory() as directory:
                        check_off_search_runs_native_worker_without_java_or_eula(
                            Path(directory), patches, world_type, biome)
                finally:
                    patches.stack.close()

    def test_non_hut_single_biome_off_finishes_without_services_or_gpu(self):
        from ultra_low_hut import ROOT
        template = json.loads((ROOT / "data/mineshafts/templates.json").read_text())[0]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = dict(version="1.21", verification_mode="off", devices=[0], started_at=1,
                          world_type="single_biome", biome="minecraft:desert",
                          record_height=-55, target_height=-59,
                          qualified_search=dict(
                              json.loads((ROOT / "config/search/runtime.json").read_text()),
                              template=template))
            (root / "config.json").write_text(json.dumps(config))
            with patch.object(sys, "argv", ["search", "--root", str(root), "--resume"]), \
                 patch.object(search_huts.signal, "signal"), \
                 patch.object(search_huts, "start", side_effect=AssertionError("Java started")), \
                 patch.object(search_huts.subprocess, "Popen", side_effect=AssertionError("GPU started")):
                search_huts.main()
            result = json.loads((root / "STOPPED.json").read_text())
            self.assertEqual(result["reason"], "world-has-no-witch-huts")
            world = json.loads((root / "WORLD_HAS_NO_WITCH_HUTS.json").read_text())
            self.assertEqual(world["biome"], "minecraft:desert")

    def test_native_collect_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            check_native_campaign_collect_and_recovery_never_publish_verified_huts(Path(directory))


if __name__ == "__main__":
    unittest.main()
