import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import validate


class ValidatorTests(unittest.TestCase):
    def test_command_failure_preserves_status_and_output(self):
        result = validate.run([sys.executable, "-c", "print('failure detail'); raise SystemExit(7)"])
        self.assertEqual("FAIL", result["status"])
        self.assertEqual(7, result["exit_code"])
        self.assertEqual("failure detail", result["detail"])

    def test_timeout_is_a_failure(self):
        result = validate.run([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.1)
        self.assertEqual("FAIL", result["status"])
        self.assertIsNone(result["exit_code"])
        self.assertIn("Timed out", result["detail"])

    def test_report_output_is_bounded(self):
        result = validate.run([sys.executable, "-c", "print('x' * 10000)"])
        self.assertEqual("PASS", result["status"])
        self.assertEqual(4096, len(result["detail"]))

    def test_missing_executable_is_reported_without_crashing(self):
        result = validate.run(["/nonexistent/termux-validation-test"])
        self.assertEqual("FAIL", result["status"])

    @mock.patch.object(validate.platform, "machine", return_value="x86_64")
    def test_arm64_decoder_is_not_used_on_other_architectures(self, _):
        self.assertEqual("SKIP", validate.cpu_capabilities()["status"])

    def test_report_refuses_to_overwrite_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            report.write_text("keep this")
            with self.assertRaises(FileExistsError):
                validate.main(["--output", str(report)])
            self.assertEqual("keep this", report.read_text())

    def test_report_keeps_skipped_and_manual_checks_distinct_and_cleans_temp_files(self):
        with tempfile.TemporaryDirectory() as directory:
            report = Path(directory) / "report.json"
            with mock.patch.dict(os.environ, {"TMPDIR": directory}), \
                    mock.patch.object(validate, "metadata", return_value={}), \
                    mock.patch.object(validate, "cpu_capabilities", return_value={"status": "PASS"}), \
                    mock.patch.object(validate, "power_snapshot", return_value={}), \
                    mock.patch.object(validate, "smoke_tests", return_value=[
                        {"name": "required", "status": "FAIL"},
                        {"name": "optional", "status": "SKIP"}]), \
                    mock.patch.object(validate, "benchmarks") as bench, \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(1, validate.main(["--output", str(report)]))
                bench.assert_not_called()
            result = json.loads(report.read_text())
            self.assertEqual({"PASS": 0, "FAIL": 1, "SKIP": 1}, result["summary"])
            self.assertTrue(all(x["status"] == "NOT_RUN" for x in result["manual_checks"]))
            self.assertEqual([report], list(Path(directory).iterdir()))
            self.assertEqual(0o600, report.stat().st_mode & 0o777)


if __name__ == "__main__":
    unittest.main()
