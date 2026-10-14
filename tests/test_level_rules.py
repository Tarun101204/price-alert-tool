"""
Tests for 'level' rule evaluation logic.
Covers crossing semantics, boundary conditions, touching behavior,
and multiple transition cycles.
"""

import unittest
from decimal import Decimal
from alerts import evaluate_level_rule


class TestLevelRules(unittest.TestCase):
    def setUp(self):
        self.rule_below = {
            "id": "r1",
            "instrument": "INFY",
            "type": "level",
            "direction": "below",
            "level": Decimal("1500"),
            "raw_level": 1500,
        }
        self.rule_above = {
            "id": "r2",
            "instrument": "INFY",
            "type": "level",
            "direction": "above",
            "level": Decimal("1500"),
            "raw_level": 1500,
        }

    def test_day_one_cannot_fire(self):
        """Day 1 lacks a previous day, so it cannot be on the other side."""
        prices = [
            ("2026-09-01", Decimal("1400.00")),
        ]
        alerts = evaluate_level_rule(self.rule_below, prices)
        self.assertEqual(len(alerts), 0)

    def test_clean_cross_below(self):
        """Crosses from above (1520.50) to below (1498.00)."""
        prices = [
            ("2026-09-01", Decimal("1520.50")),
            ("2026-09-02", Decimal("1498.00")),
        ]
        alerts = evaluate_level_rule(self.rule_below, prices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "2026-09-02")
        self.assertEqual(alerts[0][1], "r1")
        self.assertEqual(alerts[0][2], "2026-09-02 r1 INFY level below 1500")

    def test_clean_cross_above(self):
        """Crosses from below (1480.00) to above (1510.00)."""
        prices = [
            ("2026-09-01", Decimal("1480.00")),
            ("2026-09-02", Decimal("1510.00")),
        ]
        alerts = evaluate_level_rule(self.rule_above, prices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "2026-09-02")
        self.assertEqual(alerts[0][2], "2026-09-02 r2 INFY level above 1500")

    def test_staying_on_same_side_does_not_fire_again(self):
        """Once crossed, remaining below on subsequent days should not re-trigger."""
        prices = [
            ("2026-09-01", Decimal("1520.00")),  # above
            ("2026-09-02", Decimal("1490.00")),  # fires below
            ("2026-09-03", Decimal("1480.00")),  # still below, no fire
            ("2026-09-04", Decimal("1470.00")),  # still below, no fire
        ]
        alerts = evaluate_level_rule(self.rule_below, prices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "2026-09-02")

    def test_touch_level_then_cross(self):
        """Price touches 1500 then drops below on next day: fires on the day it drops below."""
        prices = [
            ("2026-09-01", Decimal("1510.00")),  # above
            ("2026-09-02", Decimal("1500.00")),  # touches level
            ("2026-09-03", Decimal("1490.00")),  # crosses below
        ]
        alerts = evaluate_level_rule(self.rule_below, prices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][0], "2026-09-03")

    def test_touch_level_and_bounce_back_does_not_cross(self):
        """Price touches 1500 then bounces back up: never crosses below."""
        prices = [
            ("2026-09-01", Decimal("1510.00")),  # above
            ("2026-09-02", Decimal("1500.00")),  # touches
            ("2026-09-03", Decimal("1520.00")),  # back above
        ]
        alerts = evaluate_level_rule(self.rule_below, prices)
        self.assertEqual(len(alerts), 0)

    def test_multi_cycle_crossings(self):
        """Price oscillates across level multiple times: each valid cross fires."""
        prices = [
            ("2026-09-01", Decimal("1550.00")),  # above
            ("2026-09-02", Decimal("1450.00")),  # fires below
            ("2026-09-03", Decimal("1550.00")),  # goes above (no below alert)
            ("2026-09-04", Decimal("1480.00")),  # fires below again
        ]
        alerts = evaluate_level_rule(self.rule_below, prices)
        self.assertEqual(len(alerts), 2)
        self.assertEqual(alerts[0][0], "2026-09-02")
        self.assertEqual(alerts[1][0], "2026-09-04")

    def test_fractional_decimal_level(self):
        """Level rule with fractional value (e.g. 1500.50)."""
        rule_fractional = {
            "id": "r3",
            "instrument": "INFY",
            "type": "level",
            "direction": "above",
            "level": Decimal("1500.50"),
            "raw_level": 1500.50,
        }
        prices = [
            ("2026-09-01", Decimal("1500.00")),
            ("2026-09-02", Decimal("1500.55")),
        ]
        alerts = evaluate_level_rule(rule_fractional, prices)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0][2], "2026-09-02 r3 INFY level above 1500.5")


if __name__ == "__main__":
    unittest.main()
