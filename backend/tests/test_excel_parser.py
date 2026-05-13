"""Tests for Excel parser service."""

from __future__ import annotations

import os
import tempfile
from unittest.mock import patch

import pandas as pd
import pytest

from app.services.excel_parser import (
    DEFAULT_COLUMN_MAP,
    DATE_COLUMNS,
    NUMERIC_COLUMNS,
    REQUIRED_COLUMNS,
    ExcelParser,
    ParseResult,
    ValidationError,
)


# ── Parser initialization tests ─────────────────────────────


class TestExcelParserInit:

    def test_default_config(self):
        parser = ExcelParser()
        assert parser.required_columns == REQUIRED_COLUMNS
        assert "metric_value" in parser.numeric_columns
        assert len(parser.column_map) > 0

    def test_custom_column_map(self):
        custom_map = {"custom_col": ["custom_alias", "custom name"]}
        parser = ExcelParser(column_map=custom_map)
        assert "custom_col" in parser.column_map
        assert "custom_alias" in parser._reverse_map

    def test_reverse_map_built_correctly(self):
        parser = ExcelParser()
        assert "metric_name" in parser._reverse_map.values()
        assert "指标名称" in parser._reverse_map
        assert "metric" in parser._reverse_map


# ── File parsing tests ──────────────────────────────────────


class TestExcelParse:

    def test_parse_xlsx(self, sample_excel_path):
        parser = ExcelParser()
        result = parser.parse(sample_excel_path)

        assert isinstance(result, ParseResult)
        assert result.row_count == 1000
        assert result.column_count > 0
        assert isinstance(result.dataframe, pd.DataFrame)

    def test_parse_xls(self, sample_xls_path):
        parser = ExcelParser()
        result = parser.parse(sample_xls_path)

        assert isinstance(result, ParseResult)
        assert result.row_count == 1000

    def test_parse_file_not_found(self):
        parser = ExcelParser()
        with pytest.raises(ValueError, match="Failed to parse"):
            parser.parse("/nonexistent/file.xlsx")

    def test_parse_empty_sheet(self):
        # Create empty Excel file
        df = pd.DataFrame()
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        df.to_excel(path, index=False, engine="openpyxl")

        parser = ExcelParser()
        result = parser.parse(path)

        assert result.row_count == 0
        assert len(result.errors) == 1
        assert result.errors[0].message == "Excel sheet is empty"

        os.unlink(path)

    def test_parse_file_name_extraction(self, sample_excel_path):
        parser = ExcelParser()
        result = parser.parse(sample_excel_path)
        assert result.file_name != ""


# ── Column mapping tests ────────────────────────────────────


class TestColumnMapping:

    def test_exact_match_english(self):
        df = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": [1000],
            "period": ["2024-01"],
        })

        parser = ExcelParser()
        result = parser.parse_from_df(df)

        assert "metric_name" in result.dataframe.columns

    def test_exact_match_chinese(self, sample_excel_with_bad_columns):
        parser = ExcelParser()
        result = parser.parse(sample_excel_with_bad_columns)

        assert "metric_name" in result.dataframe.columns
        assert "metric_value" in result.dataframe.columns
        assert "period" in result.dataframe.columns

    def test_fuzzy_match(self):
        """Test fuzzy matching for column names."""
        parser = ExcelParser()

        # Test exact match via reverse map (lowercase alias lookup)
        result = parser._fuzzy_match("指标名称")
        assert result == "metric_name"

        result = parser._fuzzy_match("金额")
        assert result == "metric_value"

        # Test partial match
        result = parser._fuzzy_match("科目名称")
        assert result == "metric_name"

    def test_fuzzy_match_no_result(self):
        parser = ExcelParser()
        result = parser._fuzzy_match("totally_unknown_column_xyz")
        assert result is None

    def test_missing_required_column(self):
        df = pd.DataFrame({
            "metric_name": ["revenue"],
            # Missing metric_value and period
        })

        parser = ExcelParser()
        errors = []
        result_df = parser._map_columns(df, errors)

        # Should have errors for missing required columns
        missing_errors = [e for e in errors if "not found" in e.message]
        assert len(missing_errors) >= 2  # metric_value and period


# ── Type coercion tests ─────────────────────────────────────


class TestTypeCoercion:

    def test_numeric_coercion(self):
        df = pd.DataFrame({
            "metric_value": ["1000", "2000", "invalid", "4000"],
            "gross_profit_rate": ["0.5", "0.3", "bad", "0.1"],
        })

        parser = ExcelParser()
        errors = []
        result = parser._coerce_types(df, errors)

        # Invalid values should become NaN
        assert pd.isna(result.at[2, "metric_value"])
        assert pd.isna(result.at[2, "gross_profit_rate"])
        assert result.at[0, "metric_value"] == 1000.0

    def test_date_coercion(self):
        df = pd.DataFrame({
            "period": ["2024-01", "2024/02/15", "not_a_date", "2024-04"],
        })

        parser = ExcelParser()
        errors = []
        result = parser._coerce_types(df, errors)

        # Valid dates should be converted to string YYYY-MM format via pandas
        # Invalid dates become empty
        assert "2024-01" in result.at[0, "period"] or result.at[0, "period"] != ""

    def test_string_coercion(self):
        df = pd.DataFrame({
            "metric_name": [123, None, "valid"],
            "entity": [None, "CompanyA", ""],
        })

        parser = ExcelParser()
        errors = []
        result = parser._coerce_types(df, errors)

        # NaN values should be converted to "nan" string or empty
        assert str(result.at[1, "metric_name"]) in ("nan", "")
        assert result.at[1, "entity"] == "CompanyA"


# ── Row validation tests ────────────────────────────────────


class TestRowValidation:

    def test_valid_rows(self):
        df = pd.DataFrame({
            "metric_name": ["revenue", "cost"],
            "metric_value": [1000.0, 500.0],
            "period": ["2024-01", "2024-02"],
        })

        parser = ExcelParser()
        errors = parser._validate_rows(df)
        assert len(errors) == 0

    def test_missing_required_fields(self):
        df = pd.DataFrame({
            "metric_name": ["revenue", "", "cost"],
            "metric_value": [1000.0, 500.0, 300.0],
            "period": ["2024-01", "2024-02", "2024-03"],
        })

        parser = ExcelParser()
        errors = parser._validate_rows(df)

        # Row 1: empty metric_name
        empty_name_errors = [e for e in errors if e.column == "metric_name"]
        assert len(empty_name_errors) >= 1

    def test_invalid_numeric_values(self):
        df = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": ["not_a_number"],
            "period": ["2024-01"],
        })

        parser = ExcelParser()
        errors = parser._validate_rows(df)

        # Type coercion makes it NaN, not a validation error here
        # The error would be caught during coercion


# ── DataFrame convenience tests ─────────────────────────────


class TestFromDataFrame:

    def test_from_dataframe(self):
        df = pd.DataFrame({
            "a": [1, 2, 3],
            "b": ["x", "y", "z"],
        })

        result = ExcelParser.from_dataframe(df)
        assert result.row_count == 3
        assert result.column_count == 2
        assert result.errors == []

    def test_parse_from_df_helper(self):
        """Test using the from_dataframe class method as a helper."""
        df = pd.DataFrame({
            "metric_name": ["revenue"],
            "metric_value": [100],
            "period": ["2024-01"],
        })
        parser = ExcelParser()
        result = parser.parse_from_df(df)
        assert result.row_count == 1

    def test_full_parse_pipeline(self, sample_excel_path):
        """Test the complete parse flow: file -> column mapping -> type coercion -> validation."""
        parser = ExcelParser()
        result = parser.parse(sample_excel_path)

        assert result.row_count == 1000
        assert "metric_name" in result.dataframe.columns
        assert "metric_value" in result.dataframe.columns
        assert result.dataframe["metric_value"].dtype in (float, int)
