"""Great Expectations v1 validation runner.

Validates raw tables against expectations using GX 1.x API.

Usage:
    python -m ingestion.utils.gx_validator
"""

from __future__ import annotations

import logging

import great_expectations as gx
import great_expectations.expectations as gxe
from ingestion.utils.config import get_database_url

logger = logging.getLogger(__name__)


def validate_wfp_prices() -> bool:
    """Validate raw.wfp_prices table."""
    logger.info("Validating raw.wfp_prices...")

    context = gx.get_context()
    db_url = get_database_url()

    # Connect to database
    datasource = context.data_sources.add_or_update_sql(name="pg", connection_string=db_url)
    asset = datasource.add_table_asset(
        name="wfp_prices", table_name="wfp_prices", schema_name="raw"
    )
    batch_definition = asset.add_batch_definition_whole_table("full")

    # Define expectations
    suite = context.suites.add_or_update(gx.ExpectationSuite(name="wfp_prices_suite"))
    suite.expectations = [
        gxe.ExpectTableRowCountToBeBetween(min_value=1000, max_value=500000),
        gxe.ExpectColumnValuesToNotBeNull(column="market_name"),
        gxe.ExpectColumnValuesToNotBeNull(column="commodity_name"),
        gxe.ExpectColumnValuesToNotBeNull(column="price"),
        gxe.ExpectColumnValuesToNotBeNull(column="price_date"),
        gxe.ExpectColumnValuesToBeBetween(column="price", min_value=0.01, max_value=200000),
    ]
    suite.save()

    # Validate
    validation_definition = context.validation_definitions.add_or_update(
        gx.ValidationDefinition(
            name="wfp_validation",
            data=batch_definition,
            suite=suite,
        )
    )
    result = validation_definition.run()
    success = result.success

    if success:
        logger.info("  ✅ raw.wfp_prices: ALL PASSED")
    else:
        logger.warning("  ❌ raw.wfp_prices: FAILED")
        for r in result.results:
            if not r.success:
                logger.warning(f"    {r.expectation_config.type}: {r.result}")

    return success


def validate_worldbank_prices() -> bool:
    """Validate raw.worldbank_prices table."""
    logger.info("Validating raw.worldbank_prices...")

    context = gx.get_context()
    db_url = get_database_url()

    datasource = context.data_sources.add_or_update_sql(name="pg", connection_string=db_url)
    asset = datasource.add_table_asset(
        name="worldbank_prices", table_name="worldbank_prices", schema_name="raw"
    )
    batch_definition = asset.add_batch_definition_whole_table("full")

    suite = context.suites.add_or_update(gx.ExpectationSuite(name="worldbank_prices_suite"))
    suite.expectations = [
        gxe.ExpectTableRowCountToBeBetween(min_value=1000, max_value=200000),
        gxe.ExpectColumnValuesToNotBeNull(column="market_name"),
        gxe.ExpectColumnValuesToNotBeNull(column="commodity_name"),
        gxe.ExpectColumnValuesToNotBeNull(column="price"),
        gxe.ExpectColumnValuesToNotBeNull(column="price_date"),
        gxe.ExpectColumnValuesToBeBetween(column="price", min_value=1, max_value=50000),
    ]
    suite.save()

    validation_definition = context.validation_definitions.add_or_update(
        gx.ValidationDefinition(
            name="worldbank_validation",
            data=batch_definition,
            suite=suite,
        )
    )
    result = validation_definition.run()
    success = result.success

    if success:
        logger.info("  ✅ raw.worldbank_prices: ALL PASSED")
    else:
        logger.warning("  ❌ raw.worldbank_prices: FAILED")
        for r in result.results:
            if not r.success:
                logger.warning(f"    {r.expectation_config.type}: {r.result}")

    return success


def validate_nbs_prices() -> bool:
    """Validate raw.nbs_prices table."""
    logger.info("Validating raw.nbs_prices...")

    context = gx.get_context()
    db_url = get_database_url()

    datasource = context.data_sources.add_or_update_sql(name="pg", connection_string=db_url)
    asset = datasource.add_table_asset(
        name="nbs_prices", table_name="nbs_prices", schema_name="raw"
    )
    batch_definition = asset.add_batch_definition_whole_table("full")

    suite = context.suites.add_or_update(gx.ExpectationSuite(name="nbs_prices_suite"))
    suite.expectations = [
        gxe.ExpectTableRowCountToBeBetween(min_value=10, max_value=50000),
        gxe.ExpectColumnValuesToNotBeNull(column="commodity_name"),
        gxe.ExpectColumnValuesToNotBeNull(column="price"),
        gxe.ExpectColumnValuesToBeBetween(column="price", min_value=50, max_value=50000),
    ]
    suite.save()

    validation_definition = context.validation_definitions.add_or_update(
        gx.ValidationDefinition(
            name="nbs_validation",
            data=batch_definition,
            suite=suite,
        )
    )
    result = validation_definition.run()
    success = result.success

    if success:
        logger.info("  ✅ raw.nbs_prices: ALL PASSED")
    else:
        logger.warning("  ❌ raw.nbs_prices: FAILED")
        for r in result.results:
            if not r.success:
                logger.warning(f"    {r.expectation_config.type}: {r.result}")

    return success


def validate_cbn_rates() -> bool:
    """Validate raw.cbn_rates table."""
    logger.info("Validating raw.cbn_rates...")

    context = gx.get_context()
    db_url = get_database_url()

    datasource = context.data_sources.add_or_update_sql(name="pg", connection_string=db_url)
    asset = datasource.add_table_asset(name="cbn_rates", table_name="cbn_rates", schema_name="raw")
    batch_definition = asset.add_batch_definition_whole_table("full")

    suite = context.suites.add_or_update(gx.ExpectationSuite(name="cbn_rates_suite"))
    suite.expectations = [
        gxe.ExpectTableRowCountToBeBetween(min_value=1, max_value=100000),
        gxe.ExpectColumnValuesToNotBeNull(column="rate_date"),
        gxe.ExpectColumnValuesToNotBeNull(column="central_rate"),
        gxe.ExpectColumnValuesToBeBetween(column="central_rate", min_value=100, max_value=5000),
    ]
    suite.save()

    validation_definition = context.validation_definitions.add_or_update(
        gx.ValidationDefinition(
            name="cbn_validation",
            data=batch_definition,
            suite=suite,
        )
    )
    result = validation_definition.run()
    success = result.success

    if success:
        logger.info("  ✅ raw.cbn_rates: ALL PASSED")
    else:
        logger.warning("  ❌ raw.cbn_rates: FAILED")
        for r in result.results:
            if not r.success:
                logger.warning(f"    {r.expectation_config.type}: {r.result}")

    return success


def validate_weather() -> bool:
    """Validate raw.weather table."""
    logger.info("Validating raw.weather...")

    context = gx.get_context()
    db_url = get_database_url()

    datasource = context.data_sources.add_or_update_sql(name="pg", connection_string=db_url)
    asset = datasource.add_table_asset(name="weather", table_name="weather", schema_name="raw")
    batch_definition = asset.add_batch_definition_whole_table("full")

    suite = context.suites.add_or_update(gx.ExpectationSuite(name="weather_data_suite"))
    suite.expectations = [
        gxe.ExpectTableRowCountToBeBetween(min_value=0, max_value=500000),
        gxe.ExpectColumnValuesToNotBeNull(column="market_name"),
        gxe.ExpectColumnValuesToNotBeNull(column="weather_date"),
        gxe.ExpectColumnValuesToBeBetween(
            column="temperature_max", min_value=15, max_value=50, mostly=0.95
        ),
        gxe.ExpectColumnValuesToBeBetween(
            column="precipitation_mm", min_value=0, max_value=500, mostly=0.95
        ),
    ]
    suite.save()

    validation_definition = context.validation_definitions.add_or_update(
        gx.ValidationDefinition(
            name="weather_validation",
            data=batch_definition,
            suite=suite,
        )
    )
    result = validation_definition.run()
    success = result.success

    if success:
        logger.info("  ✅ raw.weather: ALL PASSED")
    else:
        logger.warning("  ❌ raw.weather: FAILED")
        for r in result.results:
            if not r.success:
                logger.warning(f"    {r.expectation_config.type}: {r.result}")

    return success


def validate_all() -> bool:
    """Run all validations."""
    results = {}

    try:
        results["wfp_prices"] = validate_wfp_prices()
    except Exception as e:
        logger.error(f"WFP validation error: {e}")
        results["wfp_prices"] = False

    try:
        results["worldbank_prices"] = validate_worldbank_prices()
    except Exception as e:
        logger.error(f"WorldBank validation error: {e}")
        results["worldbank_prices"] = False

    try:
        results["nbs_prices"] = validate_nbs_prices()
    except Exception as e:
        logger.error(f"NBS validation error: {e}")
        results["nbs_prices"] = False

    try:
        results["cbn_rates"] = validate_cbn_rates()
    except Exception as e:
        logger.error(f"CBN validation error: {e}")
        results["cbn_rates"] = False

    try:
        results["weather"] = validate_weather()
    except Exception as e:
        logger.error(f"Weather validation error: {e}")
        results["weather"] = False

    # Summary
    print("\n" + "=" * 50)
    print("GREAT EXPECTATIONS VALIDATION RESULTS")
    print("=" * 50)
    for table, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] | raw.{table}")

    all_passed = all(results.values())
    print(f"\n  {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    return all_passed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    success = validate_all()
    if not success:
        exit(1)
