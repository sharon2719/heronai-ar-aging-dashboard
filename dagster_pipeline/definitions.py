"""
Dagster Definitions for HeronAI AR Dashboard
Combines all assets, jobs, and schedules
"""
from dagster import Definitions, load_assets_from_modules
import dagster_pipeline.assets as assets_module  # ✅ FIXED import

# Load all assets
all_assets = load_assets_from_modules([assets_module])

# Import jobs and schedules from assets module
from dagster_pipeline.assets import (
    full_etl_job,
    extract_only_job,
    transform_only_job,
    load_only_job,
    refresh_ar_summary_job,
    daily_etl_schedule,
    ar_summary_refresh_schedule
)

# Define all resources, jobs, and schedules
defs = Definitions(
    assets=all_assets,
    jobs=[
        full_etl_job,
        extract_only_job,
        transform_only_job,
        load_only_job,
        refresh_ar_summary_job
    ],
    schedules=[
        daily_etl_schedule,
        ar_summary_refresh_schedule
    ]
)
