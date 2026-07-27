"""Post-ingestion validation runner.

Runs all data quality checks (both lightweight SQL checks and Great Expectations)
after ingestion completes. Designed to be called as a pipeline step:

    ingest → validate → transform (dbt)

If validation fails, the pipeline should halt before dbt runs.

Usage:
    python -m ingestion.validate

Exit codes:
    0 - All validations passed
    1 - One or more validations failed
"""

from __future__ import annotations

import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_sql_checks() -> tuple[int, int]:
    """Run lightweight SQL-based data quality checks.

    Returns:
        Tuple of (passed_count, failed_count).
    """
    from ingestion.utils.data_quality import run_all_checks

    logger.info("Running SQL-based data quality checks...")
    results = run_all_checks()

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)

    for r in results:
        status = "[PASS]" if r.passed else "[FAIL]"
        logger.info(f"  {status} {r.table} / {r.check_name}: {r.details}")

    return passed, failed


def run_gx_checks() -> tuple[int, int]:
    """Run Great Expectations validation suites.

    Returns:
        Tuple of (passed_count, failed_count).
    """
    try:
        from ingestion.utils.gx_validator import (
            validate_cbn_rates,
            validate_nbs_prices,
            validate_weather,
            validate_wfp_prices,
            validate_worldbank_prices,
        )

        logger.info("Running Great Expectations validations...")

        results = {}
        results["wfp_prices"] = validate_wfp_prices()
        results["worldbank_prices"] = validate_worldbank_prices()
        results["nbs_prices"] = validate_nbs_prices()
        results["cbn_rates"] = validate_cbn_rates()
        results["weather"] = validate_weather()

        passed = sum(1 for v in results.values() if v)
        failed = sum(1 for v in results.values() if not v)
        return passed, failed

    except ImportError:
        logger.warning("Great Expectations not installed - skipping GX validations")
        return 0, 0
    except Exception as e:
        logger.error(f"GX validation error: {e}")
        return 0, 1


def log_to_database(sql_passed: int, sql_failed: int, gx_passed: int, gx_failed: int) -> None:
    """Log validation results to the data_quality_log table."""
    import json

    from sqlalchemy import create_engine, text

    from ingestion.utils.config import get_database_url

    try:
        engine = create_engine(get_database_url())
        with engine.begin() as conn:
            conn.execute(
                text("""
                    INSERT INTO raw.data_quality_log (suite_name, success, statistics, results_summary)
                    VALUES (:suite, :success, :stats, :summary)
                """),
                {
                    "suite": "post_ingestion_validation",
                    "success": sql_failed == 0 and gx_failed == 0,
                    "stats": json.dumps(
                        {
                            "sql_passed": sql_passed,
                            "sql_failed": sql_failed,
                            "gx_passed": gx_passed,
                            "gx_failed": gx_failed,
                            "total_passed": sql_passed + gx_passed,
                            "total_failed": sql_failed + gx_failed,
                        }
                    ),
                    "summary": (
                        f"SQL: {sql_passed} passed, {sql_failed} failed | "
                        f"GX: {gx_passed} passed, {gx_failed} failed"
                    ),
                },
            )
        logger.info("Validation results logged to raw.data_quality_log")
    except Exception as e:
        logger.warning(f"Could not log to database: {e}")


def main() -> None:
    """Run the full post-ingestion validation suite."""
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("POST-INGESTION VALIDATION")
    logger.info("=" * 60)

    # Phase 1: SQL checks (fast, no external deps)
    sql_passed, sql_failed = run_sql_checks()

    logger.info("")

    # Phase 2: Great Expectations (comprehensive, slower)
    gx_passed, gx_failed = run_gx_checks()

    # Log results to database
    log_to_database(sql_passed, sql_failed, gx_passed, gx_failed)

    # Final report
    elapsed = time.time() - start_time
    total_passed = sql_passed + gx_passed
    total_failed = sql_failed + gx_failed

    logger.info("")
    logger.info("=" * 60)
    logger.info("VALIDATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  SQL checks:  {sql_passed} passed, {sql_failed} failed")
    logger.info(f"  GX suites:   {gx_passed} passed, {gx_failed} failed")
    logger.info(f"  Total:       {total_passed} passed, {total_failed} failed")
    logger.info(f"  Duration:    {elapsed:.1f}s")
    logger.info("=" * 60)

    if total_failed > 0:
        logger.error("VALIDATION FAILED - Pipeline should halt before dbt transform.")
        sys.exit(1)
    else:
        logger.info("ALL VALIDATIONS PASSED - Safe to proceed with dbt transform.")
        sys.exit(0)


if __name__ == "__main__":
    main()
