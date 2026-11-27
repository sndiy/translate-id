"""Ensure the evaluation suite has >= 15 cases and passes end-to-end."""

import importlib.util

from helpers import ROOT

SPEC = importlib.util.spec_from_file_location("run_evals", ROOT / "evals" / "run_evals.py")
assert SPEC and SPEC.loader
MOD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MOD)


def test_eval_suite_has_at_least_15_cases_and_passes():
    results = MOD.run_all()
    assert len(results) >= 15
    failed = [r for r in results if not r.passed]
    assert failed == [], failed
