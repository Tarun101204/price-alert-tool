"""
Integration and CLI tests for alerts.py.
Verifies end-to-end command line execution, argument handling,
stdout formatting, and ordering by date then rule id.
"""

import os
import subprocess
import sys
import unittest


class TestCLIIntegration(unittest.TestCase):
    def setUp(self):
        self.project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.alerts_script = os.path.join(self.project_dir, "alerts.py")
        self.sample_prices = os.path.join(self.project_dir, "data", "sample_prices.csv")
        self.sample_rules = os.path.join(self.project_dir, "data", "sample_rules.json")
        self.extended_prices = os.path.join(self.project_dir, "data", "extended_prices.csv")

    def _run_cli(self, args):
        cmd = [sys.executable, self.alerts_script] + args
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res

    def test_sample_dataset_from_brief(self):
        """Runs with sample_prices.csv and sample_rules.json from the brief."""
        res = self._run_cli([self.sample_prices, self.sample_rules])
        self.assertEqual(res.returncode, 0)
        output_lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        self.assertEqual(output_lines, ["2026-09-03 r1 INFY level below 1500"])

    def test_extended_dataset_both_alerts_fired(self):
        """Runs with extended dataset reproducing both alert lines from brief."""
        res = self._run_cli([self.extended_prices, self.sample_rules])
        self.assertEqual(res.returncode, 0)
        output_lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
        expected = [
            "2026-09-03 r1 INFY level below 1500",
            "2026-09-24 r2 TCS ma_cross 5/20 above",
        ]
        self.assertEqual(output_lines, expected)

    def test_sorting_by_date_then_rule_id(self):
        """When multiple alerts fire on the same date, they must be sorted by rule id."""
        # Create temp files for this specific test
        prices_content = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.00\n"
            "2026-09-01,TCS,4000.00\n"
            "2026-09-02,INFY,1480.00\n"
            "2026-09-02,TCS,3800.00\n"
        )
        # Two rules: r_z and r_a both firing on 2026-09-02
        rules_content = (
            '[\n'
            '  {"id": "r_z", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500},\n'
            '  {"id": "r_a", "instrument": "TCS", "type": "level", "direction": "below", "level": 3900}\n'
            ']\n'
        )
        import tempfile
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".csv") as pf:
            pf.write(prices_content)
            pf_name = pf.name
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as rf:
            rf.write(rules_content)
            rf_name = rf.name

        try:
            res = self._run_cli([pf_name, rf_name])
            self.assertEqual(res.returncode, 0)
            output_lines = [line.strip() for line in res.stdout.strip().splitlines() if line.strip()]
            expected = [
                "2026-09-02 r_a TCS level below 3900",
                "2026-09-02 r_z INFY level below 1500",
            ]
            self.assertEqual(output_lines, expected)
        finally:
            os.remove(pf_name)
            os.remove(rf_name)

    def test_missing_cli_arguments_fails_gracefully(self):
        """Running with no arguments exits with code 1 and prints usage."""
        res = self._run_cli([])
        self.assertEqual(res.returncode, 1)
        self.assertIn("Usage:", res.stderr)

    def test_nonexistent_file_exits_with_error(self):
        """Non-existent file exits with code 2."""
        res = self._run_cli(["nonexistent_prices.csv", self.sample_rules])
        self.assertEqual(res.returncode, 2)
        self.assertIn("Error:", res.stderr)


if __name__ == "__main__":
    unittest.main()
