#!/usr/bin/env python3
"""Test runner script for running different test suites"""

import subprocess
import sys
import argparse


def run_tests(suite="all", verbose=False, coverage=False):
    """Run specified test suite"""
    
    base_cmd = ["pytest", "-v"] if verbose else ["pytest"]
    
    if coverage:
        base_cmd.extend(["--cov=app", "--cov-report=term-missing"])
    
    suites = {
        "all": [],
        "unit": ["tests/unit/", "-m", "unit"],
        "integration": ["tests/integration/", "-m", "integration"],
        "e2e": ["tests/e2e/", "-m", "e2e"],
        "live": ["tests/e2e/", "-m", "e2e_live"],
        "performance": ["tests/performance/", "-m", "performance"],
        "security": ["tests/security/", "-m", "security"],
        "fast": ["-m", "not slow"],
        "slow": ["-m", "slow"],
    }
    
    if suite not in suites:
        print(f"Unknown suite: {suite}")
        print(f"Available: {', '.join(suites.keys())}")
        sys.exit(1)
    
    cmd = base_cmd + suites[suite]
    
    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)
    
    result = subprocess.run(cmd, cwd="/Users/yogeshwargopi/Documents/webprojects/guvi-new/LLM-Code/backend")
    
    return result.returncode


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run test suites")
    parser.add_argument(
        "suite",
        nargs="?",
        default="all",
        choices=["all", "unit", "integration", "e2e", "live", "performance", "security", "fast", "slow"],
        help="Test suite to run"
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    parser.add_argument("-c", "--coverage", action="store_true", help="Run with coverage")
    
    args = parser.parse_args()
    
    exit_code = run_tests(args.suite, args.verbose, args.coverage)
    sys.exit(exit_code)