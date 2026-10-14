"""
Tests for real-world edge cases in prices and rules files.
Tests handling of:
- Out-of-order and interleaved dates
- Extra whitespace, BOM marks, and blank rows
- Missing columns or malformed headers
- Non-numeric, negative, or zero price values
- Duplicate date entries per instrument
- Unrecognized instruments in rules or data
- Invalid rule parameters (short >= long, negative windows, bad types)
- Floating-point vs Decimal precision edge cases
"""

import os
import tempfile
import unittest
from decimal import Decimal
from alerts import load_prices, load_rules, process_alerts


class TestRealWorldEdgeCases(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write_file(self, filename: str, content: str) -> str:
        path = os.path.join(self.temp_dir.name, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def test_out_of_order_dates_are_sorted_chronologically(self):
        """CSV with completely scrambled dates should be sorted properly per instrument."""
        csv_content = (
            "date,instrument,close\n"
            "2026-09-03,INFY,1498.00\n"
            "2026-09-01,INFY,1520.50\n"
            "2026-09-02,INFY,1534.10\n"
        )
        csv_path = self._write_file("scrambled.csv", csv_content)
        prices = load_prices(csv_path)

        infy_dates = [d for d, _ in prices["INFY"]]
        self.assertEqual(infy_dates, ["2026-09-01", "2026-09-02", "2026-09-03"])

    def test_whitespace_and_bom_resilience(self):
        """CSV with BOM, spaces in headers, spaces in values, and blank lines."""
        csv_content = (
            "\ufeff date , instrument , close \n"
            "\n"
            " 2026-09-01 , INFY , 1520.50 \n"
            " 2026-09-02 , INFY , 1480.00 \n"
            "\n"
        )
        csv_path = self._write_file("bom_spaces.csv", csv_content)
        prices = load_prices(csv_path)
        self.assertIn("INFY", prices)
        self.assertEqual(len(prices["INFY"]), 2)
        self.assertEqual(prices["INFY"][0][1], Decimal("1520.50"))

    def test_reject_duplicate_dates_for_same_instrument(self):
        """Two prices for the same instrument on the same date should be rejected."""
        csv_content = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.50\n"
            "2026-09-01,INFY,1525.00\n"
        )
        csv_path = self._write_file("duplicate_date.csv", csv_content)
        with self.assertRaises(ValueError) as ctx:
            load_prices(csv_path)
        self.assertIn("Duplicate price entry", str(ctx.exception))

    def test_reject_non_numeric_prices(self):
        """CSV containing NaN, null, or text close prices must raise ValueError."""
        csv_content = (
            "date,instrument,close\n"
            "2026-09-01,INFY,invalid_price\n"
        )
        csv_path = self._write_file("bad_price.csv", csv_content)
        with self.assertRaises(ValueError) as ctx:
            load_prices(csv_path)
        self.assertIn("invalid price value", str(ctx.exception))

    def test_reject_negative_or_zero_prices(self):
        """Close price of 0 or negative should be rejected."""
        csv_content = (
            "date,instrument,close\n"
            "2026-09-01,INFY,-50.00\n"
        )
        csv_path = self._write_file("neg_price.csv", csv_content)
        with self.assertRaises(ValueError) as ctx:
            load_prices(csv_path)
        self.assertIn("price must be positive", str(ctx.exception))

    def test_reject_missing_required_column(self):
        """Missing 'close' column in header."""
        csv_content = (
            "date,instrument\n"
            "2026-09-01,INFY\n"
        )
        csv_path = self._write_file("missing_col.csv", csv_content)
        with self.assertRaises(ValueError) as ctx:
            load_prices(csv_path)
        self.assertIn("missing required columns", str(ctx.exception))

    def test_invalid_date_format(self):
        """Non ISO YYYY-MM-DD date."""
        csv_content = (
            "date,instrument,close\n"
            "01-09-2026,INFY,1500.00\n"
        )
        csv_path = self._write_file("bad_date.csv", csv_content)
        with self.assertRaises(ValueError) as ctx:
            load_prices(csv_path)
        self.assertIn("Invalid date format", str(ctx.exception))

    def test_rule_instrument_not_in_price_data(self):
        """Rules targeting an instrument not in prices file should gracefully not fire."""
        csv_content = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.50\n"
            "2026-09-02,INFY,1490.00\n"
        )
        rules_content = (
            '[\n'
            '  {"id": "r1", "instrument": "RELIANCE", "type": "level", "direction": "below", "level": 2500}\n'
            ']\n'
        )
        csv_path = self._write_file("prices.csv", csv_content)
        rules_path = self._write_file("rules.json", rules_content)

        alerts = process_alerts(csv_path, rules_path)
        self.assertEqual(len(alerts), 0)

    def test_empty_rules_array(self):
        """Empty rules list should produce zero alerts."""
        csv_content = (
            "date,instrument,close\n"
            "2026-09-01,INFY,1520.50\n"
        )
        csv_path = self._write_file("prices.csv", csv_content)
        rules_path = self._write_file("empty_rules.json", "[]")

        alerts = process_alerts(csv_path, rules_path)
        self.assertEqual(len(alerts), 0)

    def test_invalid_ma_window_short_ge_long(self):
        """Rule where short >= long must raise ValueError."""
        rules_content = (
            '[\n'
            '  {"id": "r1", "instrument": "TCS", "type": "ma_cross", "short": 20, "long": 5, "direction": "above"}\n'
            ']\n'
        )
        rules_path = self._write_file("bad_windows.json", rules_content)
        with self.assertRaises(ValueError) as ctx:
            load_rules(rules_path)
        self.assertIn("must be strictly less than 'long' window", str(ctx.exception))

    def test_duplicate_rule_id(self):
        """Duplicate rule ID in JSON must raise ValueError."""
        rules_content = (
            '[\n'
            '  {"id": "r1", "instrument": "INFY", "type": "level", "direction": "below", "level": 1500},\n'
            '  {"id": "r1", "instrument": "TCS", "type": "level", "direction": "above", "level": 3900}\n'
            ']\n'
        )
        rules_path = self._write_file("dup_rules.json", rules_content)
        with self.assertRaises(ValueError) as ctx:
            load_rules(rules_path)
        self.assertIn("Duplicate rule id", str(ctx.exception))

    def test_unsupported_rule_type(self):
        """Unsupported rule type must raise ValueError."""
        rules_content = (
            '[\n'
            '  {"id": "r1", "instrument": "INFY", "type": "rsi", "direction": "above", "period": 14}\n'
            ']\n'
        )
        rules_path = self._write_file("bad_type.json", rules_content)
        with self.assertRaises(ValueError) as ctx:
            load_rules(rules_path)
        self.assertIn("unsupported type", str(ctx.exception))

    def test_decimal_precision_exactness(self):
        """Checks that Decimal prevents float precision errors (e.g. 0.1 + 0.2 != 0.3)."""
        rule = {
            "id": "r1",
            "instrument": "TEST",
            "type": "level",
            "direction": "below",
            "level": Decimal("0.3"),
            "raw_level": 0.3,
        }
        prices = [
            ("2026-09-01", Decimal("0.1") + Decimal("0.2") + Decimal("0.05")),  # 0.35 (above)
            ("2026-09-02", Decimal("0.1") + Decimal("0.2")),                    # 0.30 (touches level, not below)
            ("2026-09-03", Decimal("0.29")),                                   # 0.29 (crosses below)
        ]
        from alerts import evaluate_level_rule
        alerts = evaluate_level_rule(rule, prices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "2026-09-03")


if __name__ == "__main__":
    unittest.main()
