#!/usr/bin/env python3
"""
Test Runner for Price Alert Tool.
Runs the entire test suite using Python's standard unittest framework.
Zero external dependencies required.
"""

import os
import sys
import unittest


def run_all_tests():
    project_dir = os.path.dirname(os.path.abspath(__file__))
    tests_dir = os.path.join(project_dir, "tests")

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=tests_dir, pattern="test_*.py")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    run_all_tests()
