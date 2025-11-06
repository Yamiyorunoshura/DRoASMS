import pytest


def _threshold(n: int) -> int:
    return n // 2 + 1


@pytest.mark.unit
def test_threshold_formula_sample_values() -> None:
    for n, expected in [(1, 1), (2, 2), (3, 2), (4, 3), (5, 3), (10, 6)]:
        assert _threshold(n) == expected


def _early_reject(approve: int, n: int, total_voted: int, t: int) -> bool:
    remaining = max(0, n - total_voted)
    return approve + remaining < t


@pytest.mark.unit
def test_early_rejection_logic() -> None:
    # N=5, T=3; approve=1, voted=4 -> remaining=1; 1+1 < 3 => early reject
    assert _early_reject(approve=1, n=5, total_voted=4, t=3) is True

    # N=5, T=3; approve=2, voted=3 -> remaining=2; 2+2 >= 3 => cannot early reject
    assert _early_reject(approve=2, n=5, total_voted=3, t=3) is False
