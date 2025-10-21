"""
Dagster Definitions for HeronAI AR Dashboard
Production configuration with persistent storage
"""
from pathlib import Path
from dagster import Definitions, load_assets_from_modules, FilesystemIOManager
import dagster_pipeline.assets as assets_module 

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

# Configure persistent storage directory
# This directory will store intermediate data between pipeline steps
STORAGE_DIR = Path(__file__).parent.parent / "dagster_storage"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

# Define all resources, jobs, and schedules
defs = Definitions(
    assets=all_assets,
    
    jobs=[
        full_etl_job,              # PRIMARY: Use this for scheduled runs
        extract_only_job,          # Utility: Extract data only
        transform_only_job,        # Utility: Transform (requires extract first)
        load_only_job,             # Utility: Load (requires extract + transform)
        refresh_ar_summary_job     # Utility: Quick AR summary refresh
    ],
    
    schedules=[
        daily_etl_schedule,        # Runs full_etl_job daily at 6 AM
        ar_summary_refresh_schedule  # Refreshes AR summary every 4 hours
    ],
    
    resources={
        # Filesystem IO Manager: Persists data between pipeline steps
        # Stores intermediate results (raw_customers, transformed_invoices, etc.)
        "io_manager": FilesystemIOManager(
            base_dir=str(STORAGE_DIR)
        )
    }
)