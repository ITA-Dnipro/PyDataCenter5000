import pytest

from agents.utils import jitter


def test_jitter_within_bounds():
    """
    Test that uncorrelated jitter backoff generated values remain within
    bounds.
    """
    backoff = jitter(0.5, 1.5)

    for _ in range(100):
        value = next(backoff)
        assert 0.5 <= value <= 1.5


def test_jitter_min_equals_max():
    """Test the edge case when base is equal to cap in jitter."""
    for delay in [1, 2, 3]:
        backoff = jitter(delay, delay)
        assert next(backoff) == delay


def test_jitter_randomness():
    """
    Check that multiple calls to jitter generator produce different
    values.
    """
    backoff = jitter(0.5, 1.5)

    values = set(next(backoff) for _ in range(10))
    assert len(values) > 1


def test_jitter_min_larger_than_max_error():
    """
    Test the edge case when base is larger than cap
    (the error is raised).
    """
    with pytest.raises(
        ValueError, match='Minimum delay cannot be larger than maximum delay'
    ):
        next(jitter(1.5, 0.5))
