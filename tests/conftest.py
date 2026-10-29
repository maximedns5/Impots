"""Shared fixtures.

Building the tax-benefit system costs ~3 s and openfisca's first computation in a
process costs ~2 s more. Both are paid once, here, so that the timing assertions
in `test_engine.py` measure warm behaviour rather than start-up.
"""

from __future__ import annotations

import os

import pytest

from impots.engine import system, warm_up


def pytest_configure(config) -> None:
    """The suite runs the API as a local tool: computations open without a key and no
    rate limit (D-295). Set here, before any fixture of any scope makes a request.
    `tests/test_securite.py` clears these per test to check the closed defaults."""
    os.environ.setdefault("IMPOTS_AUTH", "aucune")
    os.environ.setdefault("IMPOTS_DEBIT", "0")
    os.environ.setdefault("IMPOTS_DEBIT_CALCULS", "0")


@pytest.fixture(scope="session", autouse=True)
def warm_engine() -> None:
    """Load the TBS and run one throwaway simulation before any test asserts timing."""
    system.baseline()
    warm_up()


@pytest.fixture
def quiet_machine() -> None:
    """Refuse to run a wall-clock budget on a machine that cannot honour one.

    The timing tests exist to catch a light request that started computing the
    benefits cascade — a change in what the code does. On an oversubscribed
    machine a stopwatch measures the neighbours instead: the same full-tier
    computation was observed taking 6.5 s and 18 s within a minute of each other
    at load 33 on 8 cores. Skipping loudly is honest; loosening the budget until
    it passes anywhere would throw the signal away.

    `test_light_tier_does_not_trigger_the_benefits_cascade` is the structural
    version of the same check and always runs.
    """
    if os.environ.get("IMPOTS_SKIP_PERF") == "1":
        pytest.skip("IMPOTS_SKIP_PERF=1")
    cores = os.cpu_count() or 1
    try:
        load = os.getloadavg()[0]
    except (OSError, AttributeError):  # pragma: no cover - not POSIX
        return
    if load > cores:
        pytest.skip(
            f"machine oversubscribed: load {load:.1f} on {cores} cores. "
            "Re-run when idle to check the timing budget."
        )
