"""Controller regressions for final candidate delivery and config publication."""

from contextlib import ExitStack
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from ultra_low_hut import ROOT
from ultra_low_hut.search import campaign, run


class SearchCompletionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.root = self.directory / "phases/phase000000/run"
        self.root.parent.mkdir(parents=True)
        self.template = json.loads((ROOT / "data/mineshafts/templates.json").read_text())[0]
        template_path = self.root.parent / "template.json"
        template_path.write_text(json.dumps(self.template))
        self.phase = dict(index=0, directory="phases/phase000000",
                          identity=list(campaign.domain_identity(campaign.normalize_template(self.template))),
                          template_sha256=campaign.digest(template_path))
        build = self.directory / "runs/hut-build/test-qualified"
        build.mkdir(parents=True)
        (build / "config.json").write_text(json.dumps(dict(
            screen={}, qualified_search=dict(template=self.template))))
        self.patches = ExitStack()
        self.addCleanup(self.patches.close)
        self.patches.enter_context(patch.object(run, "ROOT", self.directory))
        self.patches.enter_context(patch.object(run, "resolve_hunt", return_value=dict(
            screen={}, build_profile="test", requested_version="1.21")))
        self.patches.enter_context(patch.object(run, "resume_worker",
                                               side_effect=lambda path, *_: path.mkdir(exist_ok=True)))
        self.patches.enter_context(patch.object(run.signal, "signal"))
        self.patches.enter_context(patch.object(run.time, "sleep"))
        self.patches.enter_context(patch.object(run, "SearchLog"))
        self.patches.enter_context(patch.object(run, "SearchMetrics", return_value=SimpleNamespace(
            snapshot=lambda *_: {}, query=lambda *_: None, result=lambda *_: None)))

    def invoke(self, mode, *extra):
        self.patches.enter_context(patch.object(sys, "argv", [
            "search", "--root", str(self.root), "--devices", "0",
            "--verification", mode, "--exhaust", "--accept-eula", *extra]))
        run.main()

    def test_final_shortlist_is_verified_before_exhaustion_and_service_shutdown(self):
        row = dict(seed="123", x=16, z=32, discovery={}, geometry=dict(width=7),
                   reference=dict(accepted=True, y=-60))
        output = self.root / "gpu0/search000000"

        class Worker:
            pid = 123

            def poll(self):
                # The first poll occurs after collect() has scanned shortlists.
                # Publication and process exit then happen before exhaustion is checked.
                output.mkdir(exist_ok=True)
                (output / "shortlist.jsonl").write_text(json.dumps(row) + "\n")
                return 0

        service = Mock()
        service.poll.return_value = None
        group = Mock()
        group.ready.return_value = True
        group.submit.return_value = ("request.json", row)
        responses = {"1.21": dict(response=self.root / "response.json",
                                   result=dict(version="1.21", heights=[-60]))}
        group.collect.side_effect = [None, ({-60: ["1.21"]}, responses)]
        self.patches.enter_context(patch.object(run, "start", return_value=(service, {})))
        self.patches.enter_context(patch.object(run, "VerificationGroup", return_value=group))
        self.patches.enter_context(patch.object(run, "loading_order_fields", return_value={}))
        self.patches.enter_context(patch.object(run.subprocess, "Popen", return_value=Worker()))

        def terminate(process):
            if process is service:
                self.assertEqual(group.collect.call_count, 2)
                self.assertEqual(len((self.root / "validation.jsonl").read_text().splitlines()), 1)

        self.patches.enter_context(patch.object(run, "terminate", side_effect=terminate))
        self.invoke("on")
        stopped = json.loads((self.root / "STOPPED.json").read_text())
        self.assertEqual(stopped["reason"], "coordinate-domain-exhausted")
        self.assertEqual(stopped["verified"], 1)
        self.assertEqual(stopped["pending"], 0)
        self.assertEqual(group.submit.call_count, 1)
        self.assertEqual(json.loads((self.root / "verified-huts.jsonl").read_text())["HPos"], -60)

    def test_first_published_config_is_complete_and_stable_for_campaign(self):
        published = []
        write = run.atomic

        def publish(path, value):
            write(path, value)
            if path == self.root / "config.json":
                published.append(json.loads(path.read_text()))
                self.assertTrue({"verify_versions", "verify_workers", "verify_java"} <= value.keys())
                campaign.check_phase(self.directory, self.phase)

        worker = Mock(pid=123)
        worker.poll.return_value = 0
        self.patches.enter_context(patch.object(run, "atomic", side_effect=publish))
        self.patches.enter_context(patch.object(run.subprocess, "Popen", return_value=worker))
        self.patches.enter_context(patch.object(run, "terminate"))
        self.invoke("off")
        self.assertEqual(len(published), 1)
        campaign.check_phase(self.directory, self.phase)
        self.assertEqual(json.loads((self.root / "STOPPED.json").read_text())["reason"],
                         "coordinate-domain-exhausted")


    def test_campaign_resume_allows_verifier_resources_but_freezes_search(self):
        worker = Mock(pid=123)
        worker.poll.return_value = 0
        self.patches.enter_context(patch.object(run.subprocess, "Popen", return_value=worker))
        self.patches.enter_context(patch.object(run, "terminate"))
        self.invoke("off")
        config_path = self.root / "config.json"
        # A pre-upgrade campaign must validate its old fingerprint first.
        self.phase["child_config_sha256"] = campaign.digest(config_path)
        campaign.check_phase(self.directory, self.phase)
        self.assertNotIn("child_config_sha256", self.phase)
        self.invoke("off", "--resume", "--verify-workers", "8",
                    "--verify-java", "1.21=/custom/jdk/bin/java")
        campaign.check_phase(self.directory, self.phase)
        saved = json.loads(config_path.read_text())
        self.assertEqual(saved["verify_workers"], 8)
        self.assertEqual(saved["verify_java"]["1.21"], "/custom/jdk/bin/java")
        saved["target_height"] -= 1
        config_path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, "Saved child configuration changed"):
            campaign.check_phase(self.directory, self.phase)

    def test_legacy_campaign_fingerprint_does_not_accept_changed_configuration(self):
        self.root.mkdir()
        config_path = self.root / "config.json"
        saved = dict(qualified_search=dict(template=self.template), target_height=-59)
        config_path.write_text(json.dumps(saved))
        self.phase["child_config_sha256"] = campaign.digest(config_path)
        saved["target_height"] = -58
        config_path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, "Saved child configuration changed"):
            campaign.check_phase(self.directory, self.phase)
        self.assertNotIn("child_search_sha256", self.phase)


if __name__ == "__main__":
    unittest.main()
