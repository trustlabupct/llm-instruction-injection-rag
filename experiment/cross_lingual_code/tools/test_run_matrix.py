#!/usr/bin/env python3
"""Automated tests for tools/run_matrix.py.

Run with:
    python tools/test_run_matrix.py

Everything runs inside a temporary sandbox directory and all subprocess
calls (build_dataset.py, run_experiment.py, evaluator.py,
build_dashboard.py) are mocked out, so this suite needs NO Ollama, NO
sentence-transformers, and does not touch your real data/results/figures
folders. It checks that:

  - safe_name()        sanitizes model names for use in folder names
  - ask() / ask_choice() / ask_int()
                        validate input, retry on bad input, and apply
                        defaults correctly
  - collect_configs()  builds the expected list of configurations from a
                        simulated interactive session
  - archive()          moves the right files into the right subfolders,
                        tags repeated runs correctly, does not crash when
                        some files are missing, and leaves the source
                        folders empty afterward
  - run_once()         calls build_dataset.py, run_experiment.py,
                        evaluator.py and (optionally) build_dashboard.py
                        with the correct arguments, in the right order,
                        and stops before archiving if a step fails
  - main()             keeps going after a failed run and reports an
                        accurate success/failure summary
"""
from __future__ import annotations

import builtins
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import run_tests as rm  # noqa: E402


class SandboxTestCase(unittest.TestCase):
    """Base class that points run_matrix's module-level paths at a temp dir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

        # Save originals so we can restore them after each test.
        self._orig = {
            "ROOT": rm.ROOT, "DATA": rm.DATA, "RESULTS": rm.RESULTS,
            "FIGURES": rm.FIGURES, "DASHBOARD": rm.DASHBOARD, "RUNS": rm.RUNS,
        }

        rm.ROOT = self.tmp_path
        rm.DATA = self.tmp_path / "data"
        rm.RESULTS = self.tmp_path / "results"
        rm.FIGURES = self.tmp_path / "figures"
        rm.DASHBOARD = self.tmp_path / "dashboard.html"
        rm.RUNS = self.tmp_path / "runs"

        rm.DATA.mkdir(parents=True, exist_ok=True)
        rm.RESULTS.mkdir(parents=True, exist_ok=True)
        rm.FIGURES.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        for name, value in self._orig.items():
            setattr(rm, name, value)
        self._tmp.cleanup()

    # -- helpers ------------------------------------------------------

    def _touch_all_outputs(self):
        for name in rm.DATA_FILES:
            (rm.DATA / name).write_text("fake")
        for name in rm.RESULTS_FILES:
            (rm.RESULTS / name).write_text("fake")
        for name in rm.FIGURE_FILES:
            (rm.FIGURES / name).write_bytes(b"fake")
        rm.DASHBOARD.write_text("<html>fake</html>")


class TestSafeName(unittest.TestCase):
    def test_replaces_colons_slashes_and_spaces(self):
        self.assertEqual(rm.safe_name("llama3.1:8b"), "llama3.1-8b")
        self.assertEqual(rm.safe_name("org/model-x"), "org-model-x")
        self.assertEqual(rm.safe_name("my model"), "my_model")
        self.assertEqual(rm.safe_name("plain-name"), "plain-name")


class TestPrompts(unittest.TestCase):
    def _feed(self, *answers):
        it = iter(answers)
        builtins.input = lambda prompt="": next(it)

    def tearDown(self):
        # Make sure a broken test can't leave input() patched for later tests.
        builtins.input = input

    def test_ask_returns_default_on_empty(self):
        self._feed("")
        self.assertEqual(rm.ask("Question", default="fallback"), "fallback")

    def test_ask_retries_until_non_empty_when_no_default(self):
        self._feed("", "", "value")
        self.assertEqual(rm.ask("Question"), "value")

    def test_ask_choice_rejects_invalid_then_accepts_valid(self):
        self._feed("maybe", "banana", "yes")
        result = rm.ask_choice("Pick", ["yes", "no"])
        self.assertEqual(result, "yes")

    def test_ask_choice_uses_default(self):
        self._feed("")
        self.assertEqual(rm.ask_choice("Pick", ["yes", "no"], default="no"), "no")

    def test_ask_int_rejects_non_numeric_and_too_small(self):
        self._feed("abc", "0", "5")
        self.assertEqual(rm.ask_int("How many", minimum=1), 5)

    def test_ask_int_uses_default(self):
        self._feed("")
        self.assertEqual(rm.ask_int("How many", default=3), 3)


class TestCollectConfigs(unittest.TestCase):
    def tearDown(self):
        builtins.input = input

    def test_builds_expected_config_list(self):
        answers = iter([
            "2",             # number of configurations
            "llama3.2:3b", "en", "sp", "", "3",   # config 1
            "gemma3:4b", "sp", "sp", "", "1",     # config 2
            "n",             # build dashboard?
        ])
        builtins.input = lambda prompt="": next(answers)

        configs, build_dashboard = rm.collect_configs()

        self.assertEqual(len(configs), 2)
        self.assertEqual(configs[0], {
            "model": "llama3.2:3b", "query": "en", "malicious": "sp",
            "backend": "ollama", "repeats": 3,
        })
        self.assertEqual(configs[1], {
            "model": "gemma3:4b", "query": "sp", "malicious": "sp",
            "backend": "ollama", "repeats": 1,
        })
        self.assertFalse(build_dashboard)

    def test_rejects_invalid_language_before_accepting(self):
        answers = iter([
            "1",
            "llama3.1:8b",   # model
            "fr", "en",      # query language: "fr" invalid, retry with "en"
            "sp",            # malicious language
            "",              # backend (default)
            "1",             # repeats
            "y",             # build dashboard?
        ])
        builtins.input = lambda prompt="": next(answers)

        configs, build_dashboard = rm.collect_configs()
        self.assertEqual(configs[0]["query"], "en")
        self.assertTrue(build_dashboard)


class TestArchive(SandboxTestCase):
    def test_moves_files_into_expected_structure(self):
        self._touch_all_outputs()

        dest = rm.archive("llama3.1:8b", "en", "sp")

        self.assertTrue((dest / "data" / "documents.csv").exists())
        self.assertTrue((dest / "data" / "test_queries.csv").exists())
        for name in rm.RESULTS_FILES:
            self.assertTrue((dest / "results" / name).exists())
        for name in rm.FIGURE_FILES:
            self.assertTrue((dest / "figures" / name).exists())
        self.assertTrue((dest / "dashboard.html").exists())

        self.assertIn("llama3.1-8b", dest.name)
        self.assertIn("q-en", dest.name)
        self.assertIn("m-sp", dest.name)

    def test_source_folders_are_emptied_after_archiving(self):
        self._touch_all_outputs()
        rm.archive("llama3.1:8b", "en", "sp")

        self.assertEqual(list(rm.DATA.iterdir()), [])
        self.assertEqual(list(rm.RESULTS.iterdir()), [])
        self.assertEqual(list(rm.FIGURES.iterdir()), [])
        self.assertFalse(rm.DASHBOARD.exists())

    def test_repetition_tag_present_only_when_more_than_one_repeat(self):
        self._touch_all_outputs()
        dest_multi = rm.archive("m", "en", "sp", rep=2, total_reps=5)
        self.assertIn("_rep2of5", dest_multi.name)

        self._touch_all_outputs()
        dest_single = rm.archive("m", "en", "sp", rep=1, total_reps=1)
        self.assertNotIn("rep", dest_single.name)

    def test_does_not_crash_when_source_files_are_missing(self):
        # Nothing was created in data/results/figures/dashboard.html.
        dest = rm.archive("m", "en", "sp")
        self.assertTrue((dest / "data").is_dir())
        self.assertTrue((dest / "results").is_dir())
        self.assertTrue((dest / "figures").is_dir())
        self.assertEqual(list((dest / "data").iterdir()), [])


class TestRunOnce(SandboxTestCase):
    CFG = {"model": "llama3.1:8b", "query": "en", "malicious": "sp", "backend": "ollama"}

    def test_calls_all_four_steps_in_order_with_correct_args(self):
        calls = []
        with mock.patch.object(rm, "sh", side_effect=lambda cmd: calls.append(cmd)), \
             mock.patch.object(rm, "archive") as archive_mock:
            rm.run_once(self.CFG, build_dashboard=True, rep=1, total_reps=1)

        self.assertEqual(len(calls), 4)
        self.assertIn("data/build_dataset.py", calls[0])
        self.assertIn("--query-language", calls[0])
        self.assertIn("en", calls[0])
        self.assertIn("--malicious_doc-language", calls[0])
        self.assertIn("sp", calls[0])

        self.assertIn("src/run_experiment.py", calls[1])
        self.assertIn("--model", calls[1])
        self.assertIn("llama3.1:8b", calls[1])
        self.assertIn("--malicious-doc-language", calls[1])

        self.assertIn("src/evaluator.py", calls[2])
        self.assertIn("tools/build_dashboard.py", calls[3])

        archive_mock.assert_called_once_with("llama3.1:8b", "en", "sp", 1, 1)

    def test_skips_dashboard_step_when_disabled(self):
        calls = []
        with mock.patch.object(rm, "sh", side_effect=lambda cmd: calls.append(cmd)), \
             mock.patch.object(rm, "archive"):
            rm.run_once(self.CFG, build_dashboard=False)

        self.assertEqual(len(calls), 3)
        self.assertTrue(all("build_dashboard.py" not in c for c in calls))

    def test_failure_in_a_step_propagates_and_skips_archiving(self):
        def fake_sh(cmd):
            if "src/run_experiment.py" in cmd:
                raise subprocess.CalledProcessError(1, cmd)

        with mock.patch.object(rm, "sh", side_effect=fake_sh), \
             mock.patch.object(rm, "archive") as archive_mock:
            with self.assertRaises(subprocess.CalledProcessError):
                rm.run_once(self.CFG, build_dashboard=True)
            archive_mock.assert_not_called()


class TestMain(unittest.TestCase):
    def tearDown(self):
        builtins.input = input

    def test_continues_after_a_failed_run_and_reports_summary(self):
        configs = [
            {"model": "m1", "query": "en", "malicious": "sp", "backend": "ollama", "repeats": 2},
            {"model": "m2", "query": "sp", "malicious": "sp", "backend": "ollama", "repeats": 1},
        ]

        call_log = []

        def fake_run_once(cfg, build_dashboard, rep=None, total_reps=None):
            call_log.append((cfg["model"], rep))
            if cfg["model"] == "m1" and rep == 1:
                raise subprocess.CalledProcessError(1, ["fake"])

        with mock.patch.object(rm, "collect_configs", return_value=(configs, True)), \
             mock.patch.object(rm, "ask_choice", return_value="y"), \
             mock.patch.object(rm, "run_once", side_effect=fake_run_once):
            with self.assertRaises(SystemExit) as ctx:
                rm.main()

        # 3 runs total (2 repeats + 1), one of them fails.
        self.assertEqual(len(call_log), 3)
        self.assertEqual(ctx.exception.code, 1)

    def test_reports_success_and_exits_cleanly_when_everything_passes(self):
        configs = [{"model": "m1", "query": "en", "malicious": "sp", "backend": "ollama", "repeats": 1}]

        with mock.patch.object(rm, "collect_configs", return_value=(configs, True)), \
             mock.patch.object(rm, "ask_choice", return_value="y"), \
             mock.patch.object(rm, "run_once", return_value=None):
            # Should NOT raise SystemExit when there are no failures.
            rm.main()

    def test_cancel_before_running_skips_execution_entirely(self):
        configs = [{"model": "m1", "query": "en", "malicious": "sp", "backend": "ollama", "repeats": 1}]

        with mock.patch.object(rm, "collect_configs", return_value=(configs, True)), \
             mock.patch.object(rm, "ask_choice", return_value="n"), \
             mock.patch.object(rm, "run_once") as run_once_mock:
            rm.main()
            run_once_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
