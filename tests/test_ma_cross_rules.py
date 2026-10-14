"""
Tests for 'ma_cross' rule evaluation logic.
Covers moving average windows, baseline establishment on day L,
earliest crossover on day L+1, and crossover directionality.
"""

import unittest
from decimal import Decimal
from alerts import evaluate_ma_cross_rule


class TestMACrossRules(unittest.TestCase):
    def setUp(self):
        self.rule_above = {
            "id": "r2",
            "instrument": "TCS",
            "type": "ma_cross",
            "short": 5,
            "long": 20,
            "direction": "above",
        }
        self.rule_below = {
            "id": "r3",
            "instrument": "TCS",
            "type": "ma_cross",
            "short": 5,
            "long": 20,
            "direction": "below",
        }

    def test_insufficient_history_never_fires(self):
        """Fewer than long_win + 1 days can never evaluate a cross."""
        # Only 20 days: Long MA is defined on day 20, but day 19 had no Long MA.
        prices = [(f"2026-09-{i:02d}", Decimal("3900.00")) for i in range(1, 21)]
        alerts = evaluate_ma_cross_rule(self.rule_above, prices)
        self.assertEqual(len(alerts), 0)

    def test_earliest_cross_is_day_long_plus_one(self):
        """Day 21 (index 20) is the earliest possible day for a 5/20 cross."""
        # 20 days at 3900, but days 16..20 are lower (3800) so short MA < long MA on day 20
        prices = []
        for i in range(1, 16):
            prices.append((f"2026-09-{i:02d}", Decimal("3900.00")))
        for i in range(16, 21):
            prices.append((f"2026-09-{i:02d}", Decimal("3800.00")))
        # Day 21 price surges to 4500, causing short MA to cross above long MA
        prices.append(("2026-09-21", Decimal("4500.00")))

        alerts = evaluate_ma_cross_rule(self.rule_above, prices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "2026-09-21")
        self.assertEqual(alerts[0][1], "r2")
        self.assertEqual(alerts[0][2], "2026-09-21 r2 TCS ma_cross 5/20 above")

    def test_cross_below(self):
        """Short MA starts above long MA on day 20, and drops below on day 21."""
        prices = []
        # Days 1..15 at 3800
        for i in range(1, 16):
            prices.append((f"2026-09-{i:02d}", Decimal("3800.00")))
        # Days 16..20 at 3950 (short MA > long MA on day 20)
        for i in range(16, 21):
            prices.append((f"2026-09-{i:02d}", Decimal("3950.00")))
        # Day 21 drops sharply to 3200 (short MA crosses below long MA)
        prices.append(("2026-09-21", Decimal("3200.00")))

        alerts = evaluate_ma_cross_rule(self.rule_below, prices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "2026-09-21")
        self.assertEqual(alerts[0][2], "2026-09-21 r3 TCS ma_cross 5/20 below")

    def test_no_repeated_alerts_while_trend_persists(self):
        """Short MA staying above long MA on subsequent days does not trigger duplicate alerts."""
        prices = []
        for i in range(1, 16):
            prices.append((f"2026-09-{i:02d}", Decimal("3900.00")))
        for i in range(16, 21):
            prices.append((f"2026-09-{i:02d}", Decimal("3800.00")))
        # Days 21, 22, 23 all elevated
        prices.append(("2026-09-21", Decimal("4500.00")))  # Crosses above here
        prices.append(("2026-09-22", Decimal("4550.00")))  # Still above
        prices.append(("2026-09-23", Decimal("4600.00")))  # Still above

        alerts = evaluate_ma_cross_rule(self.rule_above, prices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "2026-09-21")

    def test_small_window_crossover(self):
        """Tests short window 2, long window 4."""
        rule_small = {
            "id": "r_small",
            "instrument": "AAPL",
            "type": "ma_cross",
            "short": 2,
            "long": 4,
            "direction": "above",
        }
        # Day 1: 10, Day 2: 10, Day 3: 8, Day 4: 8
        # Day 4: short MA (8) < long MA (9)
        # Day 5: 14 -> short MA (11) > long MA (10) -> fires above!
        prices = [
            ("2026-09-01", Decimal("10")),
            ("2026-09-02", Decimal("10")),
            ("2026-09-03", Decimal("8")),
            ("2026-09-04", Decimal("8")),
            ("2026-09-05", Decimal("14")),
        ]
        alerts = evaluate_ma_cross_rule(rule_small, prices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "2026-09-05")
        self.assertEqual(alerts[0][2], "2026-09-05 r_small AAPL ma_cross 2/4 above")


if __name__ == "__main__":
    unittest.main()
