"""Data cleaning service: dedup, missing values, range validation, date normalization."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class CleaningError:
    """Single data cleaning error or warning."""

    row_index: int
    rule: str
    message: str
    original_value: Any = None
    corrected_value: Any = None
    severity: str = "error"  # error | warning | auto_fixed


@dataclass
class CleaningResult:
    """Result of the data cleaning process."""

    dataframe: pd.DataFrame
    errors: list[CleaningError]
    original_row_count: int
    cleaned_row_count: int
    removed_row_count: int
    auto_fixed_count: int = 0


# Range validation rules for financial metrics
RANGE_RULES: dict[str, tuple[float | None, float | None]] = {
    "gross_profit_rate": (-1.0, 1.0),
    "net_profit_rate": (-1.0, 1.0),
    "dso": (0.0, 365.0),
    "ito": (0.0, 365.0),
    "dpo": (0.0, 365.0),
    "cash_conversion_cycle": (-365.0, 365.0),
    "revenue": (0.0, None),
    "cost": (0.0, None),
    "ar_amount": (0.0, None),
    "ap_amount": (0.0, None),
    "inventory": (0.0, None),
    "metric_value": (None, None),  # no range limit for generic metric
}

# Positive-only columns (amounts that must be >= 0)
POSITIVE_COLUMNS = {"revenue", "cost", "ar_amount", "ap_amount", "inventory"}


class DataCleaner:
    """Clean and validate financial data DataFrame.

    Handles deduplication, missing values, range validation,
    date normalization, and cross-validation with original data.
    """

    def __init__(
        self,
        dedup_keys: list[str] | None = None,
        range_rules: dict[str, tuple[float | None, float | None]] | None = None,
        fill_defaults: dict[str, Any] | None = None,
    ) -> None:
        self.dedup_keys = dedup_keys or ["metric_name", "period", "entity"]
        self.range_rules = range_rules or RANGE_RULES
        self.fill_defaults = fill_defaults or {
            "metric_unit": "",
            "entity": "",
            "tags": {},
        }

    def clean(
        self,
        df: pd.DataFrame,
        original_df: pd.DataFrame | None = None,
    ) -> CleaningResult:
        """Run the full cleaning pipeline.

        Args:
            df: DataFrame to clean (from Excel parser).
            original_df: Original raw DataFrame for cross-validation.

        Returns:
            CleaningResult with cleaned DataFrame and error log.
        """
        original_count = len(df)
        errors: list[CleaningError] = []
        auto_fixed = 0

        logger.info("Starting data cleaning: %d rows", original_count)

        # Step 1: Date normalization
        df, step_errors, fixed = self._normalize_dates(df)
        errors.extend(step_errors)
        auto_fixed += fixed

        # Step 2: Missing value handling
        df, step_errors, fixed = self._handle_missing_values(df)
        errors.extend(step_errors)
        auto_fixed += fixed

        # Step 3: Range validation
        df, step_errors, fixed = self._validate_ranges(df)
        errors.extend(step_errors)
        auto_fixed += fixed

        # Step 4: Deduplication
        df, step_errors = self._deduplicate(df)
        errors.extend(step_errors)

        # Step 5: Cross-validation with original data
        if original_df is not None:
            step_errors = self._cross_validate(df, original_df)
            errors.extend(step_errors)

        cleaned_count = len(df)
        removed_count = original_count - cleaned_count

        result = CleaningResult(
            dataframe=df,
            errors=errors,
            original_row_count=original_count,
            cleaned_row_count=cleaned_count,
            removed_row_count=removed_count,
            auto_fixed_count=auto_fixed,
        )

        logger.info(
            "Cleaning complete: %d -> %d rows (%d removed, %d auto-fixed, %d issues)",
            original_count,
            cleaned_count,
            removed_count,
            auto_fixed,
            len(errors),
        )
        return result

    def _normalize_dates(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[CleaningError], int]:
        """Normalize period column to standard format (YYYY-MM or YYYY-Qn)."""
        errors: list[CleaningError] = []
        fixed = 0

        if "period" not in df.columns:
            return df, errors, fixed

        for idx in df.index:
            val = df.at[idx, "period"]
            if pd.isna(val) or val == "":
                errors.append(CleaningError(
                    row_index=int(idx),
                    rule="date_normalization",
                    message="Empty period value",
                    severity="error",
                ))
                continue

            period_str = str(val).strip()
            normalized = self._normalize_period_string(period_str)

            if normalized != period_str:
                df.at[idx, "period"] = normalized
                errors.append(CleaningError(
                    row_index=int(idx),
                    rule="date_normalization",
                    message=f"Normalized period from '{period_str}' to '{normalized}'",
                    original_value=period_str,
                    corrected_value=normalized,
                    severity="auto_fixed",
                ))
                fixed += 1

        return df, errors, fixed

    @staticmethod
    def _normalize_period_string(period: str) -> str:
        """Normalize various period formats to YYYY-MM or YYYY-Qn."""
        period = period.strip()

        # Already in YYYY-MM format
        if len(period) == 7 and period[4] == "-":
            return period

        # YYYY/MM/DD -> YYYY-MM
        if "/" in period and len(period) == 10:
            try:
                dt = datetime.strptime(period, "%Y/%m/%d")
                return dt.strftime("%Y-%m")
            except ValueError:
                pass

        # YYYY-MM-DD -> YYYY-MM
        if "-" in period and len(period) == 10:
            try:
                dt = datetime.strptime(period, "%Y-%m-%d")
                return dt.strftime("%Y-%m")
            except ValueError:
                pass

        # YYYYQn -> YYYY-Qn
        import re
        m = re.match(r"^(\d{4})[Qq](\d)$", period)
        if m:
            return f"{m.group(1)}-Q{m.group(2)}"

        # YYYY年n季度 -> YYYY-Qn
        m = re.match(r"^(\d{4})年(\d)季度$", period)
        if m:
            return f"{m.group(1)}-Q{m.group(2)}"

        # YYYY年n月 -> YYYY-MM
        m = re.match(r"^(\d{4})年(\d{1,2})月$", period)
        if m:
            return f"{m.group(1)}-{int(m.group(2)):02d}"

        # YYYYMM -> YYYY-MM
        m = re.match(r"^(\d{4})(\d{2})$", period)
        if m:
            return f"{m.group(1)}-{m.group(2)}"

        return period

    def _handle_missing_values(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[CleaningError], int]:
        """Fill missing values with defaults for non-critical columns."""
        errors: list[CleaningError] = []
        fixed = 0

        for col, default in self.fill_defaults.items():
            if col not in df.columns:
                continue

            mask = df[col].isna() | (df[col] == "")
            count = mask.sum()
            if count > 0:
                df.loc[mask, col] = default
                errors.append(CleaningError(
                    row_index=-1,
                    rule="missing_value",
                    message=f"Filled {count} missing values in '{col}' with default",
                    corrected_value=default,
                    severity="auto_fixed",
                ))
                fixed += int(count)

        return df, errors, fixed

    def _validate_ranges(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[CleaningError], int]:
        """Validate numeric columns against expected ranges."""
        errors: list[CleaningError] = []
        fixed = 0
        rows_to_drop: list[int] = []

        for col, (min_val, max_val) in self.range_rules.items():
            if col not in df.columns:
                continue

            for idx in df.index:
                val = df.at[idx, col]
                if pd.isna(val):
                    continue

                try:
                    num_val = float(val)
                except (ValueError, TypeError):
                    continue

                if min_val is not None and num_val < min_val:
                    errors.append(CleaningError(
                        row_index=int(idx),
                        rule="range_validation",
                        message=f"{col}={num_val} is below minimum {min_val}",
                        original_value=num_val,
                        severity="error",
                    ))
                    rows_to_drop.append(int(idx))

                elif max_val is not None and num_val > max_val:
                    errors.append(CleaningError(
                        row_index=int(idx),
                        rule="range_validation",
                        message=f"{col}={num_val} exceeds maximum {max_val}",
                        original_value=num_val,
                        severity="error",
                    ))
                    rows_to_drop.append(int(idx))

        # Drop rows with range violations
        if rows_to_drop:
            unique_drops = list(set(rows_to_drop))
            df = df.drop(index=unique_drops).reset_index(drop=True)

        return df, errors, fixed

    def _deduplicate(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, list[CleaningError]]:
        """Remove duplicate rows based on composite key."""
        errors: list[CleaningError] = []

        available_keys = [k for k in self.dedup_keys if k in df.columns]
        if not available_keys:
            return df, errors

        before_count = len(df)
        df = df.drop_duplicates(subset=available_keys, keep="last")
        after_count = len(df)
        removed = before_count - after_count

        if removed > 0:
            errors.append(CleaningError(
                row_index=-1,
                rule="deduplication",
                message=f"Removed {removed} duplicate rows (keys: {available_keys})",
                severity="warning",
            ))

        return df, errors

    def _cross_validate(
        self, cleaned_df: pd.DataFrame, original_df: pd.DataFrame
    ) -> list[CleaningError]:
        """Cross-validate cleaned data against original to detect data loss."""
        errors: list[CleaningError] = []

        # Check that no rows were silently modified in key fields
        key_cols = [c for c in self.dedup_keys if c in cleaned_df.columns and c in original_df.columns]
        if not key_cols:
            return errors

        cleaned_keys = set()
        for _, row in cleaned_df.iterrows():
            key = tuple(str(row.get(k, "")) for k in key_cols)
            cleaned_keys.add(key)

        # Check for rows that exist in original but not in cleaned
        missing_keys: set[tuple] = set()
        for _, row in original_df.iterrows():
            key = tuple(str(row.get(k, "")) for k in key_cols)
            if key not in cleaned_keys:
                missing_keys.add(key)

        if missing_keys:
            errors.append(CleaningError(
                row_index=-1,
                rule="cross_validation",
                message=f"{len(missing_keys)} rows from original data not in cleaned output",
                severity="warning",
            ))

        return errors
