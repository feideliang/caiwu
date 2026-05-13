"""Excel parser service: parse .xlsx/.xls, column mapping, type coercion, validation."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

# Default column mapping: canonical_name -> possible Excel column names
DEFAULT_COLUMN_MAP: dict[str, list[str]] = {
    "metric_name": ["metric_name", "指标名称", "metric", "name", "科目", "科目名称"],
    "metric_value": ["metric_value", "指标值", "value", "金额", "数值", "amount"],
    "metric_unit": ["metric_unit", "单位", "unit"],
    "period": ["period", "期间", "日期", "date", "会计期间", "时间"],
    "entity": ["entity", "实体", "公司", "company", "部门", "department", "组织"],
    "gross_profit_rate": ["gross_profit_rate", "毛利率", "gross_profit"],
    "net_profit_rate": ["net_profit_rate", "净利率", "net_profit"],
    "dso": ["dso", "应收账款周转天数", "DSO"],
    "ito": ["ito", "存货周转天数", "ITO"],
    "dpo": ["dpo", "应付账款周转天数", "DPO"],
    "cash_conversion_cycle": ["cash_conversion_cycle", "现金周转期", "CCC"],
    "revenue": ["revenue", "收入", "营业收入"],
    "cost": ["cost", "成本", "营业成本"],
    "ar_amount": ["ar_amount", "应收账款", "AR"],
    "ap_amount": ["ap_amount", "应付账款", "AP"],
    "inventory": ["inventory", "存货", "库存"],
}

# Columns that should be numeric
NUMERIC_COLUMNS = {
    "metric_value",
    "gross_profit_rate",
    "net_profit_rate",
    "dso",
    "ito",
    "dpo",
    "cash_conversion_cycle",
    "revenue",
    "cost",
    "ar_amount",
    "ap_amount",
    "inventory",
}

# Columns that should be dates
DATE_COLUMNS = {"period"}

# Required columns for a valid financial data row
REQUIRED_COLUMNS = {"metric_name", "metric_value", "period"}


@dataclass
class ValidationError:
    """Single row validation error."""

    row_index: int
    column: str
    message: str
    raw_value: Any = None


@dataclass
class ParseResult:
    """Result of parsing an Excel file."""

    dataframe: pd.DataFrame
    errors: list[ValidationError]
    row_count: int
    column_count: int
    file_name: str = ""


class ExcelParser:
    """Parse Excel files (.xlsx/.xls) into validated DataFrames.

    Supports exact and fuzzy column name matching, type coercion,
    and row-level validation.
    """

    def __init__(
        self,
        column_map: dict[str, list[str]] | None = None,
        required_columns: set[str] | None = None,
        numeric_columns: set[str] | None = None,
    ) -> None:
        self.column_map = column_map or DEFAULT_COLUMN_MAP
        self.required_columns = required_columns or REQUIRED_COLUMNS
        self.numeric_columns = numeric_columns or NUMERIC_COLUMNS
        self._reverse_map = self._build_reverse_map()

    def _build_reverse_map(self) -> dict[str, str]:
        """Build a mapping from Excel column name -> canonical name."""
        reverse: dict[str, str] = {}
        for canonical, aliases in self.column_map.items():
            for alias in aliases:
                reverse[alias.lower().strip()] = canonical
        return reverse

    def parse(self, file_path: str, sheet_name: int | str = 0) -> ParseResult:
        """Parse an Excel file and return validated result.

        Args:
            file_path: Path to .xlsx or .xls file.
            sheet_name: Sheet name or index to parse.

        Returns:
            ParseResult with DataFrame and validation errors.
        """
        errors: list[ValidationError] = []
        file_name = file_path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]

        logger.info("Parsing Excel file: %s sheet=%s", file_path, sheet_name)

        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine="openpyxl")
        except Exception as exc:
            # Try xlrd for .xls files
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name, engine="xlrd")
            except Exception:
                raise ValueError(f"Failed to parse Excel file: {exc}")

        if df.empty:
            errors.append(ValidationError(
                row_index=-1,
                column="_file",
                message="Excel sheet is empty",
            ))
            return ParseResult(
                dataframe=pd.DataFrame(),
                errors=errors,
                row_count=0,
                column_count=0,
                file_name=file_name,
            )

        # Map columns to canonical names
        df = self._map_columns(df, errors)

        # Coerce types
        df = self._coerce_types(df, errors)

        # Validate rows
        errors.extend(self._validate_rows(df))

        result = ParseResult(
            dataframe=df,
            errors=errors,
            row_count=len(df),
            column_count=len(df.columns),
            file_name=file_name,
        )

        logger.info(
            "Parsed %d rows, %d columns, %d validation errors",
            result.row_count,
            result.column_count,
            len(errors),
        )
        return result

    def _map_columns(
        self, df: pd.DataFrame, errors: list[ValidationError]
    ) -> pd.DataFrame:
        """Map Excel column names to canonical names using exact + fuzzy matching."""
        original_columns = list(df.columns)
        rename_map: dict[str, str] = {}

        for col in original_columns:
            col_lower = str(col).lower().strip()

            # Exact match in reverse map
            if col_lower in self._reverse_map:
                rename_map[col] = self._reverse_map[col_lower]
                continue

            # Fuzzy match
            matched = self._fuzzy_match(col_lower)
            if matched:
                rename_map[col] = matched
                logger.debug("Fuzzy matched column '%s' -> '%s'", col, matched)
            else:
                # Keep original column name
                pass

        df = df.rename(columns=rename_map)

        # Check for missing required columns
        present = set(df.columns)
        for req_col in self.required_columns:
            if req_col not in present:
                errors.append(ValidationError(
                    row_index=-1,
                    column=req_col,
                    message=f"Required column '{req_col}' not found in Excel file",
                ))

        return df

    def _fuzzy_match(self, col_name: str) -> str | None:
        """Attempt fuzzy matching of a column name to a canonical name."""
        # Remove common prefixes/suffixes
        cleaned = re.sub(r"[\s\-_]+", " ", col_name).strip()

        for canonical, aliases in self.column_map.items():
            for alias in aliases:
                alias_clean = re.sub(r"[\s\-_]+", " ", alias.lower()).strip()
                if cleaned == alias_clean:
                    return canonical
                # Partial match: one contains the other (at least 3 chars)
                if len(cleaned) >= 3 and len(alias_clean) >= 3:
                    if cleaned in alias_clean or alias_clean in cleaned:
                        return canonical

        return None

    def _coerce_types(
        self, df: pd.DataFrame, errors: list[ValidationError]
    ) -> pd.DataFrame:
        """Coerce column types: numeric, date, string."""
        # Numeric columns
        for col in self.numeric_columns:
            if col not in df.columns:
                continue
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # Date columns
        for col in DATE_COLUMNS:
            if col not in df.columns:
                continue
            df[col] = pd.to_datetime(df[col], errors="coerce").astype(str)
            # Replace 'NaT' string with empty
            df[col] = df[col].replace("NaT", "")

        # String columns: ensure metric_name and entity are strings
        for col in ["metric_name", "entity"]:
            if col in df.columns:
                df[col] = df[col].astype(str).replace("nan", "")

        return df

    def _validate_rows(self, df: pd.DataFrame) -> list[ValidationError]:
        """Validate each row for required fields and data types."""
        errors: list[ValidationError] = []

        for idx, row in df.iterrows():
            # Check required fields
            for col in self.required_columns:
                if col in df.columns:
                    val = row.get(col)
                    if val is None or (isinstance(val, str) and not val.strip()):
                        errors.append(ValidationError(
                            row_index=int(idx),
                            column=col,
                            message=f"Required field '{col}' is empty",
                            raw_value=val,
                        ))

            # Check numeric values
            for col in self.numeric_columns:
                if col in df.columns:
                    val = row.get(col)
                    if val is not None:
                        try:
                            float(val)
                        except (ValueError, TypeError):
                            errors.append(ValidationError(
                                row_index=int(idx),
                                column=col,
                                message=f"Value '{val}' is not a valid number",
                                raw_value=val,
                            ))

        return errors

    def parse_from_df(self, df: pd.DataFrame) -> ParseResult:
        """Run column mapping, type coercion, and validation on an existing DataFrame."""
        errors: list[ValidationError] = []
        df = df.copy()
        df = self._map_columns(df, errors)
        df = self._coerce_types(df, errors)
        errors.extend(self._validate_rows(df))
        return ParseResult(
            dataframe=df,
            errors=errors,
            row_count=len(df),
            column_count=len(df.columns),
        )

    @classmethod
    def from_dataframe(cls, df: pd.DataFrame) -> ParseResult:
        """Create a ParseResult from an already-loaded DataFrame.

        Useful for testing or when data comes from other sources.
        """
        return ParseResult(
            dataframe=df,
            errors=[],
            row_count=len(df),
            column_count=len(df.columns),
        )
