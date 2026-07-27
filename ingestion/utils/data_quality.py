"""Lightweight data quality validation module.

Runs quality checks against the raw tables in PostgreSQL.
Implements the same checks defined in Great Expectations suites
but using plain pandas/SQL — no external dependencies needed.

When Great Expectations is installed, use the full GX runner instead.
This module serves as both a fallback and a quick validation tool.

Usage:
    python -m ingestion.utils.data_quality
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy import create_engine, text

from ingestion.utils.config import get_database_url

logger = logging.getLogger(__name__)


@dataclass
class CheckResult:
    """Result of a single data quality check."""

    table: str
    check_name: str
    passed: bool
    details: str


def run_all_checks() -> list[CheckResult]:
    """Run all data quality checks against raw tables.

    Returns:
        List of CheckResult objects.
    """
    engine = create_engine(get_database_url())
    results: list[CheckResult] = []

    with engine.connect() as conn:
        results.extend(_check_wfp_prices(conn))
        results.extend(_check_worldbank_prices(conn))
        results.extend(_check_nbs_prices(conn))
        results.extend(_check_cbn_rates(conn))
        results.extend(_check_weather(conn))

    return results


def _check_wfp_prices(conn) -> list[CheckResult]:
    """Validate raw.wfp_prices table."""
    table = "raw.wfp_prices"
    results = []

    # Row count
    count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    results.append(
        CheckResult(
            table=table,
            check_name="row_count",
            passed=count is not None and count >= 1000,
            details=f"Row count: {count} (expected >= 1000)",
        )
    )

    if not count:
        return results

    # Null checks
    for col in ["market_name", "commodity_name", "price", "price_date"]:
        null_count = conn.execute(
            text(f"SELECT count(*) FROM {table} WHERE {col} IS NULL")
        ).scalar()
        results.append(
            CheckResult(
                table=table,
                check_name=f"not_null_{col}",
                passed=null_count == 0,
                details=f"Nulls in {col}: {null_count}",
            )
        )

    # Price range
    stats = conn.execute(
        text(f"SELECT min(price), max(price), avg(price) FROM {table} WHERE price IS NOT NULL")
    ).fetchone()
    min_p, max_p, avg_p = stats
    results.append(
        CheckResult(
            table=table,
            check_name="price_range",
            passed=min_p > 0 and max_p < 200000,
            details=f"Price range: {min_p:.2f} - {max_p:.2f} (avg: {avg_p:.2f})",
        )
    )

    # Freshness
    latest = conn.execute(text(f"SELECT max(price_date) FROM {table}")).scalar()
    days_old = (date.today() - latest).days if latest else 999
    results.append(
        CheckResult(
            table=table,
            check_name="freshness",
            passed=days_old <= 90,
            details=f"Latest data: {latest} ({days_old} days old)",
        )
    )

    return results


def _check_worldbank_prices(conn) -> list[CheckResult]:
    """Validate raw.worldbank_prices table."""
    table = "raw.worldbank_prices"
    results = []

    count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    results.append(
        CheckResult(
            table=table,
            check_name="row_count",
            passed=count is not None and count >= 1000,
            details=f"Row count: {count} (expected >= 1000)",
        )
    )

    if not count:
        return results

    # Null checks
    for col in ["market_name", "commodity_name", "price", "price_date"]:
        null_count = conn.execute(
            text(f"SELECT count(*) FROM {table} WHERE {col} IS NULL")
        ).scalar()
        results.append(
            CheckResult(
                table=table,
                check_name=f"not_null_{col}",
                passed=null_count == 0,
                details=f"Nulls in {col}: {null_count}",
            )
        )

    # Price range
    stats = conn.execute(
        text(f"SELECT min(price), max(price) FROM {table} WHERE price IS NOT NULL")
    ).fetchone()
    min_p, max_p = stats
    results.append(
        CheckResult(
            table=table,
            check_name="price_range",
            passed=min_p > 0 and max_p < 50000,
            details=f"Price range: {min_p:.2f} - {max_p:.2f}",
        )
    )

    return results


def _check_nbs_prices(conn) -> list[CheckResult]:
    """Validate raw.nbs_prices table."""
    table = "raw.nbs_prices"
    results = []

    count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    results.append(
        CheckResult(
            table=table,
            check_name="row_count",
            passed=count is not None and count >= 10,
            details=f"Row count: {count} (expected >= 10)",
        )
    )

    if not count:
        return results

    # Price range
    stats = conn.execute(
        text(f"SELECT min(price), max(price) FROM {table} WHERE price IS NOT NULL")
    ).fetchone()
    min_p, max_p = stats
    results.append(
        CheckResult(
            table=table,
            check_name="price_range",
            passed=min_p >= 50 and max_p <= 50000,
            details=f"Price range: {min_p:.2f} - {max_p:.2f}",
        )
    )

    return results


def _check_cbn_rates(conn) -> list[CheckResult]:
    """Validate raw.cbn_rates table."""
    table = "raw.cbn_rates"
    results = []

    count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    results.append(
        CheckResult(
            table=table,
            check_name="row_count",
            passed=count is not None and count >= 1,
            details=f"Row count: {count}",
        )
    )

    return results


def _check_weather(conn) -> list[CheckResult]:
    """Validate raw.weather table."""
    table = "raw.weather"
    results = []

    count = conn.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    results.append(
        CheckResult(
            table=table,
            check_name="row_count",
            passed=count is not None and count >= 0,
            details=f"Row count: {count} (weather is optional)",
        )
    )

    return results


def print_report(results: list[CheckResult]) -> None:
    """Print a formatted quality report."""
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total = len(results)

    print("\n" + "=" * 70)
    print("DATA QUALITY REPORT")
    print("=" * 70)

    current_table = ""
    for r in results:
        if r.table != current_table:
            current_table = r.table
            print(f"\n  {current_table}")
            print(f"  {'─' * 50}")

        status = "✅ PASS" if r.passed else "❌ FAIL"
        print(f"    {status} | {r.check_name}: {r.details}")

    print(f"\n{'─' * 70}")
    print(f"  SUMMARY: {passed}/{total} passed, {failed} failed")
    print("=" * 70)

    return failed == 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = run_all_checks()
    all_passed = print_report(results)
    if not all_passed:
        exit(1)
