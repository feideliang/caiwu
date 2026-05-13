"""Tests for data cleaning service."""

from __future__ import annotations

import pandas as pd
import pytest

from app.services.data_cleaner import (
    POSITIVE_COLUMNS,
    RANGE_RULES,
    CleaningError,
    CleaningResult,
    DataCleaner,
)


# ── Cleaning initialization tests ──────────────────────────


class TestDataCleanerInit:

    def test_default_config(self):
        cleaner = DataCleaner()
        assert cleaner.dedup_keys == ["metric_name", "period", "entity"]
        assert "gross_profit_rate" in cleaner.range_rules
        assert cleaner.fill_defaults["metric_unit"] == ""

    def test_custom_dedup_keys(self):
        cleaner = DataCleaner(dedup_keys=["metric_name", "period"])
        assert cleaner.dedup_keys == ["metric_name", "period"]

    def test_custom_range_rules(self):
        rules = {"custom_metric": (0.0, 100.0)}
        cleaner = DataCleaner(range_rules=rules)
        assert "custom_metric" in cleaner.range_rules
        assert cleaner.range_rules["custom_metric"] == (0.0, 100.0)


# ── Date normalization tests ────────────────────────────────


class TestDateNormalization:

    def test_already_normalized(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({"period": ["2024-01", "2024-02"]})
        result_df, errors, fixed = cleaner._normalize_dates(df)
        assert fixed == 0
        assert result_df.at[0, "period"] == "2024-01"

    def test_slash_date_format(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({"period": ["2024/01/15"]})
        result_df, errors, fixed = cleaner._normalize_dates(df)
        assert result_df.at[0, "period"] == "2024-01"
        assert fixed == 1

    def test_full_date_format(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({"period": ["2024-03-20"]})
        result_df, errors, fixed = cleaner._normalize_dates(df)
        assert result_df.at[0, "period"] == "2024-03"
        assert fixed == 1

    def test_quarter_format(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({"period": ["2024Q1", "2024Q3"]})
        result_df, errors, fixed = cleaner._normalize_dates(df)
        assert result_df.at[0, "period"] == "2024-Q1"
        assert result_df.at[1, "period"] == "2024-Q3"
        assert fixed == 2

    def test_chinese_month_format(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({"period": ["2024年1月", "2024年12月"]})
        result_df, errors, fixed = cleaner._normalize_dates(df)
        assert result_df.at[0, "period"] == "2024-01"
        assert result_df.at[1, "period"] == "2024-12"

    def test_yyyymm_format(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({"period": ["202401", "202412"]})
        result_df, errors, fixed = cleaner._normalize_dates(df)
        assert result_df.at[0, "period"] == "2024-01"
        assert result_df.at[1, "period"] == "2024-12"

    def test_empty_period(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({"period": ["", None, "2024-01"]})
        result_df, errors, fixed = cleaner._normalize_dates(df)
        # Empty periods should generate errors
        error_count = sum(1 for e in errors if "Empty period" in e.message)
        assert error_count >= 1

    def test_normalize_period_string_static(self):
        assert DataCleaner._normalize_period_string("2024-01") == "2024-01"
        assert DataCleaner._normalize_period_string("2024Q1") == "2024-Q1"
        assert DataCleaner._normalize_period_string("2024/01/15") == "2024-01"
        assert DataCleaner._normalize_period_string("2024年1月") == "2024-01"
        assert DataCleaner._normalize_period_string("202401") == "2024-01"
        # Unknown format passes through
        assert DataCleaner._normalize_period_string("unknown") == "unknown"

    def test_chinese_quarter_format(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({"period": ["2024年1季度", "2024年3季度"]})
        result_df, errors, fixed = cleaner._normalize_dates(df)
        assert result_df.at[0, "period"] == "2024-Q1"
        assert result_df.at[1, "period"] == "2024-Q3"


# ── Missing value handling tests ────────────────────────────


class TestMissingValueHandling:

    def test_fill_defaults(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["a", "b"],
            "metric_unit": [None, "CNY"],
            "entity": ["A", None],
        })
        result_df, errors, fixed = cleaner._handle_missing_values(df)

        assert result_df.at[0, "metric_unit"] == ""
        assert result_df.at[0, "entity"] == "A"
        assert result_df.at[1, "entity"] == ""

    def test_no_missing_values(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["a"],
            "metric_unit": ["CNY"],
            "entity": ["A"],
        })
        result_df, errors, fixed = cleaner._handle_missing_values(df)
        assert fixed == 0

    def test_missing_column_ignored(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({"metric_name": ["a"]})
        result_df, errors, fixed = cleaner._handle_missing_values(df)
        # Should not raise for missing optional columns
        assert isinstance(result_df, pd.DataFrame)


# ── Range validation tests ──────────────────────────────────


class TestRangeValidation:

    def test_valid_ranges(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "gross_profit_rate": [0.5, 0.3, -0.1],
        })
        result_df, errors, fixed = cleaner._validate_ranges(df)
        assert len(result_df) == 3  # No rows dropped
        assert len(errors) == 0

    def test_gross_profit_rate_out_of_range(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["gpr", "gpr", "gpr"],
            "period": ["2024-01", "2024-02", "2024-03"],
            "gross_profit_rate": [0.5, 1.5, -2.0],  # 1.5 > 1, -2 < -1
        })
        result_df, errors, fixed = cleaner._validate_ranges(df)

        # Rows with out-of-range values should be dropped
        assert len(result_df) == 1  # Only the valid row remains
        assert len(errors) == 2  # Two violations

    def test_negative_revenue(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue", "revenue"],
            "period": ["2024-01", "2024-02"],
            "revenue": [1000000, -500],  # Negative revenue should fail
        })
        result_df, errors, fixed = cleaner._validate_ranges(df)

        # Negative revenue row should be dropped
        assert len(result_df) == 1
        assert len(errors) >= 1

    def test_dso_range(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["dso"],
            "period": ["2024-01"],
            "dso": [500],  # > 365
        })
        result_df, errors, fixed = cleaner._validate_ranges(df)
        assert len(result_df) == 0  # Dropped

    def test_no_range_for_metric_value(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["custom"],
            "period": ["2024-01"],
            "metric_value": [-999999],  # metric_value has no range limit
        })
        result_df, errors, fixed = cleaner._validate_ranges(df)
        assert len(result_df) == 1  # Not dropped


# ── Deduplication tests ─────────────────────────────────────


class TestDeduplication:

    def test_remove_duplicates(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue", "revenue", "cost"],
            "metric_value": [1000, 1200, 500],
            "period": ["2024-01", "2024-01", "2024-01"],
            "entity": ["A", "A", "A"],
        })
        result_df, errors = cleaner._deduplicate(df)

        assert len(result_df) == 2  # One duplicate removed
        assert any("duplicate" in e.message.lower() for e in errors)

    def test_no_duplicates(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue", "cost"],
            "metric_value": [1000, 500],
            "period": ["2024-01", "2024-01"],
            "entity": ["A", "A"],
        })
        result_df, errors = cleaner._deduplicate(df)
        assert len(result_df) == 2
        assert len(errors) == 0

    def test_different_entities_not_duplicate(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue", "revenue"],
            "metric_value": [1000, 2000],
            "period": ["2024-01", "2024-01"],
            "entity": ["CompanyA", "CompanyB"],
        })
        result_df, errors = cleaner._deduplicate(df)
        assert len(result_df) == 2  # Different entities, not duplicates

    def test_no_dedup_keys_available(self):
        cleaner = DataCleaner(dedup_keys=["nonexistent_key"])
        df = pd.DataFrame({"a": [1, 1]})
        result_df, errors = cleaner._deduplicate(df)
        assert len(result_df) == 2  # No dedup possible


# ── Cross-validation tests ──────────────────────────────────


class TestCrossValidation:

    def test_all_rows_present(self):
        cleaner = DataCleaner()
        cleaned = pd.DataFrame({
            "metric_name": ["a", "b"],
            "period": ["2024-01", "2024-02"],
            "entity": ["A", "A"],
        })
        original = cleaned.copy()
        errors = cleaner._cross_validate(cleaned, original)
        assert len(errors) == 0

    def test_missing_rows_detected(self):
        cleaner = DataCleaner()
        cleaned = pd.DataFrame({
            "metric_name": ["a"],
            "period": ["2024-01"],
            "entity": ["A"],
        })
        original = pd.DataFrame({
            "metric_name": ["a", "b", "c"],
            "period": ["2024-01", "2024-01", "2024-01"],
            "entity": ["A", "A", "A"],
        })
        errors = cleaner._cross_validate(cleaned, original)
        assert any("not in cleaned" in e.message for e in errors)

    def test_no_key_columns(self):
        cleaner = DataCleaner(dedup_keys=["nonexistent"])
        cleaned = pd.DataFrame({"x": [1]})
        original = pd.DataFrame({"x": [1, 2]})
        errors = cleaner._cross_validate(cleaned, original)
        assert len(errors) == 0


# ── Full pipeline tests ─────────────────────────────────────


class TestFullPipeline:

    def test_clean_valid_data(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue", "cost", "dso"],
            "metric_value": [1000000, 500000, 45.0],
            "metric_unit": ["CNY", "CNY", ""],
            "period": ["2024-01", "2024-01", "2024-01"],
            "entity": ["A", "A", "A"],
        })
        result = cleaner.clean(df)

        assert result.cleaned_row_count == 3
        assert result.removed_row_count == 0

    def test_clean_with_duplicates(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue", "revenue", "cost"],
            "metric_value": [1000, 1200, 500],
            "period": ["2024-01", "2024-01", "2024-01"],
            "entity": ["A", "A", "A"],
        })
        result = cleaner.clean(df)

        assert result.cleaned_row_count == 2
        assert result.removed_row_count == 1

    def test_clean_with_out_of_range(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue", "revenue", "revenue"],
            "metric_value": [1000000, -500000, 300000],  # Negative revenue should fail
            "period": ["2024-01", "2024-02", "2024-03"],
            "entity": ["A", "A", "A"],
            "revenue": [1000000, -500000, 300000],  # Also in the revenue column for range check
        })
        result = cleaner.clean(df)

        assert result.removed_row_count >= 1

    def test_clean_with_missing_values(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue", "cost"],
            "metric_value": [1000, 500],
            "period": ["2024-01", "2024-02"],
            "entity": [None, "B"],
            "metric_unit": [None, "CNY"],
        })
        result = cleaner.clean(df)

        # Entity and metric_unit should be filled with defaults
        assert result.dataframe.at[0, "entity"] == ""
        assert result.dataframe.at[0, "metric_unit"] == ""

    def test_clean_empty_dataframe(self):
        cleaner = DataCleaner()
        df = pd.DataFrame()
        result = cleaner.clean(df)
        assert result.cleaned_row_count == 0
        assert result.original_row_count == 0

    def test_clean_with_original_df(self):
        cleaner = DataCleaner()
        original = pd.DataFrame({
            "metric_name": ["a", "b", "c"],
            "period": ["2024-01", "2024-01", "2024-01"],
            "entity": ["A", "A", "A"],
            "metric_value": [1, 2, 3],
        })
        # Cleaned df has only 2 rows (one deduped)
        cleaned = pd.DataFrame({
            "metric_name": ["a", "b"],
            "period": ["2024-01", "2024-01"],
            "entity": ["A", "A"],
            "metric_value": [1, 2],
        })
        result = cleaner.clean(cleaned, original_df=original)

        # Should have cross-validation warning
        cv_errors = [e for e in result.errors if e.rule == "cross_validation"]
        assert len(cv_errors) >= 1

    def test_clean_date_normalization_in_pipeline(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue"] * 3,
            "metric_value": [100, 200, 300],
            "period": ["2024/01/15", "2024Q2", "2024年3月"],
            "entity": ["A"] * 3,
        })
        result = cleaner.clean(df)

        assert result.dataframe.at[0, "period"] == "2024-01"
        assert result.dataframe.at[1, "period"] == "2024-Q2"
        assert result.dataframe.at[2, "period"] == "2024-03"


# ── Edge case tests ─────────────────────────────────────────


class TestEdgeCases:

    def test_very_large_dataframe(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue"] * 10000,
            "metric_value": range(10000),
            "period": ["2024-01"] * 10000,
            "entity": ["A"] * 10000,
        })
        result = cleaner.clean(df)
        # All should be deduped to 1
        assert result.cleaned_row_count == 1
        assert result.removed_row_count == 9999

    def test_nan_values_in_numeric_columns(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue", "cost"],
            "metric_value": [float("nan"), 500],
            "period": ["2024-01", "2024-02"],
            "entity": ["A", "A"],
        })
        result = cleaner.clean(df)
        # NaN values should not cause crashes
        assert result.cleaned_row_count >= 1

    def test_special_characters_in_strings(self):
        cleaner = DataCleaner()
        df = pd.DataFrame({
            "metric_name": ["revenue & cost", "利润 (毛利)"],
            "metric_value": [1000, 500],
            "period": ["2024-01", "2024-02"],
            "entity": ["A&B Corp", "中国公司"],
        })
        result = cleaner.clean(df)
        assert result.cleaned_row_count == 2
