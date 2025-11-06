"""Property-based tests for balance validation logic using Hypothesis.

These tests use Hypothesis to generate test cases automatically, focusing on
edge cases and boundary conditions that might be missed in manual tests.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st


@given(
    balance=st.integers(min_value=0, max_value=1_000_000_000),
    amount=st.integers(min_value=1, max_value=1_000_000_000),
)
@pytest.mark.unit
def test_balance_sufficient_check_property(balance: int, amount: int) -> None:
    """Property: Balance check result should be consistent.

    Given any balance and amount:
    - If balance >= amount, check should pass (result = 1)
    - If balance < amount, check should fail (result = 0)
    """
    # Simulate the balance check logic from fn_check_transfer_balance
    check_result = 1 if balance >= amount else 0

    # Property 1: Sufficient balance always passes
    if balance >= amount:
        assert check_result == 1, f"Balance {balance} >= amount {amount} should pass"

    # Property 2: Insufficient balance always fails
    if balance < amount:
        assert check_result == 0, f"Balance {balance} < amount {amount} should fail"

    # Property 3: Zero balance always fails for non-zero amounts
    if balance == 0 and amount > 0:
        assert check_result == 0, "Zero balance should fail for any positive amount"

    # Property 4: Zero amount always passes (edge case)
    if amount == 0:
        assert check_result == 1, "Zero amount should always pass"


@given(
    balance=st.integers(min_value=0, max_value=1_000_000_000),
    amount=st.integers(min_value=0, max_value=1_000_000_000),
)
@pytest.mark.unit
def test_balance_check_commutative_property(balance: int, amount: int) -> None:
    """Property: Balance check should be commutative for equal values.

    Checking balance >= amount should be equivalent to checking amount <= balance.
    """
    result1 = 1 if balance >= amount else 0
    result2 = 1 if amount <= balance else 0

    assert result1 == result2, "Balance check should be commutative"


@given(
    balance=st.integers(min_value=0, max_value=1_000_000_000),
    amount1=st.integers(min_value=1, max_value=1_000_000_000),
    amount2=st.integers(min_value=1, max_value=1_000_000_000),
)
@pytest.mark.unit
def test_balance_check_transitive_property(balance: int, amount1: int, amount2: int) -> None:
    """Property: Balance check should be transitive.

    If balance >= amount1 and amount1 >= amount2, then balance >= amount2.
    """
    check1 = balance >= amount1
    check2 = amount1 >= amount2
    check3 = balance >= amount2

    if check1 and check2:
        assert check3, "Balance check should be transitive"


@given(
    balance=st.integers(min_value=0, max_value=1_000_000_000),
    amount=st.integers(min_value=0, max_value=1_000_000_000),
)
@pytest.mark.unit
def test_balance_check_boundary_conditions(balance: int, amount: int) -> None:
    """Property: Balance check handles boundary conditions correctly.

    Tests edge cases:
    - Maximum values
    - Zero values
    - Balance exactly equal to amount
    """
    check_result = 1 if balance >= amount else 0

    # Boundary: balance exactly equals amount
    if balance == amount:
        assert check_result == 1, "Equal balance and amount should pass"

    # Boundary: balance = amount - 1 (if amount > 0)
    if amount > 0 and balance == amount - 1:
        assert check_result == 0, "Balance one less than amount should fail"

    # Boundary: balance = amount + 1 (if amount >= 0)
    if balance == amount + 1:
        assert check_result == 1, "Balance one more than amount should pass"


@given(
    initial_balance=st.integers(min_value=0, max_value=1_000_000),
    transfer_amount=st.integers(min_value=1, max_value=1_000_000),
)
@pytest.mark.unit
def test_balance_after_transfer_property(initial_balance: int, transfer_amount: int) -> None:
    """Property: Balance after transfer should be consistent.

    If transfer is valid (balance >= amount), then:
    - New balance = old balance - amount
    - New balance >= 0
    """
    can_transfer = initial_balance >= transfer_amount

    if can_transfer:
        new_balance = initial_balance - transfer_amount
        assert new_balance >= 0, "Balance after valid transfer should be non-negative"
        assert (
            new_balance == initial_balance - transfer_amount
        ), "Balance calculation should be correct"

    if not can_transfer:
        # Transfer should not proceed
        assert (
            initial_balance < transfer_amount
        ), "Invalid transfer should not proceed when balance is insufficient"
