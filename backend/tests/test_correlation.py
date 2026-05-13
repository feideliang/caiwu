"""Tests for the correlation analysis service."""

from __future__ import annotations

import math
import pytest

from app.services.correlation import (
    pearson_correlation,
    spearman_correlation,
    classify_strength,
    _rank_data,
)
from app.tasks.prediction import _compute_mape


class TestPearsonCorrelation:
    """Test Pearson correlation coefficient calculation."""

    def test_perfect_positive(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        r, p, n = pearson_correlation(x, y)
        assert r == pytest.approx(1.0, abs=1e-6)
        assert n == 5

    def test_perfect_negative(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 8.0, 6.0, 4.0, 2.0]
        r, p, n = pearson_correlation(x, y)
        assert r == pytest.approx(-1.0, abs=1e-6)

    def test_no_correlation(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [5.0, 3.0, 7.0, 2.0, 8.0]
        r, p, n = pearson_correlation(x, y)
        assert abs(r) < 0.5  # weak or no correlation

    def test_minimum_observations(self):
        x = [1.0, 2.0]
        y = [3.0, 4.0]
        with pytest.raises(Exception):  # BusinessError
            pearson_correlation(x, y)

    def test_constant_values(self):
        x = [5.0, 5.0, 5.0, 5.0]
        y = [1.0, 2.0, 3.0, 4.0]
        r, p, n = pearson_correlation(x, y)
        assert r == 0.0  # no variance in x

    def test_coefficient_bounded(self):
        import random
        random.seed(42)
        x = [random.uniform(0, 100) for _ in range(20)]
        y = [random.uniform(0, 100) for _ in range(20)]
        r, p, n = pearson_correlation(x, y)
        assert -1.0 <= r <= 1.0


class TestSpearmanCorrelation:
    """Test Spearman rank correlation."""

    def test_monotonic_positive(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [2.0, 4.0, 6.0, 8.0, 10.0]
        r, p, n = spearman_correlation(x, y)
        assert r == pytest.approx(1.0, abs=1e-6)

    def test_monotonic_negative(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [10.0, 8.0, 6.0, 4.0, 2.0]
        r, p, n = spearman_correlation(x, y)
        assert r == pytest.approx(-1.0, abs=1e-6)


class TestClassifyStrength:
    """Test correlation strength classification."""

    def test_strong(self):
        assert classify_strength(0.85) == "strong"
        assert classify_strength(-0.9) == "strong"
        assert classify_strength(0.7) == "strong"

    def test_moderate(self):
        assert classify_strength(0.5) == "moderate"
        assert classify_strength(-0.6) == "moderate"
        assert classify_strength(0.4) == "moderate"

    def test_weak(self):
        assert classify_strength(0.2) == "weak"
        assert classify_strength(-0.3) == "weak"
        assert classify_strength(0.1) == "weak"

    def test_none(self):
        assert classify_strength(0.0) == "none"
        assert classify_strength(0.05) == "none"


class TestRankData:
    """Test rank data computation for Spearman."""

    def test_simple_ranking(self):
        assert _rank_data([10.0, 20.0, 30.0]) == [1.0, 2.0, 3.0]

    def test_ties_get_average_rank(self):
        ranks = _rank_data([10.0, 20.0, 20.0, 30.0])
        assert ranks[0] == 1.0
        assert ranks[1] == 2.5  # average of ranks 2 and 3
        assert ranks[2] == 2.5
        assert ranks[3] == 4.0


class TestMAPE:
    """Test Mean Absolute Percentage Error computation."""

    def test_perfect_prediction(self):
        assert _compute_mape([100.0, 200.0], [100.0, 200.0]) == 0.0

    def test_known_error(self):
        # Predicted 110 and 190 for actual 100 and 200
        # Errors: |100-110|/100 = 10%, |200-190|/200 = 5% -> MAPE = 7.5%
        mape = _compute_mape([100.0, 200.0], [110.0, 190.0])
        assert mape == pytest.approx(7.5, abs=0.1)

    def test_empty_lists(self):
        assert _compute_mape([], []) == 100.0

    def test_zero_actual_skipped(self):
        mape = _compute_mape([0.0, 100.0], [1.0, 110.0])
        # The 0.0 actual is skipped, only 10% error remains
        assert mape == pytest.approx(10.0, abs=0.1)
