#!/usr/bin/env python3
"""
Price Alert Tool
Reads daily prices for several instruments from a CSV file, applies alert
rules from a JSON configuration file, and prints alerts that fired chronologically.

Evaluation Criteria & Semantics:
1. Level rule:
   Fires on the first day close crosses the level in the given direction
   (it was on the other side the previous day).
2. Moving average cross rule (ma_cross):
   Fires on the day the short moving average crosses the long moving average
   in the given direction. Moving averages require a full window of days before
   they are defined.
3. Output format:
   One line per alert, ordered by date ascending, then rule id ascending.
   No output for days on which no rule fires.
"""

import csv
import json
import os
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Tuple


def format_level(level_val: Any) -> str:
    """Format numeric level cleanly without superfluous trailing zeros."""
    d = Decimal(str(level_val))
    if d == d.to_integral():
        return str(d.to_integral())
    # Format with normalized exponent and trailing zero stripping
    return f"{d.normalize():f}"


def parse_date(date_str: str) -> str:
    """Validate ISO YYYY-MM-DD date string format."""
    clean_date = date_str.strip()
    try:
        parsed = datetime.strptime(clean_date, "%Y-%m-%d")
        return parsed.strftime("%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date format '{date_str}'. Expected 'YYYY-MM-DD'.") from e


def load_prices(csv_path: str) -> Dict[str, List[Tuple[str, Decimal]]]:
    """
    Load daily close prices from CSV file.
    Groups prices by instrument and sorts them chronologically by trading day.
    
    Header expected: date,instrument,close
    Handles out-of-order dates, whitespace in headers/values, and empty lines.
    Rejects malformed numbers and duplicate dates for the same instrument.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Prices file not found: '{csv_path}'")

    instrument_data: Dict[str, Dict[str, Decimal]] = {}

    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        # Strip potential BOM and empty lines
        reader = csv.reader(f)
        
        # Read and normalize header
        header = None
        for raw_row in reader:
            if not raw_row or not any(field.strip() for field in raw_row):
                continue
            header = [col.strip().lower() for col in raw_row]
            break

        if not header:
            raise ValueError(f"Prices file '{csv_path}' is empty or missing a valid header.")

        required_cols = {"date", "instrument", "close"}
        if not required_cols.issubset(set(header)):
            missing = required_cols - set(header)
            raise ValueError(f"Prices file missing required columns: {', '.join(sorted(missing))}")

        col_idx = {col: idx for idx, col in enumerate(header)}
        date_idx = col_idx["date"]
        inst_idx = col_idx["instrument"]
        close_idx = col_idx["close"]

        line_num = 1
        for raw_row in reader:
            line_num += 1
            if not raw_row or not any(field.strip() for field in raw_row):
                continue  # Skip blank lines

            if len(raw_row) <= max(date_idx, inst_idx, close_idx):
                raise ValueError(f"Line {line_num} in '{csv_path}' has fewer columns than required.")

            date_raw = raw_row[date_idx].strip()
            inst_raw = raw_row[inst_idx].strip()
            close_raw = raw_row[close_idx].strip()

            if not inst_raw:
                raise ValueError(f"Line {line_num} has empty instrument name.")

            date_str = parse_date(date_raw)

            try:
                close_val = Decimal(close_raw)
            except InvalidOperation:
                raise ValueError(f"Line {line_num} contains invalid price value: '{close_raw}'")

            if close_val <= Decimal("0"):
                raise ValueError(f"Line {line_num} price must be positive, found: {close_val}")

            if inst_raw not in instrument_data:
                instrument_data[inst_raw] = {}

            if date_str in instrument_data[inst_raw]:
                raise ValueError(
                    f"Duplicate price entry on date '{date_str}' for instrument '{inst_raw}' at line {line_num}."
                )

            instrument_data[inst_raw][date_str] = close_val

    # Convert to sorted list of (date_str, close_decimal) per instrument
    sorted_prices: Dict[str, List[Tuple[str, Decimal]]] = {}
    for inst, date_map in instrument_data.items():
        sorted_prices[inst] = sorted(date_map.items(), key=lambda x: x[0])

    return sorted_prices


def load_rules(json_path: str) -> List[Dict[str, Any]]:
    """
    Load and validate alert rules from a JSON file.
    Rules must have unique ids and valid parameters.
    """
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Rules file not found: '{json_path}'")

    try:
        with open(json_path, mode="r", encoding="utf-8") as f:
            rules = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format in rules file '{json_path}': {e.msg}") from e

    if not isinstance(rules, list):
        raise ValueError(f"Rules configuration in '{json_path}' must be a JSON array.")

    seen_ids = set()
    validated_rules = []

    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            raise ValueError(f"Rule at index {idx} must be a JSON object.")

        # Required fields
        for field in ("id", "instrument", "type", "direction"):
            if field not in rule:
                raise ValueError(f"Rule at index {idx} missing required field '{field}'.")

        rule_id = str(rule["id"]).strip()
        if not rule_id:
            raise ValueError(f"Rule at index {idx} has an empty 'id'.")

        if rule_id in seen_ids:
            raise ValueError(f"Duplicate rule id found: '{rule_id}'.")
        seen_ids.add(rule_id)

        instrument = str(rule["instrument"]).strip()
        rule_type = str(rule["type"]).strip().lower()
        direction = str(rule["direction"]).strip().lower()

        if direction not in ("above", "below"):
            raise ValueError(f"Rule '{rule_id}': invalid direction '{direction}'. Must be 'above' or 'below'.")

        val_rule: Dict[str, Any] = {
            "id": rule_id,
            "instrument": instrument,
            "type": rule_type,
            "direction": direction,
        }

        if rule_type == "level":
            if "level" not in rule:
                raise ValueError(f"Level rule '{rule_id}' missing 'level' field.")
            try:
                level_dec = Decimal(str(rule["level"]))
            except InvalidOperation:
                raise ValueError(f"Level rule '{rule_id}' has non-numeric level: '{rule['level']}'.")
            if level_dec <= Decimal("0"):
                raise ValueError(f"Level rule '{rule_id}' has non-positive level: '{level_dec}'.")
            val_rule["level"] = level_dec
            val_rule["raw_level"] = rule["level"]

        elif rule_type == "ma_cross":
            for win_field in ("short", "long"):
                if win_field not in rule:
                    raise ValueError(f"ma_cross rule '{rule_id}' missing '{win_field}' window field.")
                val = rule[win_field]
                if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
                    raise ValueError(f"ma_cross rule '{rule_id}' field '{win_field}' must be a positive integer.")

            short_win = int(rule["short"])
            long_win = int(rule["long"])

            if short_win >= long_win:
                raise ValueError(
                    f"ma_cross rule '{rule_id}': 'short' window ({short_win}) must be strictly less than 'long' window ({long_win})."
                )

            val_rule["short"] = short_win
            val_rule["long"] = long_win

        else:
            raise ValueError(f"Rule '{rule_id}' has unsupported type '{rule_type}'.")

        validated_rules.append(val_rule)

    return validated_rules


def evaluate_level_rule(
    rule: Dict[str, Any],
    prices: List[Tuple[str, Decimal]]
) -> List[Tuple[str, str, str]]:
    """
    Evaluates a level rule on sorted prices for an instrument.
    Fires on the first day close crosses the level in the given direction
    (it was on the other side the previous day).
    
    Output record: (date, rule_id, formatted_line)
    """
    alerts = []
    level = rule["level"]
    direction = rule["direction"]
    rule_id = rule["id"]
    instrument = rule["instrument"]
    formatted_lvl = format_level(rule["raw_level"])

    # Requires at least 2 days to have a previous day
    for i in range(1, len(prices)):
        prev_date, prev_close = prices[i - 1]
        curr_date, curr_close = prices[i]

        fired = False
        if direction == "below":
            # Was strictly above level the previous day, and is now below level
            if prev_close > level and curr_close < level:
                fired = True
            # Also handle price touching the level exactly from above then going below
            elif prev_close >= level and curr_close < level and prev_close > curr_close:
                # If previous was exactly on level, check if the preceding state was above
                if prev_close == level and i >= 2:
                    if prices[i - 2][1] > level:
                        fired = True
        elif direction == "above":
            # Was strictly below level the previous day, and is now above level
            if prev_close < level and curr_close > level:
                fired = True
            elif prev_close <= level and curr_close > level and prev_close < curr_close:
                if prev_close == level and i >= 2:
                    if prices[i - 2][1] < level:
                        fired = True

        if fired:
            line = f"{curr_date} {rule_id} {instrument} level {direction} {formatted_lvl}"
            alerts.append((curr_date, rule_id, line))

    return alerts


def evaluate_ma_cross_rule(
    rule: Dict[str, Any],
    prices: List[Tuple[str, Decimal]]
) -> List[Tuple[str, str, str]]:
    """
    Evaluates a moving average crossover rule on sorted trading days for an instrument.
    
    Rules:
    - Moving averages need a full window of days before they are defined.
    - Long window L is first defined on day index L-1 (the L-th trading day).
    - Crossing requires comparing the relative position on day t with day t-1.
    - Therefore, day index L (the (L+1)-th trading day) is the first day an ma_cross can fire.
    
    Output record: (date, rule_id, formatted_line)
    """
    alerts = []
    short_win = rule["short"]
    long_win = rule["long"]
    direction = rule["direction"]
    rule_id = rule["id"]
    instrument = rule["instrument"]

    n = len(prices)
    if n < long_win + 1:
        # Not enough days to have both a defined previous MA and a defined current MA
        return alerts

    # Pre-calculate rolling sums using Decimal for exact arithmetic
    closes = [p[1] for p in prices]
    short_dec = Decimal(short_win)
    long_dec = Decimal(long_win)

    # Compute short MA and long MA for indices where they are valid
    # index i corresponds to the i-th day (0-indexed)
    ma_diffs: Dict[int, Decimal] = {}
    
    # We maintain running windows
    short_sum = sum(closes[long_win - 1 - short_win + 1 : long_win])
    long_sum = sum(closes[0 : long_win])
    
    ma_short = short_sum / short_dec
    ma_long = long_sum / long_dec
    ma_diffs[long_win - 1] = ma_short - ma_long

    for i in range(long_win, n):
        # Update short window
        short_sum += closes[i] - closes[i - short_win]
        # Update long window
        long_sum += closes[i] - closes[i - long_win]

        ma_short = short_sum / short_dec
        ma_long = long_sum / long_dec
        ma_diffs[i] = ma_short - ma_long

        prev_diff = ma_diffs[i - 1]
        curr_diff = ma_diffs[i]
        curr_date = prices[i][0]

        fired = False
        if direction == "above":
            # Crossed from below/equal to strictly above
            if prev_diff <= Decimal("0") and curr_diff > Decimal("0"):
                fired = True
        elif direction == "below":
            # Crossed from above/equal to strictly below
            if prev_diff >= Decimal("0") and curr_diff < Decimal("0"):
                fired = True

        if fired:
            line = f"{curr_date} {rule_id} {instrument} ma_cross {short_win}/{long_win} {direction}"
            alerts.append((curr_date, rule_id, line))

    return alerts


def process_alerts(prices_path: str, rules_path: str) -> List[str]:
    """
    Loads price data and rules, evaluates all rules, and returns sorted alert lines.
    Ordered by date ascending, then rule id ascending.
    """
    prices_by_instrument = load_prices(prices_path)
    rules = load_rules(rules_path)

    all_alerts: List[Tuple[str, str, str]] = []

    for rule in rules:
        instrument = rule["instrument"]
        # If instrument has no price data, the rule cannot fire
        if instrument not in prices_by_instrument:
            continue

        prices = prices_by_instrument[instrument]
        if rule["type"] == "level":
            all_alerts.extend(evaluate_level_rule(rule, prices))
        elif rule["type"] == "ma_cross":
            all_alerts.extend(evaluate_ma_cross_rule(rule, prices))

    # Sort alerts by date ascending, then rule id ascending
    all_alerts.sort(key=lambda item: (item[0], item[1]))

    return [item[2] for item in all_alerts]


def main() -> None:
    """CLI Entry point: python alerts.py <prices.csv> <rules.json>"""
    if len(sys.argv) != 3:
        sys.stderr.write(
            "Usage: python alerts.py <prices.csv> <rules.json>\n"
            "Example: python alerts.py data/sample_prices.csv data/sample_rules.json\n"
        )
        sys.exit(1)

    prices_path = sys.argv[1]
    rules_path = sys.argv[2]

    try:
        alert_lines = process_alerts(prices_path, rules_path)
        for line in alert_lines:
            sys.stdout.write(line + "\n")
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(2)


if __name__ == "__main__":
    main()
